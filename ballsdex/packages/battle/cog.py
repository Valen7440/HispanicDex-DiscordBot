import datetime
from collections import defaultdict
from typing import TYPE_CHECKING, Optional, cast

import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import MISSING
from tortoise.expressions import Q

from ballsdex.core.utils.transformers import (
    BallInstanceTransform
)

from ballsdex.core.models import Player
from ballsdex.core.utils.buttons import ConfirmChoiceView
from ballsdex.packages.battle.game import BattleGame
from ballsdex.packages.battle.display import BattleTeam
from ballsdex.packages.battle.ball import BattleBall
from ballsdex.settings import settings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

class Battle(commands.GroupCog):
    """
    Fight and win battles!
    """

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
        self.battles: dict[int, dict[int, list[BattleGame]]] = defaultdict(lambda: defaultdict(list))
        self.amount = int

    def get_battle(
        self,
        interaction: discord.Interaction | None = None,
        *,
        channel: discord.TextChannel | None = None,
        user: discord.User | discord.Member = MISSING,
    ) -> tuple[BattleGame, BattleTeam] | tuple[None, None]:
        guild: discord.Guild
        if interaction:
            guild = cast(discord.Guild, interaction.guild)
            channel = cast(discord.TextChannel, interaction.channel)
            user = interaction.user
        elif channel:
            guild = channel.guild
        else:
            raise TypeError("Missing interaction or channel")

        if guild.id not in self.battles:
            return (None, None)
        if channel.id not in self.battles[guild.id]:
            return (None, None)
        
        to_remove: list[BattleGame] = []

        battle: BattleGame
        for battle in self.battles[guild.id][channel.id]:
            if (
                battle.finished
                or battle.team1.cancelled
                or battle.team2.cancelled
            ):
                # remove what was supposed to have been removed
                to_remove.append(battle)
                continue
            try:
                team = battle._get_team(user)
            except RuntimeError:
                continue
            else:
                break
        else:
            for battle in to_remove:
                self.battles[guild.id][channel.id].remove(battle)
            return (None, None)

        for battle in to_remove:
            self.battles[guild.id][channel.id].remove(battle)
        return (battle, team)
    
    @app_commands.command(name="about", description="Obten informacion sobre las batallas")
    async def about(self, interaction: discord.Interaction["BallsDexBot"]):
        cog = Battle
        start_command = cog.start.extras.get("mention", "`/battle start`")

        embed = discord.Embed(
            title=f"Información sobre {settings.bot_name} Battle 2.0 (BETA)",
            color=discord.Color.blue()
        )
        embed.description = (
            f":crossed_swords: **¡Bienvenido a las batallas de {settings.collectible_name}!** :crossed_swords:\n"
            "¡Demuestra quien tiene el mejor equipo en estas batallas reinventadas!\n\n"
            "**¿Como se juega?**\n"
            f"- Primero empieza una batalla con el comando ({start_command}) y añade {settings.collectible_name}s a tu equipo, cuando estén listos, presionen el boton verde.\n"
            "- Cuando ambos usuarios acepten, se tirará el dado, si cae par, tu empiezas, sino el equipo oponente.\n"
            f"- Cuando sea tu turno, decide que hara el primer {settings.collectible_name} de tu equipo.\n"
            "- Gana el equipo que quede en pie."
        )
        embed.set_footer(text="Programado por PwL y Valen.") 

        return await interaction.response.send_message(embed=embed)

    @app_commands.command(name="start", description="Empieza una batalla")
    @app_commands.describe(user="Usuario para batallas", amount=f"Establece cantidad de {settings.collectible_name}s para comenzar la partida.", duplicates=f"Se permitirán {settings.collectible_name}s del mismo tipo")
    async def start(self, interaction: discord.Interaction["BallsDexBot"], user: discord.User, amount: app_commands.Range[int, 1, 30] | None, duplicates: bool | None):
        if user.bot:
            return await interaction.response.send_message(
                content="No puedes batallar con bots",
                ephemeral=True
            )

        if user.id == interaction.user.id:
            return await interaction.response.send_message(
                content="No puedes batallar contigo mismo.",
                ephemeral=True
            )

        battle1, team1 = self.get_battle(interaction)
        battle2, team2 = self.get_battle(channel=interaction.channel, user=user)  # type: ignore
        if battle1 or team1:
            await interaction.response.send_message(
                "Ya tienes una batalla en curso.", ephemeral=True
            )
            return
        if battle2 or team2:
            await interaction.response.send_message(
                "El usuario con el que intentas pelear ya esta en una batalla.", ephemeral=True
            )
            return

        player1, _ = await Player.get_or_create(discord_id=interaction.user.id)
        player2, _ = await Player.get_or_create(discord_id=user.id)
        if player2.discord_id in self.bot.blacklist:
            await interaction.response.send_message(
                "No puedes batallar con un usuario blacklisteado.", ephemeral=True
            )
            return

        game = BattleGame(self, interaction, BattleTeam(interaction.user, player1), BattleTeam(user, player2), amount, duplicates)
        self.battles[interaction.guild.id][interaction.channel.id].append(game)
        await game.start()

        return await interaction.response.send_message(content="¡La batalla ha comenzado!", ephemeral=True)

    @app_commands.command(name="add", description=f"Añade un {settings.collectible_name} a tu equipo.")
    @app_commands.describe(countryball=f"{settings.collectible_name.capitalize()} a añadir.")
    @app_commands.rename(countryball=settings.collectible_name)
    async def add(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        countryball: BallInstanceTransform,
    ):
        if not countryball:
            return
        
        await interaction.response.defer(ephemeral=True, thinking=True)

        battle, team = self.get_battle(interaction)
        if not battle or not team:
            await interaction.followup.send("No tienes una batalla en curso.", ephemeral=True)
            return

        if team.accepted:
            await interaction.followup.send(
                f"Ya aceptaste la batalla, no puede ser cambiada.", ephemeral=True
            )
            return

        if battle.amount: # para, falto algo
            if len(team.proposal) >= battle.amount: # si es aqui 
                await interaction.followup.send(
                    f"You can't add more than **{battle.amount}** {settings.collectible_name}s.", ephemeral=True
                )
                return

        ball = BattleBall(countryball)

        for added in team.proposal:
            if ball.id == added.id:
                await interaction.followup.send(
                    f"Ya tienes este {settings.collectible_name} en tu equipo.",
                    ephemeral=True,
                )
                return 

            if not battle.duplicates and added.countryball.country == countryball.countryball.country:
                await interaction.followup.send(    
                    f"No puedes añadir {settings.collectible_name}s del mismo tipo, en esta batalla no están permitidos.",
                    ephemeral=True,
                )
                return 
        
        team.proposal.append(ball)
        await interaction.followup.send(
            f"{countryball.countryball.country} añadido.", ephemeral=True
        )

    @app_commands.command(name="remove", description=f"Quita un {settings.collectible_name} de tu equipo.")
    @app_commands.describe(countryball=f"{settings.collectible_name.capitalize()} a remover.") 
    @app_commands.rename(countryball=settings.collectible_name)
    async def remove(
        self,
        interaction: discord.Interaction,
        countryball: BallInstanceTransform,
    ):
        if not countryball:
            return

        battle, team = self.get_battle(interaction)
        if not battle or not team:
            await interaction.response.send_message(
                "No tienes una batalla en curso.", ephemeral=True
            )
            return
        
        if team.accepted:
            await interaction.response.send_message(
                f"Ya aceptaste la batalla, no puede ser cambiada.", ephemeral=True
            )
            return

        ball = BattleBall(countryball)

        if ball not in team.proposal:
            await interaction.response.send_message(
                f"Ese {settings.collectible_name} no esta en tu equipo.", ephemeral=True
            )
            return
        
        team.proposal.remove(ball)
        await interaction.response.send_message(
            f"{countryball.countryball.country} removido.", ephemeral=True
        )

    @app_commands.command(name="surrender", description=f"Rindete en una batalla.")
    async def surrender(self, interaction: discord.Interaction["BallsDexBot"]):
        battle, team = self.get_battle(interaction)
        if not battle or not team:
            await interaction.response.send_message(
                "No tienes una batalla en curso.", ephemeral=True
            )
            return
        
        if not team.accepted and not battle.current_view.is_finished():
            await interaction.response.send_message(
                f"Esta batalla aun no comienza.", ephemeral=True
            )
            return
        
        view = ConfirmChoiceView(interaction)
        await interaction.response.send_message(
            content="¿Seguro que deseas rendirte?",
            view=view,
            ephemeral=True
        )
        await view.wait()
        if not view.value:
            return
        
        battle.finished = True

        if battle.team1.leader.id == interaction.user.id:
            winner = battle.team2
        elif battle.team2.leader.id == interaction.user.id:
            winner = battle.team1

        win_embed = discord.Embed(color=discord.Colour.gold(), title=f"Ganador de la batalla")
        win_embed.description = (
            f"{interaction.user.display_name} se ha rendido.\n\n"
            f"El ganador de esta batalla es...\n"
            f"**¡{winner.leader.display_name}!**"
        )

        await interaction.channel.send(embed=win_embed)