"""`/pod-guide` — the pinned Pod Draft walkthrough, sourced from bot/pod-draft-guide.md."""
from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from bot import audit, emojis
from bot.commands import descriptions as desc
from bot.services.pod_schedule import POD_DRAFTERS_ROLE_NAME

log = logging.getLogger(__name__)

GUIDE_PATH = Path(__file__).resolve().parents[1] / "pod-draft-guide.md"
GUIDE_MARKER = "Pod Draft Guide"


def render_pod_guide(pod_drafters_mention: str) -> str:
    text = GUIDE_PATH.read_text(encoding="utf-8").strip()
    return text.replace(":mtga:", emojis.get("mtga")).replace(f"@{POD_DRAFTERS_ROLE_NAME}", pod_drafters_mention)


class PodGuide(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="pod-guide", description=desc.POD_GUIDE)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_guide(self, interaction: discord.Interaction) -> None:
        body = render_pod_guide(self._resolve_pod_drafters_mention(interaction.guild))
        is_owner = await self.bot.is_owner(interaction.user)
        audit.event("pod_guide_invoked", user_id=str(interaction.user.id), pinned=is_owner)
        no_pings = discord.AllowedMentions.none()
        if is_owner:
            await self._remove_existing_pins(interaction.channel)
            await interaction.response.send_message(body, allowed_mentions=no_pings)
            message = await interaction.original_response()
            await self._pin(message)
            await self._react_love(message)
        else:
            await interaction.response.send_message(
                body, allowed_mentions=no_pings, ephemeral=(interaction.guild is not None)
            )

    def _resolve_pod_drafters_mention(self, guild: discord.Guild | None) -> str:
        role = discord.utils.get(guild.roles, name=POD_DRAFTERS_ROLE_NAME) if guild is not None else None
        if role is None:
            for candidate_guild in self.bot.guilds:
                role = discord.utils.get(candidate_guild.roles, name=POD_DRAFTERS_ROLE_NAME)
                if role is not None:
                    break
        return role.mention if role is not None else f"@{POD_DRAFTERS_ROLE_NAME}"

    async def _pin(self, message: discord.Message) -> None:
        try:
            await message.pin()
        except discord.HTTPException:
            log.warning("could not pin the pod guide", exc_info=True)

    async def _react_love(self, message: discord.Message) -> None:
        love = emojis.get_emoji("chordo_love")
        if love is None:
            return
        try:
            await message.add_reaction(love)
        except discord.HTTPException:
            log.warning("could not react to the pod guide", exc_info=True)

    async def _remove_existing_pins(self, channel: discord.abc.Messageable | None) -> None:
        if channel is None:
            return
        try:
            pins = await channel.pins()
        except discord.HTTPException:
            log.warning("could not read pins while refreshing the pod guide", exc_info=True)
            return
        for message in pins:
            if message.author == self.bot.user and GUIDE_MARKER in message.content:
                try:
                    await message.delete()
                except discord.HTTPException:
                    log.warning("could not remove a stale pod guide pin", exc_info=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PodGuide(bot))
