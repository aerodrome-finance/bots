from discord.ext import tasks

from .settings import BOT_TICKER_INTERVAL_MINUTES
from .data import LiquidityPool
from .helpers import LOGGER, amount_to_string
from .ticker import TickerBot


class FeesBot(TickerBot):
    """Fees bot shows total fees accross all the pools"""

    def __init__(self, *args, protocol_name: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.protocol_name = protocol_name

    async def on_ready(self):
        LOGGER.debug(f"Logged in as {self.user} (ID: {self.user.id})")
        LOGGER.debug("------")
        await self.update_presence(f"Watching fees for {self.protocol_name}")

    @tasks.loop(seconds=BOT_TICKER_INTERVAL_MINUTES * 60)
    async def ticker(self):
        try:
            pools = await LiquidityPool.get_pools()
            fees = sum(map(lambda p: p.total_fees, pools))

            await self.update_nick_for_all_servers(f"Fees ~${amount_to_string(fees)}")
            await self.update_presence(f"Based on {len(pools)} pools this epoch")
        except Exception as ex:
            LOGGER.error(f"Ticker failed with {ex}")
