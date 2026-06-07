"""Admin-only `/pod-schedule` — preview the weekly package on demand and act on it early.

Renders the exact body and buttons the Monday DM sends, ephemerally in the invoking channel.
`week` composes for any week so boundary variants and blurb cycling can be checked ahead of time;
the buttons (Post it for me / I've got it / Skip this week) carry that week, so skipping a future
week here suppresses its fallback post.
"""
from __future__ import annotations

from datetime import date, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from bot.commands import descriptions as desc
from bot.commands.messages import MSG_ADMIN_ONLY
from bot.tasks.pod_schedule_post import build_monday_package, upcoming_monday


MSG_BAD_WEEK = "Couldn't read that week — use `YYYY-MM-DD`, or leave it blank for the upcoming week."


class PodSchedule(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="pod-schedule", description=desc.POD_SCHEDULE)
    @app_commands.describe(week="Any date in the target week (YYYY-MM-DD); defaults to the upcoming week")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_schedule(self, interaction: discord.Interaction, week: str | None = None) -> None:
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(MSG_ADMIN_ONLY, ephemeral=True)
            return

        monday = upcoming_monday()
        if week:
            try:
                parsed = date.fromisoformat(week)
            except ValueError:
                await interaction.response.send_message(MSG_BAD_WEEK, ephemeral=True)
                return
            monday = parsed - timedelta(days=parsed.weekday())

        body, view, create_blocks = await build_monday_package(monday)
        await interaction.response.send_message(body, view=view, ephemeral=True)
        if create_blocks is not None:
            await interaction.followup.send(create_blocks, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PodSchedule(bot))
