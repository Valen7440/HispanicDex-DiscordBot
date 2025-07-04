from typing import TYPE_CHECKING

from ballsdex.packages.economy.cog import Economy

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


async def setup(bot: "BallsDexBot"):
    await bot.add_cog(Economy(bot))
