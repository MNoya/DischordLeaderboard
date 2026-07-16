"""Nightly archive of past pod-draft threads.

Fires at 02:00 ET, when the day's pods are long finished. Discord threads carry no auto-archive
below 24h, so old draft rooms linger in the active list; this collapses them the way "Hide After
Inactivity" would. Archiving is reversible — anyone posting reopens the thread — so it only tidies
the sidebar, it does not lock conversation.

Only events whose start time has already passed are touched, and only within a short lookback so
each night re-scans a handful of threads rather than the full history; older threads were archived
on an earlier night. Already-archived threads, and any thread with a message inside the activity
grace window, are left alone so a live conversation is never cut off mid-sentence — it archives on
a later night once it goes quiet.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands
from sqlalchemy import select

from bot.database import SessionLocal
from bot.models import PodDraftEvent
from bot.services.pod_schedule import SCHEDULE_TZ


CLEANUP_HOUR_ET = 2
LOOKBACK_DAYS = 2
ACTIVITY_GRACE = timedelta(hours=2)

log = logging.getLogger(__name__)

_bot: commands.Bot | None = None


def init_thread_cleanup(bot: commands.Bot) -> None:
    global _bot
    _bot = bot
    bot.pod_scheduler.add_job(
        archive_past_threads, "cron", hour=CLEANUP_HOUR_ET, minute=0,
        timezone=SCHEDULE_TZ, id="pod-thread-cleanup", replace_existing=True,
    )
    log.info(f"scheduled nightly pod thread cleanup at {CLEANUP_HOUR_ET:02d}:00 ET")


async def archive_past_threads() -> None:
    if _bot is None:
        return
    now = datetime.now(timezone.utc)
    thread_ids = _past_event_thread_ids(now)
    archived = 0
    for thread_id in thread_ids:
        if await _archive_thread(thread_id, now):
            archived += 1
    log.info(f"pod thread cleanup: archived {archived} of {len(thread_ids)} past-event threads")


def _past_event_thread_ids(now: datetime) -> list[int]:
    window_start = now - timedelta(days=LOOKBACK_DAYS)
    with SessionLocal() as session:
        rows = session.execute(
            select(
                PodDraftEvent.discord_thread_id,
                PodDraftEvent.team_a_thread_id,
                PodDraftEvent.team_b_thread_id,
            ).where(PodDraftEvent.event_time < now, PodDraftEvent.event_time >= window_start)
        ).all()
    ids: list[int] = []
    seen: set[int] = set()
    for row in rows:
        for raw in row:
            if raw is None:
                continue
            thread_id = int(raw)
            if thread_id not in seen:
                seen.add(thread_id)
                ids.append(thread_id)
    return ids


async def _archive_thread(thread_id: int, now: datetime) -> bool:
    try:
        channel = await _bot.fetch_channel(thread_id)
    except discord.NotFound:
        return False
    except discord.HTTPException as e:
        log.warning(f"pod thread cleanup: fetch_channel({thread_id}) failed: {e}")
        return False
    if not isinstance(channel, discord.Thread) or channel.archived:
        return False
    if _last_activity(channel) > now - ACTIVITY_GRACE:
        return False
    try:
        await channel.edit(archived=True, reason="Nightly pod thread cleanup")
    except discord.HTTPException as e:
        log.warning(f"pod thread cleanup: archive({thread_id}) failed: {e}")
        return False
    return True


def _last_activity(thread: discord.Thread) -> datetime:
    if thread.last_message_id is not None:
        return discord.utils.snowflake_time(thread.last_message_id)
    return thread.created_at or thread.archive_timestamp
