"""Owner-only `!test` triggers for the on-demand pod signup surfaces.

`poll` posts a live daily poll in this channel; `draft` posts a live /draft queue; `rsvp` posts a
live scheduled RSVP card. All reuse the production builders and persistent views and register real
signals, so clicking the buttons drives the real add / remove / fire path (a fire creates the thread
and Draftmancer lobby for real, and `rsvp` creates its thread, event, and timed jobs at post time).
Set POD_SIGNAL_FIRE_THRESHOLD low to reach a fire on your own. Neither poll nor draft arms expiry or
teardown, so the surface stays open while you poke at it.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from bot.commands.messages import MSG_FIRST_POD_TIP_POLL, MSG_FIRST_POD_TIP_QUEUE
from bot.commands.pod_queue import PodQueueView, queue_role_mention
from bot.commands.pod_rsvp import build_rsvp_embed, post_scheduled_card
from bot.commands.pod_table import offer_second_table
from bot.commands.test_group import test_group
from bot.config import settings
from bot.services import pod_launch
from bot.services.pod_signals import RSVP_YES, SCHEDULE_TZ
from bot.sets import active_set_code
from bot.tasks.pod_daily_poll import PodPollView, initial_poll_embed, poll_ping_line


log = logging.getLogger(__name__)


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

    @test_group.command(name="rsvp")
    @commands.is_owner()
    async def test_rsvp(ctx: commands.Context, minutes: int = 60, fill: int = 0) -> None:
        """Owner-only. Post a live scheduled RSVP card in this channel via the production creation
        path — thread, event, native Discord event, and timed jobs included. `minutes` sets how far
        out the pod starts; `fill` seeds that many fake Yes signups so the '≥8' multi-pod notice can
        be previewed without eight real people."""
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("Run `!test rsvp` in a server text channel — the thread is created there.")
            return
        event_time = datetime.now(SCHEDULE_TZ) + timedelta(minutes=minutes)
        set_code = active_set_code()
        name = await asyncio.to_thread(pod_launch.ondemand_event_name_sync, set_code, event_time)
        event_id = await post_scheduled_card(
            ctx.bot, ctx.channel, set_code=set_code, event_time=event_time, name=name,
        )
        if event_id is None:
            await ctx.send("Could not create the scheduled card. Check the logs.")
            return
        if fill > 0:
            await _seed_fake_yes(ctx.channel, event_id, event_time, name, fill)

    @test_group.command(name="secondtable")
    @commands.is_owner()
    async def test_secondtable(ctx: commands.Context, total: int = 14, seated: int = 8) -> None:
        """Owner-only. Post a scheduled card, seed `total` fake Yes, then simulate the first pod firing
        with `seated` of them locked in and offer a second table to the rest. No live draft needed —
        this drives the same offer path `_start_draft` fires. Needs `total - seated` at or above the
        table threshold to actually post an offer."""
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("Run `!test secondtable` in a server text channel.")
            return
        event_time = datetime.now(SCHEDULE_TZ) + timedelta(minutes=60)
        set_code = active_set_code()
        name = await asyncio.to_thread(pod_launch.ondemand_event_name_sync, set_code, event_time)
        event_id = await post_scheduled_card(
            ctx.bot, ctx.channel, set_code=set_code, event_time=event_time, name=name,
        )
        if event_id is None:
            await ctx.send("Could not create the scheduled card. Check the logs.")
            return
        names = [f"Tester {i + 1}" for i in range(total)]
        ref = await asyncio.to_thread(pod_launch.scheduled_card_ref_sync, event_id)
        for i, display in enumerate(names):
            await asyncio.to_thread(pod_launch.set_rsvp_sync, ref[2], f"filltest-{i}", display, RSVP_YES)
        await offer_second_table(ctx.bot, event_id, names[:seated])

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


async def _seed_fake_yes(
    channel: discord.TextChannel, event_id: str, event_time: datetime, name: str, count: int,
) -> None:
    """Record `count` fake Yes RSVPs against the just-posted card and re-render it, so the multi-pod
    notice can be eyeballed solo. Fake members never touch Discord; they only fill the roster."""
    ref = await asyncio.to_thread(pod_launch.scheduled_card_ref_sync, event_id)
    if ref is None:
        return
    message_id = ref[2]
    rosters = None
    for i in range(count):
        result = await asyncio.to_thread(
            pod_launch.set_rsvp_sync, message_id, f"filltest-{i}", f"Tester {i + 1}", RSVP_YES)
        if result is not None:
            rosters = result.rosters
    if rosters is None:
        return
    try:
        card = await channel.fetch_message(int(message_id))
        await card.edit(embed=build_rsvp_embed(name, event_time, rosters))
    except discord.HTTPException:
        log.warning(f"could not re-render the fake-fill card {message_id}", exc_info=True)
