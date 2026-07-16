"""Owner-only `!test` triggers for the on-demand pod signup surfaces.

`poll` posts a live daily launcher in this channel; `draft` posts a live /draft queue; `rsvp` posts a
live scheduled RSVP card. All reuse the production builders and persistent views and register real
signals, so clicking the buttons drives the real add / remove / fire path (a fire creates the thread
and Draftmancer lobby for real, and `rsvp` creates its thread, event, and timed jobs at post time).
Set POD_SIGNAL_FIRE_THRESHOLD low to reach a fire on your own.

`launcher` drives the whole surface for real: it stages a scheduled pod at the day's last slot so that
slot reflects as a committed jump-link with its Yes roster, leaving the other slots as live lazy
signals, then posts the live launcher. Everything routes through the production paths, so the preview
can't drift from what players see.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from bot.commands.messages import MSG_FIRST_POD_TIP_POLL, MSG_FIRST_POD_TIP_QUEUE
from bot.commands.pod_queue import (
    QUEUE_CLOSED_MANUAL,
    PodQueueView,
    queue_inactivity_close_reason,
    queue_role_mention,
)
from bot.commands.pod_rsvp import build_rsvp_embed, post_scheduled_card
from bot.commands.pod_table import offer_second_table
from bot.commands.test_group import test_group
from bot.config import settings
from bot.services import pod_launch
from bot.services.pod_signals import RSVP_YES, SCHEDULE_TZ, poll_buckets_for, slot_event_time
from bot.sets import active_set_code
from bot.tasks.pod_daily_poll import post_launcher


log = logging.getLogger(__name__)


async def setup(bot: commands.Bot) -> None:
    @test_group.command(name="poll")
    @commands.is_owner()
    async def test_poll(ctx: commands.Context) -> None:
        """Owner-only. Post a live daily launcher in this channel; the slot buttons drive real signals."""
        today = datetime.now(SCHEDULE_TZ).date()
        await post_launcher(ctx.bot, ctx.channel, today)

    @test_group.command(name="launcher")
    @commands.is_owner()
    async def test_launcher(ctx: commands.Context, fill: int = 5) -> None:
        """Owner-only. Drive the launcher end to end: stage a real scheduled pod at the day's last slot
        so it reflects as a committed jump-link, seed `fill` Yes RSVPs on it so the committed slot shows
        its roster, then post the live launcher for that day. The other slots are real lazy signals whose
        buttons drive the fire path; set POD_SIGNAL_FIRE_THRESHOLD low to graduate one yourself. Uses
        today when a slot is still ahead, otherwise tomorrow, so the staged pod is always in the future."""
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("Run `!test launcher` in a server text channel — the pod thread is created there.")
            return
        now = datetime.now(SCHEDULE_TZ)
        today = now.date()
        last_today = slot_event_time(today, poll_buckets_for(today)[-1].key)
        target_day = today if last_today > now else today + timedelta(days=1)
        reflect = poll_buckets_for(target_day)[-1]
        slot_time = slot_event_time(target_day, reflect.key)
        set_code = active_set_code()
        name = await asyncio.to_thread(pod_launch.ondemand_event_name_sync, set_code, slot_time)
        event_id = await post_scheduled_card(
            ctx.bot, ctx.channel, set_code=set_code, event_time=slot_time, name=name, ping_role=False,
        )
        if event_id is None:
            await ctx.send("Could not stage the reflected scheduled pod. Check the logs.")
            return
        if fill > 0:
            await _seed_fake_yes(ctx.channel, event_id, slot_time, name, fill)
        await ctx.send(f"Staged **{name}** at {reflect.name}; posting the live launcher for that day.")
        await post_launcher(ctx.bot, ctx.channel, target_day)

    @test_group.command(name="reset")
    @commands.is_owner()
    async def test_reset(ctx: commands.Context) -> None:
        """Owner-only. Clear this guild's on-demand pod signals (poll / queue / scheduled) so the `!test`
        surfaces start from a clean slate — every slot goes back to lazy. Leaves pod_draft_events and any
        live lobby alone; only the signup signals reflection reads are wiped."""
        guild_id = str(ctx.guild.id) if ctx.guild else ""
        counts = await asyncio.to_thread(pod_launch.reset_ondemand_signals_sync, guild_id)
        await ctx.send(
            f"Cleared on-demand pod signals: {counts['signals']} signals, {counts['members']} members."
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
        await offer_second_table(ctx.bot, event_id, {f"filltest-{i}" for i in range(seated)})

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

    @test_group.command(name="queueclosed")
    @commands.is_owner()
    async def test_queueclosed(ctx: commands.Context) -> None:
        """Owner-only. Post both closed-queue cards to eyeball the copy: the inactivity timeout keeps its
        roster of idle players, the manual close shows none (only the last player can close it). Inert
        previews through the real builder, no signal."""
        mention = queue_role_mention(ctx.guild)
        set_code = active_set_code()
        opened_at = datetime.now(timezone.utc) - timedelta(hours=1)
        opened_by = str(ctx.author.id)
        await ctx.send(view=PodQueueView(
            names=["Tester One", "Tester Two", "Tester Three"], role_mention=mention,
            close_reason=queue_inactivity_close_reason(), set_code=set_code,
            opened_at=opened_at, opened_by=opened_by,
        ))
        await ctx.send(view=PodQueueView(
            role_mention=mention, close_reason=QUEUE_CLOSED_MANUAL,
            set_code=set_code, opened_at=opened_at, opened_by=opened_by,
        ))


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
