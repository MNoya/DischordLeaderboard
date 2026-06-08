"""T-24h / T-3h underfill checks fired by APScheduler date jobs, plus live RSVP-driven updates.

Each check re-fetches the sesh embed's Yes list at fire time; events at or above the target stay
silent. Short events get a silent nudge in the coordination channel — no role ping — that links the
thread and the RSVP message. The T-24h check posts the nudge; the T-3h check deletes and reposts it so
it resurfaces near the event. While the nudge is up, sesh RSVP edits drive `refresh_underfill_nudge`
to keep the count current; once the pod hits the target the nudge freezes to a "full" state and stops
updating. The nudge is located by scanning channel history for the bot's own message linking the
thread — nothing is persisted to the database.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands
from sqlalchemy import select

from bot.config import settings
from bot.database import SessionLocal
from bot.models import PodDraftEvent
from bot.services.pod_schedule import build_underfill_filled_message, build_underfill_message
from bot.tasks.pod_draft_reminder import fetch_sesh_rsvps


UNDERFILL_CHECK_HOURS = (24, 3)
NUDGE_SEARCH_LIMIT = 100
FULL_NUDGE_MARKER = "Pod is full"

log = logging.getLogger(__name__)

_bot: commands.Bot | None = None


def init_underfill(bot: commands.Bot) -> None:
    """Wire the bot reference so the APScheduler callbacks can dispatch Discord work."""
    global _bot
    _bot = bot


def schedule_underfill_checks(scheduler, event_id: str, event_time: datetime) -> None:
    now = datetime.now(timezone.utc)
    for hours in UNDERFILL_CHECK_HOURS:
        run_at = event_time - timedelta(hours=hours)
        job_id = f"pod-underfill{hours}-{event_id}"
        if run_at <= now:
            with contextlib.suppress(Exception):
                scheduler.remove_job(job_id)
            continue
        scheduler.add_job(
            fire_underfill,
            "date",
            run_date=run_at,
            args=[event_id, hours],
            id=job_id,
            replace_existing=True,
        )
        log.info(f"scheduled T-{hours}h underfill check for event {event_id} at {run_at.isoformat()}")


async def fire_underfill(event_id: str, hours_before: int) -> None:
    if _bot is None:
        log.error(f"fire_underfill for {event_id}: bot reference is not initialised")
        return

    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is None:
            log.warning(f"fire_underfill: pod_draft_event {event_id} not found")
            return
        if event.socket_status != "pending":
            log.info(f"fire_underfill: event {event_id} is {event.socket_status}; skipping")
            return
        sesh_message_id = event.sesh_message_id
        event_time = event.event_time
        name = event.name
        thread_id = event.discord_thread_id

    if event_time <= datetime.now(timezone.utc):
        log.info(f"fire_underfill: event {event_id} already started; skipping")
        return

    rsvps = await fetch_sesh_rsvps(_bot, sesh_message_id)
    if rsvps is None:
        log.info(f"fire_underfill: sesh message {sesh_message_id} gone for event {event_id}; skipping")
        return
    yes_count = len(rsvps[0])
    target = settings.pod_draft_target_players

    channel = _bot.get_channel(settings.pod_draft_channel_id)
    if channel is None:
        log.warning(f"fire_underfill: coordination channel {settings.pod_draft_channel_id} unavailable")
        return

    thread_url = _thread_jump_url(thread_id)
    nudge = await _find_nudge(channel, thread_url)

    if yes_count >= target:
        if nudge is not None and not _is_frozen(nudge):
            await _safe_edit(nudge, build_underfill_filled_message(name, thread_url))
        log.info(f"T-{hours_before}h check for {event_id}: {yes_count}/{target} Yes; staying silent")
        return

    jump_url = _sesh_jump_url(sesh_message_id)
    body = build_underfill_message(name, thread_url, yes_count, target, event_time, jump_url)
    if hours_before == min(UNDERFILL_CHECK_HOURS) and nudge is not None:
        await _safe_delete(nudge)
        nudge = None
    if nudge is not None:
        await _safe_edit(nudge, body)
    else:
        await _safe_post(channel, body)
    log.info(f"T-{hours_before}h underfill nudge for {event_id}: {yes_count}/{target} Yes")


async def refresh_underfill_nudge(bot: commands.Bot, sesh_message_id: str, yes_count: int) -> None:
    """Edit the live underfill nudge in place when RSVPs change; freeze it once the pod fills.

    No-op until a check has posted a nudge — this only ever edits an existing message, never creates one.
    """
    loaded = await asyncio.to_thread(_load_event_for_nudge, str(sesh_message_id))
    if loaded is None:
        return
    name, thread_id, event_time, status = loaded
    if status != "pending":
        return

    channel = bot.get_channel(settings.pod_draft_channel_id)
    if channel is None:
        return

    thread_url = _thread_jump_url(thread_id)
    nudge = await _find_nudge(channel, thread_url)
    if nudge is None or _is_frozen(nudge):
        return

    target = settings.pod_draft_target_players
    if yes_count >= target:
        await _safe_edit(nudge, build_underfill_filled_message(name, thread_url))
        return
    jump_url = _sesh_jump_url(str(sesh_message_id))
    body = build_underfill_message(name, thread_url, yes_count, target, event_time, jump_url)
    await _safe_edit(nudge, body)


def _load_event_for_nudge(sesh_message_id: str) -> tuple[str, str, datetime, str] | None:
    with SessionLocal() as session:
        event = session.execute(
            select(PodDraftEvent).where(PodDraftEvent.sesh_message_id == sesh_message_id)
        ).scalar_one_or_none()
        if event is None:
            return None
        return event.name, event.discord_thread_id, event.event_time, event.socket_status


async def _find_nudge(channel: discord.abc.Messageable, thread_url: str) -> discord.Message | None:
    """The bot's own underfill nudge for an event, located by the thread link it carries."""
    try:
        async for message in channel.history(limit=NUDGE_SEARCH_LIMIT):
            if message.author.id == _bot.user.id and thread_url in message.content:
                return message
    except discord.HTTPException:
        log.warning("could not scan coordination channel for the underfill nudge", exc_info=True)
    return None


def _is_frozen(message: discord.Message) -> bool:
    return FULL_NUDGE_MARKER in message.content


async def _safe_post(channel: discord.abc.Messageable, body: str) -> None:
    try:
        await channel.send(body, allowed_mentions=discord.AllowedMentions.none())
    except discord.HTTPException:
        log.warning("could not post underfill nudge", exc_info=True)


async def _safe_edit(message: discord.Message, body: str) -> None:
    try:
        await message.edit(content=body, allowed_mentions=discord.AllowedMentions.none())
    except discord.HTTPException:
        log.warning(f"could not edit underfill nudge {message.id}", exc_info=True)


async def _safe_delete(message: discord.Message) -> None:
    with contextlib.suppress(discord.HTTPException):
        await message.delete()


def _thread_jump_url(thread_id: str) -> str:
    return f"https://discord.com/channels/{settings.discord_guild_id}/{thread_id}"


def _sesh_jump_url(sesh_message_id: str) -> str:
    return (
        f"https://discord.com/channels/{settings.discord_guild_id}"
        f"/{settings.pod_draft_channel_id}/{sesh_message_id}"
    )
