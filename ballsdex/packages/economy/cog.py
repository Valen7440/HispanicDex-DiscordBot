import random
from typing import TYPE_CHECKING, List, cast
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import format_dt

from ballsdex.settings import settings
from ballsdex.packages.countryballs.countryball import BallSpawnView
from ballsdex.core.models import (
    Ball,
    BallInstance,
    GuildConfig, 
    ItemsInstance, 
    ItemsBD,
    Special,
    Player
)
from tortoise.timezone import now as datetime_now

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

@app_commands.guild_only()
class Economy(commands.GroupCog):
    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    @app_commands.command()
    async def claim(self, interaction: discord.Interaction["BallsDexBot"]):
        """
        Reclama monedas diarias.
        """
        await interaction.response.defer(thinking=True, ephemeral=True)
        player, _ = await Player.get_or_create(discord_id=interaction.user.id)

        if await player.is_cooldowned():
            return await interaction.followup.send(
                "Todavía no es momento para reclamar.\n"
                f"Termina {format_dt(player.cooldown + timedelta(days=1), "R")}" # type: ignore
            )

        await player.set_cooldown()
        await player.add_money(50)

        return await interaction.followup.send(
            f"¡Has reclamado **50** fichas diarias! "
            f"Vuelve {format_dt(player.cooldown + timedelta(days=1), "R")} para reclamar monedas diarias." # type: ignore
        )

    @app_commands.command()
    async def shop(self, interaction: discord.Interaction["BallsDexBot"]):
        """
        Accede a la tienda de objetos de BallsDex.
        """
        await interaction.response.defer(thinking=True)
        guild = cast(discord.Guild, interaction.guild)

        config, _ = await GuildConfig.get_or_create(guild_id=guild.id)

        await config.fetch_related("items")

        embed = discord.Embed(title=f"Tienda de Objetos de {settings.bot_name}", color=discord.Color.red())

        if config.update_items and config.update_items < datetime_now() or len(config.items) <= 0:
            await create_items(config)

        async for item in config.items.all():
            await item.fetch_related("ball", "special")
            if item.emoji_id:
                emoji, special_emoji = (self.bot.get_emoji(int(item.emoji_id)) or '', "")
            else:
                emoji = self.bot.get_emoji(int(item.ball.emoji_id)) if item.ball and item.ball.emoji_id else ''
                special_emoji = item.special.emoji if item.special else ''

            embed.add_field(
                name=f"{special_emoji} {emoji} {item.name}",
                value=f"{item.value} monedas"
            )
    
        embed.set_footer(text="Créditos a BornarkiaDex (._themagicalflame_.; su creador) por la idea original.")
        
        return await interaction.followup.send(embed=embed)
    
    async def autocomplete_buy_items(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        current: str
    ) -> List[app_commands.Choice[str]]:
        config, _ = await GuildConfig.get_or_create(guild_id=interaction.guild_id)
        await config.fetch_related("items")

        items = await config.items.all()

        return [
            app_commands.Choice(name=f"{item.name} ({item.value})", value=str(item.pk)) 
            for item in items
            if current.lower() in item.name.lower()
        ][:25]

    @app_commands.command(name="buy")
    @app_commands.autocomplete(item=autocomplete_buy_items)
    async def buy(self, interaction: discord.Interaction, item: str):
        """
        Compra un item de la tienda de objetos.

        Parameters
        ----------
        item: app_commands.Choice[str]
            Objeto a comprar.
        """
        await interaction.response.defer(thinking=True, ephemeral=True)

        config, _ = await GuildConfig.get_or_create(guild_id=interaction.guild_id)
        player, _ = await Player.get_or_create(discord_id=interaction.user.id)

        await config.fetch_related("items")

        get_item = await ItemsBD.get_or_none(pk=int(item))
        if get_item is None or get_item not in config.items:
            return await interaction.followup.send(f"No se ha encontrado a ese item.")

        if not player.can_afford(get_item.value):
            return await interaction.followup.send(
                "No puedes pagar este item.\n"
                f"Se necesitán **{get_item.value - player.money}** fichas para poder pagar el item."
            )
        
        await get_item.fetch_related("ball", "special")

        if get_item.ball is None and get_item.special is None:
            await player.remove_money(get_item.value)
            instance = await ItemsInstance.create(player=player, item=get_item)

            return await interaction.followup.send(f"Se ha añadido a tu inventario el item **{instance.item.name}**.")
        else:
            await player.remove_money(get_item.value)

            ball: Ball | None = get_item.ball
            special: Special | None = get_item.special

            if ball is None:
                cb = await BallSpawnView.get_random(self.bot)
                ball = cb.model

            bonus_attack = random.randint(-settings.max_attack_bonus, settings.max_attack_bonus)
            bonus_health = random.randint(-settings.max_health_bonus, settings.max_health_bonus)

            instance = await BallInstance.create(
                player=player,
                ball=ball,
                special=special,
                attack_bonus=bonus_attack,
                health_bonus=bonus_health,
            )

            cb_txt = (
                instance.description(short=True, include_emoji=True, bot=self.bot)
                + f" (`{instance.attack_bonus:+}%/{instance.health_bonus:+}%`)"
            )

            return await interaction.followup.send(f"¡Has conseguido a {cb_txt} por **{get_item.value}** fichas!")

    @app_commands.command()
    async def items(self, interaction: discord.Interaction["BallsDexBot"]):
        """
        Revisa tu inventario de items.
        """
        await interaction.response.defer(thinking=True, ephemeral=True)
        player, _ = await Player.get_or_create(discord_id=interaction.user.id)
        
        await player.fetch_related("items")
        
        items = await player.items.all().prefetch_related("item")
        
        if len(items) <= 0:
            return await interaction.followup.send(f'Actualmente, tienes **0** items.', ephemeral=True)
        
        embed = discord.Embed(title=f"Items de {interaction.user.display_name}", color=discord.Color.blurple())
        embed.description = f"Tienes **{player.money}** monedas."

        i = 0
        for item in items:
            embed.add_field(name=f"Item #{i + 1}", value=item.item.name)
            i += 1

        if interaction.user.avatar:
            embed.set_thumbnail(url=interaction.user.avatar.url)

        return await interaction.followup.send(embed=embed)

async def create_items(config: GuildConfig, length: int = 6) -> None:
    if config.update_items is None or config.update_items < datetime_now():
        date = datetime.now()
        tuesday = (1 - date.weekday()) % 7
        update = date + timedelta(days=tuesday)
        config.update_items = update.replace(hour=18, minute=0, second=0, microsecond=0)
        await config.items.clear()
        await config.save()

    db_items = await ItemsBD.all()
    num_items = min(length, len(db_items))

    items = random.sample(db_items, k=num_items)
    
    for item in items:
        await config.items.add(item)
    await config.save()