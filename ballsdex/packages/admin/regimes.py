from typing import TYPE_CHECKING

import discord
import logging
from discord import app_commands

from ballsdex.core.bot import BallsDexBot
from ballsdex.core.utils.logging import log_action
from ballsdex.core.models import Regime as RegimeModel
from ballsdex.core.utils.transformers import RegimeTransform
from ballsdex.settings import settings
from .balls import save_file
from tortoise.exceptions import BaseORMException

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.admin.regimes")

class Regime(app_commands.Group):
    """
    Regimes management
    """

    @app_commands.command(name="create")
    async def regime_create(
        self,
        interaction: discord.Interaction[BallsDexBot],
        name: app_commands.Range[str, None, 64],
        background: discord.Attachment
    ):
        """
        Crea un nuevo regimen.

        Parameters
        ----------
        name: str
            Nombre del nuevo regimen
        background: discord.Attachment
            Imagen del nuevo regimen.
        """
        try:
            background_path = await save_file(background)
        except Exception as e:
            log.exception("Failed saving file when creating regime", exc_info=True)
            await interaction.followup.send(
                f"Failed saving the attached file: {background.url}.\n"
                f"Partial error: {', '.join(str(x) for x in e.args)}\n"
                "The full error is in the bot logs."
            )
            return
        
        try:
            regime = await RegimeModel.create(name=name, background="/" + str(background_path))
        except BaseORMException as e:
            log.exception("Failed creating regime with admin command", exc_info=True)
            await interaction.followup.send(
                f"Failed creating the regime.\n"
                f"Partial error: {', '.join(str(x) for x in e.args)}\n"
                "The full error is in the bot logs."
            )
        else:
            file = await background.to_file()
            await interaction.client.load_cache()
            admin_url = (
                f"[View online](<{settings.admin_url}/bd_models/regime/{regime.pk}/change/>)\n"
                if settings.admin_url
                else ""
            )
            await log_action(
                f"{interaction.user} creó el regimen {regime.name}",
                interaction.client
            )

            await interaction.followup.send(
                f"Successfully created a regime with ID {regime.pk}! "
                f"The internal cache was reloaded.\n{admin_url}"
                f"{name=}",
                file=file,
                ephemeral=True
            )
    
    @app_commands.command(name="edit")
    async def regime_edit(
        self,
        interaction: discord.Interaction[BallsDexBot],
        regime: RegimeTransform,
        name: app_commands.Range[str, None, 64] | None = None,
        background: discord.Attachment | None = None
    ):
        """
        Edita un regimen.

        Parameters
        ----------
        regime: Regime
            Regimen a editar.
        name: str
            Nuevo nombre del regimen.
        background: discord.Attachment
            Nueva imagen del regimen.
        """
        if background:
            try:
                background_path = await save_file(background)
            except Exception as e:
                log.exception("Failed saving file when creating regime", exc_info=True)
                await interaction.followup.send(
                    f"Failed saving the attached file: {background.url}.\n"
                    f"Partial error: {', '.join(str(x) for x in e.args)}\n"
                    "The full error is in the bot logs."
                )
                return
        
        if name:
            regime.name = name
            await regime.save()
        
        if background:
            regime.background = "/" + str(background_path) # type: ignore
            await regime.save()

        files = []
        
        if background:
            files.append(await background.to_file())

        await log_action(
            f"{interaction.user} actualizó el regimen {regime.name}",
            interaction.client
        )

        return await interaction.response.send_message(
            f"Se actualizó el regimen {regime.name}",
            files=files,
            ephemeral=True
        )