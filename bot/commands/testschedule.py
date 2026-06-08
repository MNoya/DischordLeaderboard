"""Owner-only `!test underfill` — preview the underfill reminder copy in Discord.

The reminder's real firing lives in bot/tasks/pod_underfill.py; this only renders the message
with sample numbers so the wording can be eyeballed. The Monday schedule package is exercised
through the real `/pod-schedule` command, not here.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import discord
from discord.ext import commands

from bot.commands.test_group import test_group
from bot.config import settings
from bot.services.pod_schedule import SCHEDULE_TZ, build_underfill_message, slots_for_week


async def setup(bot: commands.Bot) -> None:
    @test_group.command(name="underfill")
    @commands.is_owner()
    async def test_underfill(ctx: commands.Context, yes_count: int = 5) -> None:
        """Owner-only. Post a sample underfill nudge in this channel — no DB or sesh lookup."""
        body = build_underfill_message(
            ctx.channel.name if isinstance(ctx.channel, discord.Thread) else "Sample Pod Draft",
            ctx.channel.jump_url,
            yes_count,
            settings.pod_draft_target_players,
            _next_slot(),
            ctx.message.jump_url,
        )
        await ctx.send(body, allowed_mentions=discord.AllowedMentions.none())


def _next_slot() -> datetime:
    now = datetime.now(SCHEDULE_TZ)
    monday = now.date() - timedelta(days=now.weekday())
    candidates = slots_for_week(monday) + slots_for_week(monday + timedelta(days=7))
    for slot in candidates:
        if slot > now:
            return slot
    return candidates[-1]
