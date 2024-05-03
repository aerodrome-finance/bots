import pytest

from dotenv import load_dotenv

load_dotenv(".env.example")

from bots.settings import TOKEN_ADDRESS  # noqa
from bots.data import Token, Price, LiquidityPool, LiquidityPoolEpoch  # noqa


@pytest.mark.asyncio
async def test_get_by_token_address():
    t = await Token.get_by_token_address(TOKEN_ADDRESS)
    assert t.token_address == TOKEN_ADDRESS
    assert t.listed is True


@pytest.mark.asyncio
async def test_get_prices():
    prices = await Price.get_prices([await Token.get_by_token_address(TOKEN_ADDRESS)])
    assert len(prices) == 1
    [price] = prices
    assert price.pretty_price != 0


@pytest.mark.asyncio
async def test_tvl():
    pools = await LiquidityPool.get_pools()
    tvl = await LiquidityPool.tvl(pools)
    assert tvl != 0


@pytest.mark.asyncio
async def test_fees():
    pools = await LiquidityPool.get_pools()
    fees = sum(map(lambda p: p.total_fees, pools))
    assert fees != 0


@pytest.mark.asyncio
async def test_rewards():
    lpes = await LiquidityPoolEpoch.fetch_latest()
    fees = sum(map(lambda lpe: lpe.total_fees, lpes))
    bribes = sum(map(lambda lpe: lpe.total_bribes, lpes))

    assert fees != 0
    assert bribes != 0


@pytest.mark.asyncio
async def test_liquidity_pool_stats():
    pools = await LiquidityPool.get_pools()
    for pool in pools:
        tvl = await LiquidityPool.tvl([pool])
        fields = [
            # XX: these can be None for non listed tokens
            # pool.token0,
            # pool.token1,
            pool.is_stable,
            pool.pool_fee_percentage,
            pool.apr(tvl),
            pool.volume,
            pool.token0_volume,
            pool.token1_volume,
            pool.token0_fees.amount_in_stable if pool.token0_fees else 0,
            pool.token1_fees.amount_in_stable if pool.token1_fees else 0,
            pool.token0_fees.amount if pool.token0_fees else 0,
            pool.token1_fees.amount if pool.token1_fees else 0,
            pool.reserve0.amount if pool.reserve0 else 0,
            pool.reserve1.amount if pool.reserve1 else 0,
        ]
        for field in fields:
            assert field is not None
