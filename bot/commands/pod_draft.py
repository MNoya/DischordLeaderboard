"""Pod-draft slash commands."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.pod_draft_manager import ACTIVE_POD_MANAGERS


log = logging.getLogger(__name__)


class PodDraft(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ready", description="Run a Draftmancer ready check for this pod draft.")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_ready(self, interaction: discord.Interaction) -> None:
        manager = _find_manager_for_thread(interaction)
        if manager is None:
            await interaction.response.send_message(
                "No active pod draft session right now.",
                ephemeral=True,
            )
            return
        thread = interaction.channel
        await interaction.response.defer(ephemeral=True, thinking=False)
        err = await manager.initiate_ready_check(thread)
        if err is not None:
            await interaction.followup.send(f"⚠️ {err}", ephemeral=True)
        else:
            await interaction.followup.send("Ready check started — watch the thread for status.", ephemeral=True)

    @app_commands.command(name="pod-takeover", description="Take control of the Draftmancer session and disconnect the bot.")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_takeover(self, interaction: discord.Interaction) -> None:
        manager = _find_manager_for_thread(interaction)
        if manager is None:
            await interaction.response.send_message("No active pod draft session right now.", ephemeral=True)
            return

        target = _pick_takeover_target(manager, interaction.user.display_name)
        if target is None:
            await interaction.response.send_message(
                "No suitable Draftmancer user found to transfer ownership to. "
                "Make sure you're in the Draftmancer session before running this.",
                ephemeral=True,
            )
            return
        target_user_id, target_user_name = target

        await interaction.response.defer(ephemeral=False, thinking=False)
        ok, err = await manager.takeover(target_user_id)
        if not ok:
            await interaction.followup.send(f"⚠️ Takeover failed: {err}", ephemeral=True)
            return
        await interaction.followup.send(
            f"👑 {interaction.user.mention} is now in control of the Draftmancer session. Bot disconnected."
        )


def _pick_takeover_target(manager, invoker_display_name: str):
    """Prefer the invoker by display_name match; else any non-bot user. Returns (userID, userName) or None."""
    for user in manager.session_users:
        if user.get("userName") == "DisChordBot":
            continue
        if user.get("userName") == invoker_display_name:
            return user.get("userID"), user.get("userName")
    for user in manager.session_users:
        if user.get("userName") != "DisChordBot":
            return user.get("userID"), user.get("userName")
    return None


def _find_manager_for_thread(interaction: discord.Interaction):
    """Pick the manager whose thread matches the invocation, else fall back to any active one."""
    channel_id = str(interaction.channel.id) if interaction.channel else None
    for manager in ACTIVE_POD_MANAGERS.values():
        if str(manager.thread_id) == channel_id:
            return manager
    return next(iter(ACTIVE_POD_MANAGERS.values()), None)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PodDraft(bot))
