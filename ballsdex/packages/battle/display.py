import discord
from ballsdex.packages.battle.team import BattleTeam
from ballsdex.packages.battle.ball import BattleBall
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

def _get_prefix_emote(team: BattleTeam) -> str:
    if team.cancelled:
        return "\N{NO ENTRY SIGN}"
    elif team.accepted:
        return "\N{WHITE HEAVY CHECK MARK}" # no hay lock xd
    else:
        return ""

def _build_list_of_strings(
    team: BattleTeam, bot: "BallsDexBot", short: bool = False
) -> list[str]:
    # this builds a list of strings always lower than 1024 characters
    # while not cutting in the middle of a line
    proposal: list[str] = [""]
    i = 0
    
    for countryball in team.proposal:
        cb_text = countryball.ball.description(short=short, include_emoji=True, bot=bot, is_trade=True)
        if not team.cancelled:
            text = f"- {cb_text}\n"
        else:
            text = f"~~{cb_text}~~\n"

        if len(text) + len(proposal[i]) > 950:
            # move to a new list element
            i += 1
            proposal.append("")
        proposal[i] += text

    if not proposal[0]:
        proposal[0] = "*Empty*"

    return proposal


def fill_battle_embed_fields(
    embed: discord.Embed,
    bot: "BallsDexBot",
    team1: BattleTeam,
    team2: BattleTeam,
    compact: bool = False,
):
    """
    Fill the fields of an embed with the items part of a trade.

    This handles embed limits and will shorten the content if needed.

    Parameters
    ----------
    embed: discord.Embed
        The embed being updated. Its fields are cleared.
    bot: BallsDexBot
        The bot object, used for getting emojis.
    team1: BattleTeam
        The player that initiated the trade, displayed on the left side.
    team2: BattleTeam
        The player that was invited to trade, displayed on the right side.
    compact: bool
        If `True`, display countryballs in a compact way. This should not be used directly.
    """
    embed.clear_fields()

    # first, build embed strings
    # to play around the limit of 1024 characters per field, we'll be using multiple fields
    # these vars are list of fields, being a list of lines to include
    team1_proposal = _build_list_of_strings(team1, bot, compact) # trucos del goat 🐐 🤑
    team2_proposal = _build_list_of_strings(team2, bot, compact)

    # then display the text. first page is easy
    embed.add_field(
        name=f"{_get_prefix_emote(team1)} {team1.leader.name}",
        value=team1_proposal[0],
        inline=True,
    )
    embed.add_field(
        name=f"{_get_prefix_emote(team2)} {team2.leader.name}",
        value=team2_proposal[0],
        inline=True,
    )

    if len(team1_proposal) > 1 or len(team2_proposal) > 1:
        # we'll have to trick for displaying the other pages
        # fields have to stack themselves vertically
        # to do this, we add a 3rd empty field on each line (since 3 fields per line)
        i = 1
        while i < len(team1_proposal) or i < len(team2_proposal):
            embed.add_field(name="\u200B", value="\u200B", inline=True)  # empty

            if i < len(team1_proposal):
                embed.add_field(name="\u200B", value=team1_proposal[i], inline=True)
            else:
                embed.add_field(name="\u200B", value="\u200B", inline=True)

            if i < len(team2_proposal):
                embed.add_field(name="\u200B", value=team2_proposal[i], inline=True)
            else:
                embed.add_field(name="\u200B", value="\u200B", inline=True)
            i += 1

        # always add an empty field at the end, otherwise the alignment is off
        embed.add_field(name="\u200B", value="\u200B", inline=True)

    if len(embed) > 6000:
        if not compact:
            return fill_battle_embed_fields(embed, bot, team1, team2, compact=True)
        else:
            embed.clear_fields()
            embed.add_field(
                name=f"{_get_prefix_emote(team1)} {team1.leader.name}",
                value=f"Trade too long, only showing last page:\n{team1_proposal[-1]}",
                inline=True,
            )
            embed.add_field(
                name=f"{_get_prefix_emote(team2)} {team2.leader.name}",
                value=f"Trade too long, only showing last page:\n{team2_proposal[-1]}",
                inline=True,
            )

            
