"""Weekly schedule auto-post and the per-slot RSVP card sends.

At MONDAY_POST_HOUR_ET the bot posts the week's pod-draft schedule to the coordination channel and pins
it, guarded by a channel scan so a restart never double-posts. Each weekly slot's RSVP card then posts
on its own date job at card_send_time; the bot owns the card, thread, event, and native Discord event
from post time (bot/commands/pod_rsvp.py).
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import date, datetime, time, timedelta, timezone

import discord
from discord.ext import commands

from bot.commands.pod_rsvp import post_scheduled_card
from bot.config import settings
from bot.discord_helpers import resolve_pod_chat_channel
from bot.services.pod_launch import ondemand_event_name_sync, slot_occupied_by_any_pod_sync
from bot.services.pod_schedule import (
    CARD_LEAD_HOURS,
    MONDAY_CARD_SEND_HOUR_ET,
    MONDAY_KIND_NORMAL,
    MONDAY_KIND_RELEASE_WEEK,
    SCHEDULE_TZ,
    WEEKLY_SLOTS,
    card_send_time,
    compose_schedule_message,
    monday_kind,
    monday_of,
    slot_by_weekday,
    upcoming_slots,
)
from bot.sets import active_set_code


MONDAY_POST_HOUR_ET = 12
CARD_CATCH_UP_DELAY_S = 5

log = logging.getLogger(__name__)

_bot: commands.Bot | None = None


def init_schedule_post(bot: commands.Bot) -> None:
    """Wire the bot reference and arm the Monday schedule post plus the per-slot RSVP card jobs."""
    global _bot
    _bot = bot
    if not settings.pod_schedule_enabled:
        log.info("POD_SCHEDULE_ENABLED=false; weekly schedule flow disabled")
        return
    bot.pod_scheduler.add_job(
        fire_weekly_schedule_post,
        "cron",
        day_of_week="mon",
        hour=MONDAY_POST_HOUR_ET,
        minute=0,
        timezone=SCHEDULE_TZ,
        id="pod-monday-post",
        replace_existing=True,
    )
    arm_card_jobs(_current_week_monday())
    arm_card_jobs(upcoming_monday())
    log.info(
        f"weekly schedule flow armed: post Mondays {MONDAY_POST_HOUR_ET}:00 {SCHEDULE_TZ.key}, "
        f"RSVP card sends: NA Mondays {MONDAY_CARD_SEND_HOUR_ET}:00, EU T-{CARD_LEAD_HOURS}h, Sat after Thu pod"
    )


async def fire_weekly_schedule_post() -> None:
    if _bot is None:
        log.error("fire_weekly_schedule_post: bot reference is not initialised")
        return
    await _post_default_if_needed()
    arm_card_jobs(upcoming_monday())


async def _post_default_if_needed(reference: datetime | None = None) -> bool:
    channel = await _fetch_schedule_channel()
    if channel is None:
        return False
    if await _schedule_already_posted(channel):
        log.info("schedule already posted in the pod-draft-chat channel; standing down")
        return False

    reference = reference or datetime.now(SCHEDULE_TZ)
    body = compose_schedule_message(reference, active_set_code())
    message = await channel.send(body)
    await _pin_schedule(channel, message)
    schedule_monday = monday_of(upcoming_slots(reference, 1)[0])
    kind, _ = monday_kind(schedule_monday)
    if kind == MONDAY_KIND_RELEASE_WEEK:
        try:
            await message.add_reaction("👍")
        except discord.HTTPException:
            log.warning("could not add 👍 reaction to release-week post", exc_info=True)
    log.info(f"posted the weekly schedule for {schedule_monday.isoformat()} ({kind})")
    return True


async def _pin_schedule(channel: discord.abc.Messageable, message: discord.Message) -> None:
    """Pin the freshly-posted weekly schedule, unpinning the bot/owner's prior schedule pins first."""
    poster_ids = {_bot.owner_id, _bot.user.id if _bot.user else None}
    try:
        pins = await channel.pins()
    except (discord.HTTPException, AttributeError):
        log.warning("could not read pins while pinning the weekly schedule", exc_info=True)
        pins = []
    for pinned in pins:
        if pinned.id == message.id or pinned.author.id not in poster_ids or "<t:" not in pinned.content:
            continue
        try:
            await pinned.unpin()
        except discord.HTTPException:
            log.warning(f"could not unpin previous schedule {pinned.id}", exc_info=True)
    try:
        await message.pin()
    except discord.HTTPException:
        log.warning("could not pin the weekly schedule post", exc_info=True)


async def _schedule_already_posted(channel: discord.abc.Messageable) -> bool:
    since = datetime.combine(upcoming_monday(), time(MONDAY_POST_HOUR_ET, 0), tzinfo=SCHEDULE_TZ)
    poster_ids = {_bot.owner_id, _bot.user.id if _bot.user else None}
    try:
        async for message in channel.history(after=since, limit=50):
            if message.author.id in poster_ids and "<t:" in message.content:
                return True
    except discord.HTTPException:
        log.warning("could not scan the pod-draft-chat channel for an existing post", exc_info=True)
    return False


def arm_card_jobs(monday: date) -> None:
    """Schedule one RSVP card post per weekly slot at its card_send_time.

    No-op on boundary weeks (release/championship/season); deterministic job ids keep a restart
    re-arm from double-firing. A send missed to downtime is caught up immediately while the slot is
    still ahead — fire_scheduled_card skips slots that already have a pod.
    """
    scheduler = getattr(_bot, "pod_scheduler", None)
    if scheduler is None:
        return
    if monday_kind(monday)[0] != MONDAY_KIND_NORMAL:
        return
    now = datetime.now(timezone.utc)
    for slot in WEEKLY_SLOTS:
        run_at = card_send_time(slot, monday)
        job_id = f"pod-rsvp-card-{monday.isoformat()}-{slot.weekday}"
        if run_at <= now:
            slot_start = datetime.combine(
                monday + timedelta(days=slot.weekday), slot.start, tzinfo=SCHEDULE_TZ
            )
            if slot_start <= now:
                with contextlib.suppress(Exception):
                    scheduler.remove_job(job_id)
                continue
            run_at = now + timedelta(seconds=CARD_CATCH_UP_DELAY_S)
        scheduler.add_job(
            fire_scheduled_card,
            "date",
            run_date=run_at,
            args=[monday.isoformat(), slot.weekday],
            id=job_id,
            replace_existing=True,
        )
        log.info(f"armed RSVP card for {monday.isoformat()} weekday={slot.weekday} at {run_at.isoformat()}")


async def fire_scheduled_card(monday_iso: str, weekday: int) -> None:
    """Post one weekly slot's RSVP card, skipping boundary weeks, started slots, and slots that
    already have a pod — safe to fire again after a restart or catch-up."""
    if _bot is None:
        log.error("fire_scheduled_card: bot reference is not initialised")
        return
    monday = date.fromisoformat(monday_iso)
    if monday_kind(monday)[0] != MONDAY_KIND_NORMAL:
        return
    slot = slot_by_weekday(weekday)
    if slot is None:
        return
    slot_start = datetime.combine(monday + timedelta(days=slot.weekday), slot.start, tzinfo=SCHEDULE_TZ)
    if slot_start <= datetime.now(timezone.utc):
        log.info(f"RSVP card for {monday_iso} weekday={weekday}: slot already started; standing down")
        return
    if await asyncio.to_thread(slot_occupied_by_any_pod_sync, slot_start):
        log.info(f"RSVP card for {monday_iso} weekday={weekday}: pod already exists; standing down")
        return

    channel = await _fetch_coordination_channel()
    if channel is None:
        return
    set_code = active_set_code()
    name = await asyncio.to_thread(ondemand_event_name_sync, set_code, slot_start)
    await post_scheduled_card(_bot, channel, set_code=set_code, event_time=slot_start, name=name)


async def _fetch_coordination_channel() -> discord.TextChannel | None:
    channel = _bot.get_channel(settings.pod_draft_channel_id)
    if channel is None:
        try:
            channel = await _bot.fetch_channel(settings.pod_draft_channel_id)
        except discord.HTTPException as e:
            log.warning(f"could not fetch coordination channel {settings.pod_draft_channel_id}: {e}")
            return None
    return channel if isinstance(channel, discord.TextChannel) else None


async def _fetch_schedule_channel() -> discord.abc.Messageable | None:
    channel = resolve_pod_chat_channel(_bot)
    if channel is not None:
        return channel
    try:
        return await _bot.fetch_channel(settings.pod_draft_channel_id)
    except discord.HTTPException as e:
        log.warning(f"could not fetch schedule channel {settings.pod_draft_channel_id}: {e}")
        return None


def upcoming_monday() -> date:
    today = datetime.now(SCHEDULE_TZ).date()
    return today + timedelta(days=(7 - today.weekday()) % 7)


def _current_week_monday() -> date:
    today = datetime.now(SCHEDULE_TZ).date()
    return today - timedelta(days=today.weekday())
