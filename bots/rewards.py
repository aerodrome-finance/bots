from discord.ext import tasks

from .settings import BOT_TICKER_INTERVAL_MINUTES
from .data import LiquidityPoolEpoch
from .helpers import LOGGER, amount_to_string
from .ticker import TickerBot


class RewardsBot(TickerBot):
    """Rewards bot shows rewards, fees and incentives for the latest epoch"""

    def __init__(self, *args, protocol_name: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.protocol_name = protocol_name

    async def on_ready(self):
        LOGGER.debug(f"Logged in as {self.user} (ID: {self.user.id})")
        LOGGER.debug("------")
        await self.update_presence(f"rewards for {self.protocol_name}")

    @tasks.loop(seconds=BOT_TICKER_INTERVAL_MINUTES * 60)
    async def ticker(self):
        try:
            lpes = await LiquidityPoolEpoch.fetch_latest()
            fees = sum(map(lambda lpe: lpe.total_fees, lpes))
            bribes = sum(map(lambda lpe: lpe.total_bribes, lpes))

            await self.update_nick_for_all_servers(
                f"Rewards ~${amount_to_string(fees + bribes)}"
            )
            await self.update_presence(
                f"~${amount_to_string(fees)} + ~${amount_to_string(bribes)} in fees & incentives for voters"  # noqa
            )
        except Exception as ex:
            LOGGER.error(f"Ticker failed with {ex}")
