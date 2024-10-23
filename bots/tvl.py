from discord.ext import tasks

from .settings import BOT_TICKER_INTERVAL_MINUTES
from .data import LiquidityPool, Token
from .helpers import LOGGER, amount_to_string
from .ticker import TickerBot


class TVLBot(TickerBot):
    """TVL bot shows total value locked across all the pools"""

    def __init__(self, *args, protocol_name: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.protocol_name = protocol_name

    async def on_ready(self):
        LOGGER.debug(f"Logged in as {self.user} (ID: {self.user.id})")
        LOGGER.debug("------")
        await self.update_presence(f"TVL {self.protocol_name}")

    @tasks.loop(seconds=BOT_TICKER_INTERVAL_MINUTES * 60)
    async def ticker(self):
        try:
            pools = await LiquidityPool.get_pools()
            tvl = await LiquidityPool.tvl(pools)
            tokens = await Token.get_all_listed_tokens()
            await self.update_nick_for_all_servers(f"TVL ~${amount_to_string(tvl)}")
            await self.update_presence(f"Based on {len(tokens)} listed tokens")
        except Exception as ex:
            LOGGER.error(f"Ticker failed with {ex}")
