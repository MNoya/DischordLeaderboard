"""Admin-only `/pod-schedule` — preview the weekly package on demand and act on it early.

DMs the schedule (with its Post it for me / I've got it / Skip this week buttons) and each Sesh /create
command as its own message, so on mobile every code block keeps its own copy button — an in-channel reply
chain would force them into one ephemeral thread. `week` composes for any week so boundary variants and
blurb cycling can be checked ahead of time; the buttons carry that week, so skipping a future week here
suppresses its fallback post.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from bot.commands import descriptions as desc
from bot.commands.messages import MSG_ADMIN_ONLY
from bot.services.pod_schedule import SCHEDULE_TZ
from bot.tasks.pod_schedule_post import build_monday_package, upcoming_monday


MSG_BAD_WEEK = "Couldn't read that week — use `YYYY-MM-DD`, or leave it blank for the upcoming week."
MSG_SCHEDULE_IN_DMS = "📬 Schedule draft and /create commands sent to your DMs."
MSG_DMS_BLOCKED = "DMs are closed — open them to the bot to get the schedule draft and /create commands."


class PodSchedule(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="pod-schedule", description=desc.POD_SCHEDULE)
    @app_commands.describe(week="Any date in the target week (YYYY-MM-DD); defaults to the upcoming week")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def pod_schedule(self, interaction: discord.Interaction, week: str | None = None) -> None:
        ephemeral = interaction.guild is not None
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(MSG_ADMIN_ONLY, ephemeral=ephemeral)
            return

        reference = datetime.now(SCHEDULE_TZ)
        week_monday = upcoming_monday()
        if week:
            try:
                parsed = date.fromisoformat(week)
            except ValueError:
                await interaction.response.send_message(MSG_BAD_WEEK, ephemeral=ephemeral)
                return
            week_monday = parsed - timedelta(days=parsed.weekday())
            reference = datetime.combine(week_monday, time.min, tzinfo=SCHEDULE_TZ)

        body, view, create_blocks = await build_monday_package(reference, week_monday)
        await interaction.response.defer(ephemeral=ephemeral, thinking=True)
        try:
            dm = await interaction.user.create_dm()
            await dm.send(body, view=view)
            for block in create_blocks:
                await dm.send(block)
        except discord.Forbidden:
            await interaction.followup.send(MSG_DMS_BLOCKED, ephemeral=ephemeral)
            return
        await interaction.followup.send(MSG_SCHEDULE_IN_DMS, ephemeral=ephemeral)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PodSchedule(bot))
