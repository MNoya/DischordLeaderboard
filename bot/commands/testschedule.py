"""Owner-only `!test` triggers for the pod-draft scheduler, each reusing the production path.

`underfill` renders the underfill nudge with sample numbers. `reminder` renders the roster reminder
embed with sample rosters. `rolegrant` posts the auto-grant announcement embed so its look can be
checked. The Monday schedule package itself is exercised through the real `/pod-schedule` command;
the scheduled RSVP card through `!test rsvp`.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import discord
from discord.ext import commands

from bot.commands.test_group import test_group
from bot.config import settings
from bot.services.ping_roles import PING_ROLES, build_grant_embed
from bot.services.pod_roles import find_role
from bot.services.pod_schedule import SCHEDULE_TZ, build_underfill_message, slots_for_week
from bot.tasks.pod_draft_reminder import ROSTER_REMINDER_LEAD_MIN, build_roster_embed


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

    @test_group.command(name="reminder")
    @commands.is_owner()
    async def test_reminder(ctx: commands.Context) -> None:
        """Owner-only. Post a sample roster reminder embed in this channel — no DB or sesh lookup."""
        name = ctx.channel.name if isinstance(ctx.channel, discord.Thread) else "Sample Pod Draft - Jun 25"
        starts_at = datetime.now(SCHEDULE_TZ) + timedelta(minutes=ROSTER_REMINDER_LEAD_MIN)
        yes = ["Nissa Revane", "Chandra Nalaar", "Jace Beleren", "Liliana Vess", "Gideon Jura"]
        maybe = ["Ajani Goldmane", "Kaya Bala"]
        embed = build_roster_embed(name, starts_at, yes, maybe)
        await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

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
            embed = build_grant_embed(ctx.author.mention, role, spec)
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
