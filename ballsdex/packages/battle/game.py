from __future__ import annotations

import asyncio
import logging
import datetime
import random
import math
import discord
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from enum import IntEnum

from discord.ui import Button, View, Modal, TextInput

from ballsdex.core.models import BallInstance, Player, Ball
from ballsdex.packages.battle.display import fill_battle_embed_fields
from ballsdex.packages.battle.team import BattleTeam
from ballsdex.packages.battle.ball import BattleBall
from ballsdex.settings import settings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot
    from ballsdex.packages.battle.cog import Battle as BattleCog

log = logging.getLogger("ballsdex.packages.battle.game")

class BattleAction(IntEnum):
    Attack = 0
    Sleep = 1 

class ConfirmView(View):
    def __init__(self, battle: BattleGame):
        super().__init__(timeout=900)
        self.battle = battle

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        try:
            self.battle._get_team(interaction.user)
        except RuntimeError:
            await interaction.response.send_message(
                "No eres parte de esta batalla.", ephemeral=True
            )
            return False
        else:
            return True

    async def on_timeout(self):
        self.stop()
        self.battle.finished = True
        for item in self.children:
            item.disabled = True  # type: ignore
        try:
            await self.interaction.followup.edit_message("@original", view=self)  # type: ignore
        except discord.NotFound:
            pass

    @discord.ui.button(
        style=discord.ButtonStyle.success, emoji="\N{HEAVY CHECK MARK}\N{VARIATION SELECTOR-16}"
    )
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        team = self.battle._get_team(interaction.user)
        if len(team.proposal) < 1:
            await interaction.response.send_message(
                f"Necesitas al menos un {settings.collectible_name} para aceptar la batalla.", ephemeral=True
            )
            return

        if self.battle.amount:
            if len(team.proposal) < self.battle.amount: # si es aqui 
                await interaction.response.send_message(
                    f"Necesitas añadir {self.battle.amount} {settings.collectible_name}s para aceptar la batalla.", ephemeral=True
                )
                return

        if team.accepted:
            await interaction.response.send_message(
                "Ya aceptaste la batalla.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.battle.confirm(team)
        if self.battle.team1.accepted and self.battle.team2.accepted:
            await interaction.followup.send(
                content="Ambos equipos confirmaron, la batalla empezará dentro de poco...",
                ephemeral=True
            )
            await self.battle._start_battle()
        else:   
            await interaction.followup.send(
                content="Aceptaste la batalla, esperando al otro equipo...", ephemeral=True
            )   

    @discord.ui.button(
        style=discord.ButtonStyle.danger,
        emoji="\N{HEAVY MULTIPLICATION X}\N{VARIATION SELECTOR-16}",
    )
    async def deny_button(self, interaction: discord.Interaction, button: Button):
        await self.battle.user_cancel(self.battle._get_team(interaction.user))
        await interaction.response.send_message("Battle has been cancelled.", ephemeral=True)

class FightActionModal(Modal):
    ball = TextInput(
        label=f"{settings.collectible_name.capitalize()} a atacar",
        placeholder=f"Introduce nombre o ID de el {settings.collectible_name}.",
        style=discord.TextStyle.short
    )

    def __init__(self):
        super().__init__(title="Atacar", timeout=600) 
        
    async def on_submit(self, interaction: discord.Interaction):
        self.target = self.ball.value.lower()
        return await interaction.response.defer()

class BattleActionView(View):
    def __init__(self, game: BattleGame, team: BattleTeam):
        super().__init__(timeout=600)
        self.game = game
        self.team = team
        self.interaction = game.interaction 
        self.action: BattleAction | None = None
        self.target: BattleBall | None = None

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.team.leader.id:
            await interaction.response.send_message(
                content="Esta accion no es para ti",
                ephemeral=True
            )
            return False
        if self.game.finished:
            await interaction.response.send_message(
                content="La batalla ha terminado.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        self.game.cancel("No se tomo ninguna accion.")
        for item in self.children:
            item.disabled = True  # type: ignore
        try:
            await self.interaction.followup.edit_message("@original", view=self)  # type: ignore
        except discord.NotFound:
            pass

    def _ack(self):
        for child in self.children:
            child.disabled = True

    @discord.ui.button(
        label="Atacar",
        style=discord.ButtonStyle.primary,
        emoji="⚔"
    )
    async def attack_action(self, interaction: discord.Interaction, button: Button):
        opponent = self.game._get_opponent()

        if len(opponent.proposal) < 2:
            # automatically strike the remaining ball without asking
            self.action = BattleAction.Attack
            self.target = opponent.proposal[0]

            self.stop()
            self._ack()
            return await interaction.response.defer()
    
        modal = FightActionModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        target: BattleBall | None = None
        for ball in opponent.proposal:
            if modal.target.replace("#", "").upper() == f"{ball.id:0X}":
                target = ball
                break

            if modal.target in ball.countryball.country.lower():
                target = ball
                break
    
        if target is None:
            return await interaction.followup.send(
                content="No se encontro ese objetivo.",
                ephemeral=True
            )
        
        self.action = BattleAction.Attack
        self.target = target

        self.stop()
        self._ack()
        await interaction.response.defer()
        
    @discord.ui.button(
        label="Dormir",
        style=discord.ButtonStyle.secondary,
        emoji="💤"
    )
    async def sleep_action(self, interaction: discord.Interaction, button: Button):
        self.action = BattleAction.Sleep

        self.stop()
        self._ack()
        await interaction.response.defer()

class BattleGame:
    def __init__(
        self,
        cog: BattleCog,
        interaction: discord.Interaction,
        team1: BattleTeam,
        team2: BattleTeam,
        amount: int | None,
        duplicates: bool | None
    ):
        self.cog = cog
        self.bot = interaction.client
        self.interaction = interaction
        self.channel = interaction.channel
        self.team1 = team1
        self.team2 = team2
        self.amount = amount
        self.duplicates = duplicates
        self.embed = discord.Embed()
        self.task: asyncio.Task | None = None
        self.current_view: discord.ui.View | None = ConfirmView(self)
        self.current_turn: BattleTeam 
        self.finished = False
        self.message: discord.Message

    def _get_team(self, user: discord.User | discord.Member) -> BattleTeam:
        if user.id == self.team1.leader.id:
            return self.team1
        elif user.id == self.team2.leader  .id:
            return self.team2
        raise RuntimeError(f"User with ID {user.name} ({user.id}) cannot be found in the game.")


    def _get_opponent(self) -> BattleTeam | None:
        if self.current_turn:
            if self.current_turn.leader.id == self.team1.leader.id:
                return self.team2
            elif self.current_turn.leader.id == self.team2.leader.id:
                return self.team1
        else:
            raise RuntimeError("Current turn has not yet been initialized.")
    
    def _generate_embed(self):
        self.embed.title = f"{settings.bot_name} Battle 2.0 (BETA)"
        self.embed.color = discord.Color.blurple()
        self.embed.description = (
            f":crossed_swords: **Bienvenido a la batalla de {settings.collectible_name}s!** :crossed_swords:\n" # es
            f"Añade {settings.collectible_name}s a tu equipo para empezar la pelea!\n"
            f"Controlarás el primer {settings.collectible_name} que agregues a tu equipo.\n"
            f"Cuando termines, confirma, ¡y que empiece la pelea!\n"
        )

        if self.amount is not None:
            self.embed.description += f"- **Cantidad:** {self.amount}\n"

        if self.duplicates is not None:
            self.embed.description += f"- **Duplicates:** {self.duplicates}\n"

        self.embed.set_footer(text="Esta interaccion se actualiza cada 15 segundos, tienes 15 minutos antes de que termine.")

    def _generate_container(self):
        view = discord.ui.LayoutView()

        first_message = discord.ui.TextDisplay(content=f"Hey, {self.team2.leader.mention}, ¡{self.team1.leader.display_name} quiere una pelea contigo!")

        view.add_item(first_message)

        container = discord.ui.Container()

        text = discord.ui.TextDisplay(content=f"# {settings.bot_name} Battle 2.0 (BETA)")
        container.add_item(text)
        separator = discord.ui.Separator()
        container.add_item(separator)
        text2 = discord.ui.TextDisplay(content=(
            f":crossed_swords: **Bienvenido a la batalla de {settings.collectible_name}s!** :crossed_swords:\n" # es
            f"Añade {settings.collectible_name}s a tu equipo para empezar la pelea!\n"
            f"Controlarás el primer {settings.collectible_name} que agregues a tu equipo.\n"
            f"Cuando termines, confirma, ¡y que empiece la pelea!\n"
        ))
        container.add_item(text2)

        if self.amount is not None:
            text3 = discord.ui.TextDisplay(f"- **Cantidad:** {self.amount}")
            container.add_item(text3)

        if self.duplicates is not None:
            text4 = discord.ui.TextDisplay(f"- **Duplicates:** {self.duplicates}")
            container.add_item(text4)
        
        view.add_item(container)

        return view

    async def update_message_loop(self):
        """
        A loop task that updates each 15 second the battle with the new content.
        """

        assert self.task
        start_time = datetime.utcnow()

        while True:
            await asyncio.sleep(15)
            if datetime.utcnow() - start_time > timedelta(minutes=15):
                self.embed.colour = discord.Colour.dark_red()
                await self.cancel("The trade timed out")
                return

            try:
                fill_battle_embed_fields(self.embed, self.bot, self.team1, self.team2)
                await self.message.edit(embed=self.embed)
            except Exception:
                log.exception(
                    "Failed to refresh the battle proposal "
                    f"guild={self.message.guild.id} "  # type: ignore
                    f"trader1={self.team1.user.id} trader2={self.team2.user.id}"
                )
                self.embed.colour = discord.Colour.dark_red()
                await self.cancel("Se acabo el tiempo")
                return
    
    async def start(self):
        view = self._generate_container()
        # fill_battle_embed_fields(self.embed, self.bot, self.team1, self.team2)
        self.message = await self.channel.send(view=view)
        self.task = self.bot.loop.create_task(self.update_message_loop())

    async def cancel(self, reason: str = "Se cancelo la batalla."):
        """
        Cancel the battle immediately.
        """
        if self.task:
            self.task.cancel()

        self.current_view.stop()
        for item in self.current_view.children:
            item.disabled = True  # type: ignore

        fill_battle_embed_fields(self.embed, self.bot, self.team1, self.team2) 
        self.embed.description = f"**{reason}**"
        await self.message.edit(content=None, embed=self.embed, view=self.current_view)

    async def user_cancel(self, team: BattleTeam):
        """
        Register a user request to cancel the battle
        """
        team.cancelled = True
        self.embed.colour = discord.Colour.red()
        await self.cancel(f"{team.leader.display_name} canceló la batalla.")

    async def confirm(self, team: BattleTeam):      
        """
        Mark a user's proposal as accepted. If both user accept, end the trade now

        If the trade is concluded, return True, otherwise if an error occurs, return False
        """
        team.accepted = True
        fill_battle_embed_fields(self.embed, self.bot, self.team1, self.team2)
        if self.team1.accepted and self.team2.accepted:
            if self.task and not self.task.cancelled():
                # shouldn't happen but just in case
                self.task.cancel()

            self.current_view.stop()
            for item in self.current_view.children:
                item.disabled = True  # type: ignore

        await self.message.edit(embed=self.embed, view=self.current_view)  

    def _switch(self):
        if self.current_turn.leader.id == self.team1.leader.id:
            self.current_turn = self.team2
        elif self.current_turn.leader.id == self.team2.leader.id:
            self.current_turn = self.team1
        else:
            raise RuntimeError("Illegal team switch.")

    async def _perform_battle(self):
        async def _attack(ball: BattleBall, target: BattleBall):
            text = target.attack(ball.atk) # prevent infinite loops

            if target.health <= 0:
                opponent = self._get_opponent()

                await self.channel.send(
                    content=(
                        f":skull: ¡**{ball.countryball.country}** (`#{ball.id:0X}`) ha eliminado a **{target.countryball.country}** (`#{target.id:0X}`)!\n"
                    )
                )   
                opponent.proposal.remove(target)
                return
            
            await self.channel.send(
                content=(
                    f":crossed_swords: ¡**{ball.countryball.country}** (`#{ball.id:0X}`) atacó a **{target.countryball.country}** (`#{target.id:0X}`)!\n"
                    f"{text}"
                )
            )

        async def _heal(ball: BattleBall):
            random_health = ball.heal()
            await self.channel.send(
                content=(
                    f"💤 **{ball.countryball.country}** (`#{ball.id:0X}`) durmió.\n"
                    f":heart: Vida: +{random_health} ({ball.health})"
                )
            )

        for i, ball in enumerate(self.current_turn.proposal):
            await asyncio.sleep(5) # wait a bit each turn

            if i == 0:
                action_view = BattleActionView(self, self.current_turn)
                message = await self.channel.send(
                    content=f"{self.current_turn.leader.mention}, ¿que hará **{ball.countryball.country}**?",
                    view=action_view
                )
                await action_view.wait()

                await message.edit(view=action_view)

                if action_view.action == BattleAction.Attack:
                    await _attack(ball, action_view.target)
                elif action_view.action == BattleAction.Sleep:
                    await _heal(ball)
                else:
                    raise RuntimeError("Unknown battle action")
            else:
                # NPC, random actions
                opponent = self._get_opponent()
                action = random.choice(list(BattleAction))

                if len(opponent.proposal) <= 0:
                    continue # skip attack if all balls are dead

                if action == BattleAction.Attack:
                    # only attack alive balls bruh
                    possible_balls = [b for b in opponent.proposal if b.health > 0]
                    # balls with higher health will have more chance to be attacked 
                    balls_weight = [b.health for b in possible_balls]
                    target = random.choices(population=possible_balls, weights=balls_weight, k=1)[0]

                    await _attack(ball, target) 
                elif action == BattleAction.Sleep:
                    await _heal(ball)
                else:
                    raise RuntimeError("Unknown battle action")
                        

    async def _start_battle(self):
        dice_message = await self.message.reply(
            content="🎲 A tirar el dado..."
        )

        await asyncio.sleep(3)
        dice = random.randint(1, 6)

        if dice % 2 == 0:
            # even, allies starts first
            self.current_turn = self.team1
        else:
            # odd, enemy starts first
            self.current_turn = self.team2

        await dice_message.edit(
            content=(
                f"🎲 Cayó un **{dice}**\n"
                f"Cayo {'par' if dice % 2 == 0 else 'impar'}, el equipo de **{self.current_turn.leader.display_name}** inicia la pelea."
            ) 
        )

        await asyncio.sleep(3)

        total1 = len(self.team1.proposal)
        total2 = len(self.team2.proposal)

        while total1 > 0 and total2 > 0:
            # keep on the battle until one team dies
            await self._perform_battle()
            
            # once loop finished, switch turn
            self._switch()

            await asyncio.sleep(5)

            delta1 = len(self.team1.proposal)
            delta2 = len(self.team2.proposal)

            # if delta, send remaining balls
            if delta1 != total1 or delta2 != total2:
                await self.channel.send(
                    content=(
                        f"El equipo de {self.team1.leader.display_name} tiene **{delta1} {settings.collectible_name}s**.\n"
                        f"El equipo de {self.team2.leader.display_name} tiene **{delta2} {settings.collectible_name}s**."
                    )
                )

            total1 = len(self.team1.proposal)
            total2 = len(self.team2.proposal)

        await asyncio.sleep(3)

        if total1 > 0: # .length 🤑
            winner = self.team1
        elif total2 > 0:
            winner = self.team2 # xq ganaria el team1 ? si dice q tiene 0 > 0 mayor que 0 pero está diciendo q el total del team1 es mayor q el team1 xddd
        else:
            # it's a tie!
            return await self.channel.send(content="Wow, eso fue un empate, ambos equipos ganan")

        win_embed = discord.Embed(color=discord.Colour.gold(), title=f"Ganador de la batalla")
        win_embed.description = (
            f"El ganador de esta batalla fue...\n"
            f"**¡{winner.leader.display_name}!**"
        )

        self.finished = True

        return await self.channel.send(embed=win_embed)