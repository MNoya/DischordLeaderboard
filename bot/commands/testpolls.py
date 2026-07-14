"""Owner-only `!test` triggers for the on-demand pod signup surfaces.

`poll` posts a live daily poll in this channel; `draft` posts a live /draft queue. Both reuse the
production embed builders and persistent views and register real signals, so clicking the buttons
drives the real add / remove / fire path (a fire creates the thread and Draftmancer lobby for real).
Set POD_SIGNAL_FIRE_THRESHOLD low to reach a fire on your own. Neither arms expiry or teardown, so
the surface stays open while you poke at it.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

import discord
from discord.ext import commands

from bot.commands.messages import MSG_FIRST_POD_TIP_POLL, MSG_FIRST_POD_TIP_QUEUE
from bot.commands.pod_queue import PodQueueView, queue_role_mention
from bot.commands.test_group import test_group
from bot.config import settings
from bot.services import pod_launch
from bot.services.pod_signals import SCHEDULE_TZ
from bot.tasks.pod_daily_poll import PodPollView, initial_poll_embed, poll_ping_line


async def setup(bot: commands.Bot) -> None:
    @test_group.command(name="poll")
    @commands.is_owner()
    async def test_poll(ctx: commands.Context) -> None:
        """Owner-only. Post a live daily poll in this channel; the slot buttons drive the real signal."""
        today = datetime.now(SCHEDULE_TZ).date()
        embed = initial_poll_embed(today, ctx.guild)
        message = await ctx.send(
            content=poll_ping_line(ctx.guild), embed=embed, view=PodPollView(),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        guild_id = str(ctx.guild.id) if ctx.guild else ""
        await asyncio.to_thread(
            pod_launch.create_poll_signals_sync,
            guild_id=guild_id, channel_id=str(ctx.channel.id), message_id=str(message.id), signal_date=today,
        )

    @test_group.command(name="tip")
    @commands.is_owner()
    async def test_tip(ctx: commands.Context) -> None:
        """Owner-only. Post both first-contact tips verbatim to eyeball the copy."""
        threshold = settings.pod_signal_fire_threshold
        await ctx.send(MSG_FIRST_POD_TIP_POLL.format(threshold=threshold))
        await ctx.send(MSG_FIRST_POD_TIP_QUEUE.format(threshold=threshold))

    @test_group.command(name="draft")
    @commands.is_owner()
    async def test_draft(ctx: commands.Context) -> None:
        """Owner-only. Post a live /draft queue in this channel; the Join / Leave buttons drive the real signal."""
        today = datetime.now(SCHEDULE_TZ).date()
        view = PodQueueView(role_mention=queue_role_mention(ctx.guild))
        message = await ctx.send(view=view, allowed_mentions=discord.AllowedMentions(roles=True))
        guild_id = str(ctx.guild.id) if ctx.guild else ""
        await asyncio.to_thread(
            pod_launch.create_queue_signal_sync,
            guild_id=guild_id, channel_id=str(ctx.channel.id), message_id=str(message.id),
            signal_date=today, opened_by=str(ctx.author.id),
        )
