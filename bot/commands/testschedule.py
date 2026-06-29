"""Owner-only `!test` triggers for the pod-draft scheduler, each reusing the production path.

`underfill` renders the underfill nudge with sample numbers. `createsend` fires the real per-event
/create DM for a week. `rolegrant` posts the auto-grant announcement embed so its look can be checked.
The Monday schedule package itself is exercised through the real `/pod-schedule` command.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import discord
from discord.ext import commands

from bot.commands.test_group import test_group
from bot.config import settings
from bot.services.ping_roles import PING_ROLES, build_grant_embed
from bot.services.pod_roles import find_role
from bot.services.pod_schedule import (
    MONDAY_KIND_NORMAL,
    SCHEDULE_TZ,
    WEEKLY_SLOTS,
    build_underfill_message,
    monday_kind,
    slots_for_week,
)
from bot.tasks.pod_schedule_post import fire_create_command, upcoming_monday


MSG_BAD_WEEK = "Couldn't read that week — use `YYYY-MM-DD`, or leave it blank for the upcoming week."


async def setup(bot: commands.Bot) -> None:
    @test_group.command(name="underfill")
    @commands.is_owner()
    async def test_underfill(ctx: commands.Context, yes_count: int = 5) -> None:
        """Owner-only. Post a sample underfill nudge in this channel — no DB or sesh lookup."""
        name = ctx.channel.name if isinstance(ctx.channel, discord.Thread) else "Sample Pod Draft - Jun 25"
        body = build_underfill_message(
            name, yes_count, settings.pod_draft_target_players, _next_slot(), ctx.message.jump_url,
        )
        await ctx.send(body, allowed_mentions=discord.AllowedMentions.none())

    @test_group.command(name="createsend")
    @commands.is_owner()
    async def test_createsend(ctx: commands.Context, week: str = "") -> None:
        """Owner-only. DM yourself the per-event /create messages for a week via the real fire path."""
        monday = upcoming_monday()
        if week:
            try:
                parsed = date.fromisoformat(week)
            except ValueError:
                await ctx.send(MSG_BAD_WEEK)
                return
            monday = parsed - timedelta(days=parsed.weekday())
        kind, _ = monday_kind(monday)
        if kind != MONDAY_KIND_NORMAL:
            await ctx.send(f"Week of {monday.isoformat()} is a {kind} week — no pods to send. Pass a normal week.")
            return
        for slot in WEEKLY_SLOTS:
            await fire_create_command(monday.isoformat(), slot.weekday)
        await ctx.send(f"DMed {len(WEEKLY_SLOTS)} /create message(s) for the week of {monday.isoformat()}.")

    @test_group.command(name="rolegrant")
    @commands.is_owner()
    async def test_rolegrant(ctx: commands.Context) -> None:
        """Owner-only. Post the auto-grant announcement embed for each auto-granted role, to eyeball it."""
        guild = ctx.guild or ctx.bot.get_guild(settings.discord_guild_id)
        if guild is None:
            await ctx.send("No guild available to resolve roles.")
            return
        posted = 0
        for spec in PING_ROLES:
            if not spec.auto_grant:
                continue
            role = find_role(guild, spec.name)
            if role is None:
                await ctx.send(f"No `{spec.name}` role on **{guild.name}** — create it first.")
                continue
            embed = build_grant_embed(ctx.author.mention, role, spec.emoji)
            await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            posted += 1
        if posted == 0:
            await ctx.send("No auto-grant roles to preview.")


def _next_slot() -> datetime:
    now = datetime.now(SCHEDULE_TZ)
    monday = now.date() - timedelta(days=now.weekday())
    candidates = slots_for_week(monday) + slots_for_week(monday + timedelta(days=7))
    for slot in candidates:
        if slot > now:
            return slot
    return candidates[-1]
