import re
import string
import logging
import random
from typing import Optional
from pathlib import Path
from datetime import datetime

import discord
from discord.utils import format_dt
from discord import app_commands
from tortoise.exceptions import BaseORMException
from tortoise.functions import Count
from tortoise.expressions import F

from ballsdex.core.bot import BallsDexBot
from ballsdex.settings import settings

from ballsdex.core.models import GuildConfig, BallInstance, Special as SpecialModel
from ballsdex.core.utils.logging import log_action
from ballsdex.core.utils.buttons import ConfirmChoiceView
from ballsdex.core.utils.transformers import SpecialTransform
from ballsdex.core.utils.paginator import TextPageSource, Pages

log = logging.getLogger("ballsdex.packages.admin.special")
FILENAME_RE = re.compile(r"^(.+)(\.\S+)$")

async def save_file(attachment: discord.Attachment) -> Path:
    path = Path(f"./admin_panel/media/{attachment.filename}")
    match = FILENAME_RE.match(attachment.filename)
    if not match:
        raise TypeError("The file you uploaded lacks an extension.")
    i = 1
    while path.exists():
        path = Path(f"./admin_panel/media/{match.group(1)}-{i}{match.group(2)}")
        i = i + 1
    await attachment.save(path)
    return path.relative_to("./admin_panel/media/")

def generate_random_name():
    source = string.ascii_uppercase + string.ascii_lowercase + string.ascii_letters
    return "".join(random.choices(source, k=15))

class Special(app_commands.Group):
    """
    Specials management
    """
    
    @app_commands.command(name="create")
    @app_commands.checks.has_any_role(*settings.root_role_ids)
    async def special_create(
        self,
        interaction: discord.Interaction[BallsDexBot],
        name: app_commands.Range[str, None, 64],
        catch_phrase: Optional[app_commands.Range[str, None, 128]],
        start_date: Optional[app_commands.Range[str, None, 10]],
        end_date: Optional[app_commands.Range[str, None, 10]],
        rarity: str,
        background: discord.Attachment,
        emoji: app_commands.Range[str, None, 21] | None = None,
        tradeable: bool = True,
        hidden: bool = False,
        background_credits: app_commands.Range[str, None, 64] | None = None
    ):
        """
        Shortcut command for creating specials. They are disabled by default.

        Parameters
        ----------
        name: str
        catch_phrase: str
        start_date: str
            Start time of the event. If blank, starts immediately"
        end_date: str
            End time of the event. If blank, the event is permanent
        rarity: float
            Value between 0 and 1, chances of using this special background.
        background: discord.Attachment
            1428x2000 PNG image
        emoji: str
            Either a unicode character or a discord emoji ID
        tradeable: bool
        hidden: bool
        background_credits: str
        """
        await interaction.response.defer(thinking=True, ephemeral=True)

        if emoji:
            IS_INTEGER = re.match("^[-+]?[0-9]+$", str(emoji))

            if IS_INTEGER:
                emoji = interaction.client.get_emoji(int(emoji)) # type: ignore
            else:
                emoji = str(emoji)

        try:
            background_path = await save_file(background) if background else None
        except Exception as e:
            log.exception("Failed saving file when creating special", exc_info=True)
            await interaction.followup.send(
                f"Failed saving the attached file: {background.url}.\n"
                f"Partial error: {', '.join(str(x) for x in e.args)}\n"
                "The full error is in the bot logs."
            )
            return
        
        if start_date:
            start_date = datetime.strptime(str(start_date), "%Y-%m-%d").strftime("%Y-%m-%d")

        if end_date:
            end_date = datetime.strptime(str(end_date), "%Y-%m-%d").strftime("%Y-%m-%d")
        
        try:
            special = await SpecialModel.create(
                name=name,
                catch_phrase=catch_phrase,
                start_date=start_date,
                end_date=end_date,
                rarity=rarity,
                background="/" + str(background_path),
                emoji=emoji,
                tradeable=tradeable,
                hidden=hidden,
                credits=background_credits
            )
        except BaseORMException as e:
            log.exception("Failed creating special with admin command", exc_info=True)
            await interaction.followup.send(
                f"Failed creating the special.\n"
                f"Partial error: {', '.join(str(x) for x in e.args)}\n"
                "The full error is in the bot logs."
            )
        else:
            files = [await background.to_file()] if background else []
            await interaction.client.load_cache()
            admin_url = (
                f"[View online](<{settings.admin_url}/bd_models/special/{special.pk}/change/>)\n"
                if settings.admin_url
                else ""
            )
            await interaction.followup.send(
                f"Successfully created a {settings.collectible_name} with ID {special.pk}! "
                f"The internal cache was reloaded.\n{admin_url}"
                f"{name=} catch_phrase={catch_phrase if catch_phrase else None} start_date={start_date if start_date else 'Now'} "
                f"end_date={end_date if end_date else 'Permanent'} rarity={rarity} emoji={emoji if emoji else None} "
                f"{tradeable=} {hidden=} credits={background_credits if background_credits else None}",
                files=files
            )

    @app_commands.command(name="edit")
    @app_commands.checks.has_any_role(*settings.root_role_ids)
    async def special_edit(
        self,
        interaction: discord.Interaction[BallsDexBot],
        special: SpecialTransform,
        name: app_commands.Range[str, None, 64] | None = None,
        catch_phrase: app_commands.Range[str, None, 128] | None = None,
        start_date: app_commands.Range[str, None, 10] | None = None,
        end_date: app_commands.Range[str, None, 10] | None = None,
        rarity: str | None = None,
        background: discord.Attachment | None = None,
        emoji: app_commands.Range[str, None, 21] | None = None,
        tradeable: bool | None = None,
        hidden: bool | None = None,
        background_credits: app_commands.Range[str, None, 64] | None = None
    ):
        """
        Actualiza un evento.

        Parameters
        ----------
        special: Special
        name: str
        catch_phrase: str
        start_date: str
            Start time of the event. If blank, starts immediately"
        end_date: str
            End time of the event. If blank, the event is permanent
        rarity: float
            Value between 0 and 1, chances of using this special background.
        background: discord.Attachment
            1428x2000 PNG image
        emoji: str
            Either a unicode character or a discord emoji ID
        tradeable: bool
        hidden: bool
        background_credits: str
        """
        await interaction.response.defer(thinking=True, ephemeral=True)

        if emoji:
            IS_INTEGER = re.match("^[-+]?[0-9]+$", str(emoji))

            if IS_INTEGER:
                emoji = interaction.client.get_emoji(int(emoji)) # type: ignore
            else:
                emoji = str(emoji)

        if background:
            try:
                background_path = await save_file(background)
            except Exception as e:
                log.exception("Failed saving file when creating special", exc_info=True)
                await interaction.followup.send(
                    f"Failed saving the attached file: {background.url}.\n"
                    f"Partial error: {', '.join(str(x) for x in e.args)}\n"
                    "The full error is in the bot logs."
                )
                return

        # Edit

        if name:
            special.name = name
            await special.save()

        if catch_phrase:
            special.catch_phrase = catch_phrase
            await special.save()
        
        if start_date:
            if isinstance(start_date, str):
                if start_date.lower() == "null" or start_date.lower() == "none":
                    special.start_date = None # type: ignore
                else:
                    start_date = datetime.strptime(str(start_date), "%Y-%m-%d") # type: ignore
                    special.start_date = start_date # type: ignore
            
                await special.save()

        
        if end_date:
            if isinstance(end_date, str):
                if end_date.lower() == "null" or end_date.lower() == "none":
                    special.end_date = None # type: ignore
                else:
                    end_date = datetime.strptime(str(end_date), "%Y-%m-%d") # type: ignore
                    special.end_date = end_date # type: ignore

                await special.save()
        
        if rarity:
            rarity = float(rarity) # type: ignore

            special.rarity = rarity # type: ignore
            await special.save()

        if background:
            special.background = "/" + str(background_path) # type: ignore
            await special.save()

        if emoji:
            special.emoji = emoji
            await special.save()

        if tradeable:
            special.tradeable = tradeable
            await special.save()
        
        if hidden:
            special.hidden = hidden
            await special.save()

        if background_credits:
            special.credits = background_credits
            await special.save()

        files = [await background.to_file()] if background else []
        await interaction.client.load_cache()
        await interaction.followup.send(content=f"Se actualizó a **{special.name}**", files=files, ephemeral=True)

    @app_commands.command(name="delete")
    @app_commands.checks.has_any_role(*settings.root_role_ids)
    async def special_delete(
        self,
        interaction: discord.Interaction[BallsDexBot],
        special: SpecialTransform
    ):
        """
        Delete a Special.

        Parameters
        ----------
        special: Special
            Special to delete.
        """
        await interaction.response.defer(thinking=True, ephemeral=True)

        view = ConfirmChoiceView(
            interaction,
            accept_message="Confirming, deleting the special...",
            cancel_message="Request cancelled"
        )

        await interaction.followup.send(
            content=f"Are you sure you want to delete **{special.name}**?",
            view=view,
            ephemeral=True
        )

        await view.wait()

        if not view.value:
            return
        
        name = special.name
        
        await special.delete()
        
        await interaction.followup.send(content=f"{name} was successfully deleted.", ephemeral=True)

        await interaction.client.load_cache()
        
        await log_action(
            f"{interaction.user} deleted special {name}",
            interaction.client,
        )

    @app_commands.command(name="info_ball")
    @app_commands.checks.has_any_role(*settings.root_role_ids)
    async def special_info_ball(
        self,
        interaction: discord.Interaction[BallsDexBot],
        special: SpecialTransform
    ):
        """
        Mira todas las balls que tienen cierta special.

        Parameters
        ----------
        special: Special
            ...
        """
        text = ""
        results = (
            await BallInstance.filter(special=special)
            .annotate(count=Count("id"), country=F("ball__country"))
            .group_by("country")
            .order_by("-count")
            .values("count", "country")
        )

        for i, instance in enumerate(results, start=1):
            text += f"{i}. {instance["country"]} {special.emoji} {special.name} - Count: {instance["count"]}\n"

        source = TextPageSource(text, prefix="```md\n", suffix="```")
        pages = Pages(source=source, interaction=interaction, compact=True)
        pages.remove_item(pages.stop_pages)
        await pages.start(ephemeral=True)


    @app_commands.command(name="info")
    @app_commands.checks.has_any_role(*settings.root_role_ids)
    async def special_info(
        self,
        interaction: discord.Interaction[BallsDexBot],
        special: SpecialTransform
    ):
        """
        Show information about a special.

        Parameters
        ----------
        special: Special
            Special to get information about.
        """
        amount = await BallInstance.filter(special=special).count()

        files = []

        if special.background:
            extension = special.background.split(".")[1]
            file_name = f"nt_{generate_random_name()}.{extension}"

            instance = random.choice(await BallInstance.all().filter(special=special))

            file = discord.File(instance.draw_card(), filename=file_name)

            files.append(file)

        if special.emoji.isnumeric():
            emoji = interaction.client.get_emoji(int(special.emoji)) or ""
        else:
            emoji = special.emoji

        await interaction.response.send_message(
            f"**Name:** {special.name}\n"
            f"**Catch Phrase:** {special.catch_phrase}\n"
            f"**Start Date:** {format_dt(special.start_date, style="f") if special.start_date is not None else 'Now'}\n"
            f"**End Date:** {format_dt(special.end_date, style="f") if special.end_date is not None else 'Never'}\n"
            f"**Rarity:** {special.rarity}\n"
            f"**Emoji:** {emoji}\n"
            f"**Tradeable:** {special.tradeable}\n"
            f"**Hidden:** {special.hidden}\n"
            f"**Credits:** {special.credits}\n"
            f"**Amount:** {amount}",
            files=files
        )