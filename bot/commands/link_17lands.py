from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import audit
from bot.commands import descriptions as desc
from bot.services.seventeenlands import SeventeenLandsClient
from bot.services.token_link_flow import start_link_17lands_flow

logger = logging.getLogger(__name__)


class Link17Lands(commands.Cog):
    def __init__(self, bot: commands.Bot, client: SeventeenLandsClient | None = None) -> None:
        self.bot = bot
        self.client = client or SeventeenLandsClient()

    @app_commands.command(name="link-17lands", description=desc.LINK_17LANDS)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def link_17lands(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        username = str(interaction.user)
        audit.event("link_17lands_invoked", user_id=user_id, username=username)
        logger.info(f"link-17lands: {username} invoked")
        await start_link_17lands_flow(self.bot, interaction, self.client)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Link17Lands(bot))
