from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ballsdex.packages.battle.ball import BattleBall

if TYPE_CHECKING:
    import discord

    from ballsdex.core.bot import BallsDexBot
    from ballsdex.core.models import BallInstance, Player

@dataclass
class BattleTeam:
    leader: "discord.User | discord.Member"
    player: "Player"
    proposal: list["BattleBall"] = field(default_factory=list)
    cancelled: bool = False
    accepted: bool = False 