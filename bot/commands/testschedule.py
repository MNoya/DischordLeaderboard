"""Owner-only `!test monday` / `!test underfill` — fire the scheduler flows on demand."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import discord
from discord.ext import commands

from bot.commands.test_group import test_group
from bot.config import settings
from bot.services.pod_schedule import SCHEDULE_TZ, build_underfill_message, slots_for_week
from bot.tasks.pod_schedule_post import fire_monday_dm


MSG_BAD_DATE = "Usage: `!test monday [YYYY-MM-DD]` — the date picks which week to draft for."


async def setup(bot: commands.Bot) -> None:
    @test_group.command(name="monday")
    @commands.is_owner()
    async def test_monday(ctx: commands.Context, day: str = "") -> None:
        """Owner-only. DM the Monday schedule package now, as-if for `day`'s week.

        `!test monday`             — this week (live boundary detection)
        `!test monday 2026-06-15`  — any week, to preview championship/release variants
        """
        monday = None
        if day:
            try:
                parsed = date.fromisoformat(day)
            except ValueError:
                await ctx.send(MSG_BAD_DATE)
                return
            monday = parsed - timedelta(days=parsed.weekday())
        await fire_monday_dm(monday)

    @test_group.command(name="underfill")
    @commands.is_owner()
    async def test_underfill(ctx: commands.Context, yes_count: int = 5) -> None:
        """Owner-only. Post a sample underfill reminder in this channel — no DB or sesh lookup."""
        body = build_underfill_message(
            settings.pod_drafters_role_id,
            yes_count,
            settings.pod_draft_target_players,
            _next_slot(),
            ctx.message.jump_url,
        )
        await ctx.send(body, allowed_mentions=discord.AllowedMentions(roles=True))


def _next_slot() -> datetime:
    now = datetime.now(SCHEDULE_TZ)
    monday = now.date() - timedelta(days=now.weekday())
    candidates = slots_for_week(monday) + slots_for_week(monday + timedelta(days=7))
    for slot in candidates:
        if slot > now:
            return slot
    return candidates[-1]
