from typing import TYPE_CHECKING

import discord
import logging
from discord import app_commands

from ballsdex.core.bot import BallsDexBot
from ballsdex.core.utils.logging import log_action
from ballsdex.core.models import Economy as EconomyModel
from ballsdex.core.utils.transformers import EconomyTransform
from ballsdex.settings import settings
from .balls import save_file
from tortoise.exceptions import BaseORMException

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.admin.economies")

class Economy(app_commands.Group):
    """
    Economies management
    """

    @app_commands.command(name="create")
    async def economy_create(
        self,
        interaction: discord.Interaction[BallsDexBot],
        name: app_commands.Range[str, None, 64],
        icon: discord.Attachment
    ):
        """
        Crea una nueva economía.

        Parameters
        ----------
        name: str
            Nombre de la nueva economía
        icon: discord.Attachment
            Imagen de la nueva economía.
        """
        try:
            icon_path = await save_file(icon)
        except Exception as e:
            log.exception("Failed saving file when creating economy", exc_info=True)
            await interaction.followup.send(
                f"Failed saving the attached file: {icon.url}.\n"
                f"Partial error: {', '.join(str(x) for x in e.args)}\n"
                "The full error is in the bot logs."
            )
            return
        
        try:
            economy = await EconomyModel.create(name=name, icon="/" + str(icon_path))
        except BaseORMException as e:
            log.exception("Failed creating regime with admin command", exc_info=True)
            await interaction.followup.send(
                f"Failed creating the regime.\n"
                f"Partial error: {', '.join(str(x) for x in e.args)}\n"
                "The full error is in the bot logs."
            )
        else:
            file = await icon.to_file()
            await interaction.client.load_cache()
            admin_url = (
                f"[View online](<{settings.admin_url}/bd_models/economy/{economy.pk}/change/>)\n"
                if settings.admin_url
                else ""
            )
            await log_action(
                f"{interaction.user} creó la economía {economy.name}",
                interaction.client
            )

            await interaction.followup.send(
                f"Successfully created a economy with ID {economy.pk}! "
                f"The internal cache was reloaded.\n{admin_url}"
                f"{name=}",
                file=file,
                ephemeral=True
            )
    
    @app_commands.command(name="edit")
    async def economy_edit(
        self,
        interaction: discord.Interaction[BallsDexBot],
        economy: EconomyTransform,
        name: app_commands.Range[str, None, 64] | None = None,
        icon: discord.Attachment | None = None
    ):
        """
        Edita una economía.

        Parameters
        ----------
        economy: Economy
            Economía a editar.
        name: str
            Nuevo nombre de la economía.
        icon: discord.Attachment
            Nueva imagen de la economía.
        """
        if icon:
            try:
                icon_path = await save_file(icon)
            except Exception as e:
                log.exception("Failed saving file when creating economy", exc_info=True)
                await interaction.followup.send(
                    f"Failed saving the attached file: {icon.url}.\n"
                    f"Partial error: {', '.join(str(x) for x in e.args)}\n"
                    "The full error is in the bot logs."
                )
                return
        
        if name:
            economy.name = name
            await economy.save()
        
        if economy:
            economy.icon = "/" + str(icon_path) # type: ignore
            await economy.save()

        files = []
        
        if icon:
            files.append(await icon.to_file())

        await log_action(
            f"{interaction.user} actualizó la economía {economy.name}",
            interaction.client
        )

        return await interaction.response.send_message(
            f"Se actualizó la economía {economy.name}",
            files=files,
            ephemeral=True
        )