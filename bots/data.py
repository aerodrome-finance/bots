import functools
import asyncio
from thefuzz import fuzz
from web3 import AsyncWeb3, AsyncHTTPProvider
from web3.constants import ADDRESS_ZERO
from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional

from .settings import (
    WEB3_PROVIDER_URI,
    LP_SUGAR_ADDRESS,
    LP_SUGAR_ABI,
    PRICE_ORACLE_ADDRESS,
    PRICE_ORACLE_ABI,
    CONNECTOR_TOKENS_ADDRESSES,
    STABLE_TOKEN_ADDRESS,
    SUGAR_TOKENS_CACHE_MINUTES,
    SUGAR_LPS_CACHE_MINUTES,
    ORACLE_PRICES_CACHE_MINUTES,
    PRICE_BATCH_SIZE,
    GOOD_ENOUGH_PAGINATION_LIMIT,
    POOL_PAGE_SIZE,
    PRICE_THRESHOLD_FILTER,
)
from .helpers import cache_in_seconds, normalize_address, chunk

w3 = AsyncWeb3(AsyncHTTPProvider(WEB3_PROVIDER_URI))


@dataclass(frozen=True)
class Token:
    """Data class for Token

    based on:
    https://github.com/velodrome-finance/sugar/blob/v2/contracts/LpSugar.vy#L17
    """

    token_address: str
    symbol: str
    decimals: int
    listed: bool

    def value_from_bigint(self, value: float) -> float:
        return value / 10**self.decimals

    @classmethod
    def from_tuple(cls, t: Tuple) -> "Token":
        (token_address, symbol, decimals, _, listed) = t
        return Token(
            token_address=normalize_address(token_address),
            symbol=symbol,
            decimals=decimals,
            listed=listed,
        )

    @classmethod
    @cache_in_seconds(SUGAR_TOKENS_CACHE_MINUTES * 60)
    async def get_all_listed_tokens(cls) -> List["Token"]:
        tokens = await cls.get_all_tokens()
        return list(filter(lambda t: t.listed, tokens))

    @classmethod
    @cache_in_seconds(SUGAR_TOKENS_CACHE_MINUTES * 60)
    async def get_all_tokens(cls) -> List["Token"]:
        sugar = w3.eth.contract(address=LP_SUGAR_ADDRESS, abi=LP_SUGAR_ABI)
        tokens = await sugar.functions.tokens(
            GOOD_ENOUGH_PAGINATION_LIMIT, 0, ADDRESS_ZERO, []
        ).call()
        return list(map(lambda t: Token.from_tuple(t), tokens))

    @classmethod
    async def get_by_token_address(cls, token_address: str) -> Optional["Token"]:
        """Get details for specific token

        Args:
            token_address (str): token address

        Returns:
            Token: target token or None
        """
        try:
            normalized_address = normalize_address(token_address)
            tokens = await cls.get_all_listed_tokens()
            return next(t for t in tokens if t.token_address == normalized_address)
        except Exception:
            return None


@dataclass(frozen=True)
class Amount:
    token: Token
    amount: float
    price: "Price"

    @classmethod
    def build(
        cls,
        address: str,
        amount: float,
        tokens: Dict[str, Token],
        prices: Dict[str, "Price"],
    ) -> "Amount":
        address = normalize_address(address)

        if address not in tokens or address not in prices:
            return None

        token = tokens[address]

        return Amount(
            token=token, amount=token.value_from_bigint(amount), price=prices[address]
        )

    @property
    def amount_in_stable(self) -> float:
        return self.amount * self.price.price


@dataclass(frozen=True)
class Price:
    """Data class for Token Price

    based on:
    https://github.com/velodrome-finance/oracle/blob/main/contracts/VeloOracle.sol
    """

    token: Token
    price: float

    @property
    def pretty_price(self) -> float:
        return round(self.price, 5)

    @classmethod
    @cache_in_seconds(ORACLE_PRICES_CACHE_MINUTES * 60)
    async def _get_prices(
        cls,
        tokens: Tuple[Token],
        stable_token: str,
        connector_tokens: Tuple[str],
        base_rate: float,
    ):
        price_oracle = w3.eth.contract(
            address=PRICE_ORACLE_ADDRESS, abi=PRICE_ORACLE_ABI
        )
        token_list = list(map(lambda t: t.token_address, tokens))
        prices = await price_oracle.functions.getManyRatesToEthWithCustomConnectors(
            token_list,
            False,
            token_list + list(connector_tokens) + [stable_token],
            PRICE_THRESHOLD_FILTER,
        ).call()

        results = []

        for cnt, price in enumerate(prices):
            token = tokens[cnt]
            # XX: decimals are auto set to 18
            denom = 10 ** (18 + (18 - token.decimals))

            conv_price = (price / denom) / base_rate
            results.append(Price(token=token, price=conv_price))

        return results

    @classmethod
    async def get_prices(
        cls,
        tokens: List[Token],
        stable_token: str = STABLE_TOKEN_ADDRESS,
        connector_tokens: List[str] = CONNECTOR_TOKENS_ADDRESSES,
    ) -> List["Price"]:
        """Get prices for tokens in target stable token

        Args:
            tokens (List[Token]): tokens to get prices for
            stable_token (str, optional): stable token to price in.
            Defaults to STABLE_TOKEN_ADDRESS.
            connector_tokens (List[str], optional): connector tokens to use for pricing.
            Defaults to CONNECTOR_TOKENS_ADDRESSES.

        Returns:
            List: list of Price objects
        """
        stable = await Token.get_by_token_address(STABLE_TOKEN_ADDRESS)
        [base_price] = await cls._get_prices(
            tuple([stable]),
            stable_token,
            tuple(connector_tokens),
            # base rate is 1, since we don't want any conversion applied
            1,
        )

        # assume the pricing is wrong if the base price failed
        base_rate = 0 if base_price is None else base_price.price

        batches = await asyncio.gather(
            *map(
                lambda ts: cls._get_prices(
                    # XX: lists are not cacheable, convert them to tuples so lru cache is happy
                    tuple(ts),
                    stable_token,
                    tuple(connector_tokens),
                    base_rate,
                ),
                list(chunk(tokens, PRICE_BATCH_SIZE)),
            )
        )
        return functools.reduce(lambda l1, l2: l1 + l2, batches, [])


@dataclass(frozen=True)
class LiquidityPool:
    """Data class for Liquidity Pool

    based on:
    https://github.com/velodrome-finance/sugar/blob/v2/contracts/LpSugar.vy#L31
    """

    lp: str
    symbol: str
    is_stable: bool
    total_supply: float
    decimals: int
    token0: Token
    reserve0: Amount
    token1: Token
    reserve1: Amount
    token0_fees: Amount
    token1_fees: Amount
    pool_fee: float
    gauge_total_supply: float
    emissions: Amount
    emissions_token: Token
    weekly_emissions: Amount
    nfpm: str
    alm: str

    @classmethod
    def from_tuple(
        cls, t: Tuple, tokens: Dict[str, Token], prices: Dict[str, Price]
    ) -> "LiquidityPool":
        token0 = normalize_address(t[7])
        token1 = normalize_address(t[10])
        token0_fees = t[23]
        token1_fees = t[24]
        emissions_token = normalize_address(t[20])
        emissions = t[19]

        seconds_in_a_week = 7 * 24 * 60 * 60

        # Sugar.all returns a tuple with the following structure:
        # { "name": "lp", "type": "address" },          <== 0
        # { "name": "symbol", "type": "string" },       <== 1
        # { "name": "decimals", "type": "uint8" },      <== 2
        # { "name": "liquidity", "type": "uint256" },   <== 3
        # { "name": "type", "type": "int24" },          <== 4
        # { "name": "tick", "type": "int24" },          <== 5
        # { "name": "sqrt_ratio", "type": "uint160" },  <== 6
        # { "name": "token0", "type": "address" },      <== 7
        # { "name": "reserve0", "type": "uint256" },    <== 8
        # { "name": "staked0", "type": "uint256" },     <== 9
        # { "name": "token1", "type": "address" },      <== 10
        # { "name": "reserve1", "type": "uint256" },    <== 11
        # { "name": "staked1", "type": "uint256" },     <== 12
        # { "name": "gauge", "type": "address" },        <== 13
        # { "name": "gauge_liquidity", "type": "uint256" },  <== 14
        # { "name": "gauge_alive", "type": "bool" },        <== 15
        # { "name": "fee", "type": "address" },             <== 16
        # { "name": "bribe", "type": "address" },           <== 17
        # { "name": "factory", "type": "address" },         <== 18
        # { "name": "emissions", "type": "uint256" },       <== 19
        # { "name": "emissions_token", "type": "address" },  <== 20
        # { "name": "pool_fee", "type": "uint256" },        <== 21
        # { "name": "unstaked_fee", "type": "uint256" },    <== 22
        # { "name": "token0_fees", "type": "uint256" },     <== 23
        # { "name": "token1_fees", "type": "uint256" },    <== 24
        # { "name": "nfpm", "type": "address" },           <== 25
        # { "name": "alm", "type": "address" }             <== 26

        return LiquidityPool(
            lp=normalize_address(t[0]),
            symbol=t[1],
            # stable pools have type set to 0
            is_stable=t[4] == 0,
            total_supply=t[3],
            decimals=t[2],
            token0=tokens.get(token0),
            reserve0=Amount.build(token0, t[8], tokens, prices),
            token1=tokens.get(token1),
            reserve1=Amount.build(token1, t[11], tokens, prices),
            token0_fees=Amount.build(token0, token0_fees, tokens, prices),
            token1_fees=Amount.build(token1, token1_fees, tokens, prices),
            pool_fee=t[21],
            gauge_total_supply=t[14],
            emissions_token=tokens.get(emissions_token),
            emissions=Amount.build(emissions_token, emissions, tokens, prices),
            weekly_emissions=Amount.build(
                emissions_token, emissions * seconds_in_a_week, tokens, prices
            ),
            nfpm=normalize_address(t[25]),
            alm=normalize_address(t[26]),
        )

    @classmethod
    @cache_in_seconds(SUGAR_LPS_CACHE_MINUTES * 60)
    async def get_pools(cls) -> List["LiquidityPool"]:
        tokens = await Token.get_all_listed_tokens()
        prices = await Price.get_prices(tokens)

        tokens = {t.token_address: t for t in tokens}
        prices = {price.token.token_address: price for price in prices}

        sugar = w3.eth.contract(address=LP_SUGAR_ADDRESS, abi=LP_SUGAR_ABI)
        pools = []
        pool_offset = 0

        while True:
            pools_batch = await sugar.functions.all(POOL_PAGE_SIZE, pool_offset).call()

            pools += pools_batch

            if len(pools_batch) < POOL_PAGE_SIZE:
                break
            else:
                pool_offset += POOL_PAGE_SIZE

        return list(
            filter(
                lambda p: p is not None,
                map(lambda p: LiquidityPool.from_tuple(p, tokens, prices), pools),
            )
        )

    @classmethod
    @cache_in_seconds(SUGAR_LPS_CACHE_MINUTES * 60)
    async def by_address(cls, address: str) -> "LiquidityPool":
        pools = await cls.get_pools()
        try:
            a = normalize_address(address)
            return next(pool for pool in pools if pool.lp == a)
        except Exception:
            return None

    @classmethod
    async def search(cls, query: str, limit: int = 10) -> List["LiquidityPool"]:
        def match_score(query: str, symbol: str):
            return fuzz.token_sort_ratio(query, symbol)

        query_lowercase = query.lower()
        pools = await cls.get_pools()
        pools = list(
            filter(lambda p: p.token0 is not None and p.token1 is not None, pools)
        )

        # look for exact match first, i.e. we get proper pool symbol in query (case insensitive)
        exact_match = list(filter(lambda p: p.symbol.lower() == query_lowercase, pools))

        if len(exact_match) == 1:
            return exact_match

        pools_with_ratio = list(map(lambda p: (p, match_score(query, p.symbol)), pools))
        pools_with_ratio.sort(key=lambda p: p[1], reverse=True)

        return list(map(lambda pwr: pwr[0], pools_with_ratio))[:limit]

    @classmethod
    async def tvl(cls, pools) -> float:
        result = 0

        tokens = await Token.get_all_listed_tokens()
        prices = await Price.get_prices(tokens)
        prices = {price.token.token_address: price for price in prices}

        for pool in pools:
            t0 = pool.token0
            t1 = pool.token1

            if t0:
                result += pool.reserve0.amount_in_stable

            if t1:
                result += pool.reserve1.amount_in_stable

        return result

    @property
    def total_fees(self) -> float:
        result = 0

        if self.token0_fees:
            result += self.token0_fees.amount_in_stable
        if self.token1_fees:
            result += self.token1_fees.amount_in_stable

        return result

    @property
    def pool_fee_percentage(self) -> float:
        return self.pool_fee / 100

    @property
    def volume_pct(self) -> float:
        return 100 / self.pool_fee_percentage

    @property
    def volume(self) -> float:
        t0 = self.token0_fees.amount_in_stable if self.token0_fees else 0
        t1 = self.token1_fees.amount_in_stable if self.token1_fees else 0
        return self.volume_pct * (t0 + t1)

    @property
    def token0_volume(self) -> float:
        return self.token0_fees.amount * self.volume_pct if self.token0_fees else 0

    @property
    def token1_volume(self) -> float:
        return self.token1_fees.amount * self.volume_pct if self.token1_fees else 0

    def apr(self, tvl: float) -> float:
        day_seconds = 24 * 60 * 60
        reward_value = self.emissions.amount_in_stable if self.emissions else 0
        reward = reward_value * day_seconds
        staked_pct = (
            100 * self.gauge_total_supply / self.total_supply
            if self.total_supply != 0
            else 0
        )
        staked_tvl = tvl * staked_pct / 100
        return (reward / staked_tvl) * (100 * 365) if staked_tvl != 0 else 0


@dataclass(frozen=True)
class LiquidityPoolEpoch:
    """Data class for Liquidity Pool

    based on: https://github.com/velodrome-finance/sugar/blob/v2/contracts/LpSugar.vy#L69
    """

    pool_address: str
    bribes: List[Amount]
    fees: List[Amount]

    @classmethod
    @cache_in_seconds(SUGAR_LPS_CACHE_MINUTES * 60)
    async def fetch_latest(cls):
        tokens = await Token.get_all_listed_tokens()
        prices = await Price.get_prices(tokens)

        prices = {price.token.token_address: price for price in prices}
        tokens = {t.token_address: t for t in tokens}

        sugar = w3.eth.contract(address=LP_SUGAR_ADDRESS, abi=LP_SUGAR_ABI)
        pool_epochs = await sugar.functions.epochsLatest(
            GOOD_ENOUGH_PAGINATION_LIMIT, 0
        ).call()

        result = []

        for pe in pool_epochs:
            pool_address, bribes, fees = pe[1], pe[4], pe[5]

            bribes = list(
                filter(
                    lambda b: b is not None,
                    map(lambda b: Amount.build(b[0], b[1], tokens, prices), bribes),
                )
            )
            fees = list(
                filter(
                    lambda f: f is not None,
                    map(lambda f: Amount.build(f[0], f[1], tokens, prices), fees),
                )
            )

            result.append(
                LiquidityPoolEpoch(pool_address=pool_address, bribes=bribes, fees=fees)
            )

        return result

    @classmethod
    async def fetch_for_pool(cls, pool_address: str) -> "LiquidityPoolEpoch":
        pool_epochs = await cls.fetch_latest()
        try:
            a = normalize_address(pool_address)
            return next(pe for pe in pool_epochs if pe.pool_address == a)
        except Exception:
            return None

    @property
    def total_fees(self) -> float:
        return sum(map(lambda fee: fee.amount_in_stable, self.fees))

    @property
    def total_bribes(self) -> float:
        return sum(map(lambda bribe: bribe.amount_in_stable, self.bribes))
