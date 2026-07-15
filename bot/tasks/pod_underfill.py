"""T-24h / T-3h underfill checks fired by APScheduler date jobs, plus live RSVP-driven updates.

Each check re-fetches the Yes list at fire time — the sesh embed for sesh-born pods, the signal
members for card-born pods; events at or above the target stay silent. Short events get a silent
nudge in the pod-draft-chat channel — no role ping — carrying the signup link back to the RSVP
message in the coordination channel. The T-24h check posts the nudge; the T-3h check deletes and
reposts it so it resurfaces near the event. While the nudge is up, RSVP changes (sesh edits or card
clicks) keep the count current; once the pod hits the target the nudge is deleted. The nudge is
located by scanning channel history for the bot's own message carrying the signup link — nothing is
persisted to the database.
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
from bot.discord_helpers import resolve_pod_chat_channel
from bot.models import PodDraftEvent, PodSignal
from bot.services.pod_schedule import build_underfill_message
from bot.services.pod_signals import KIND_SCHEDULED
from bot.tasks.pod_draft_reminder import event_rsvps, fetch_sesh_rsvps


UNDERFILL_CHECK_HOURS = (24, 3)
NUDGE_SEARCH_LIMIT = 100
CATCH_UP_DELAY_S = 5

log = logging.getLogger(__name__)

_bot: commands.Bot | None = None


def init_underfill(bot: commands.Bot) -> None:
    """Wire the bot reference so the APScheduler callbacks can dispatch Discord work."""
    global _bot
    _bot = bot


def schedule_underfill_checks(scheduler, event_id: str, event_time: datetime, created_at: datetime) -> None:
    """Arm the T-24h / T-3h checks, firing an immediate catch-up for any check whose time already passed.

    A past check is only caught up when the event predates it (`created_at <= run_at`): that means the
    check was missed to downtime, not that the event was created short-notice. Freshly created events
    stay silent until their first future check, since the nudge means "created a while ago, still unfilled".

    Only the scheduled T-3h job resurfaces the nudge (delete + repost); the catch-up refreshes it in
    place, so a restart inside the window never reposts an already-standing nudge.
    """
    now = datetime.now(timezone.utc)
    resurface_hours = min(UNDERFILL_CHECK_HOURS)
    catch_up = False
    for hours in UNDERFILL_CHECK_HOURS:
        run_at = event_time - timedelta(hours=hours)
        job_id = f"pod-underfill{hours}-{event_id}"
        if run_at <= now:
            with contextlib.suppress(Exception):
                scheduler.remove_job(job_id)
            if event_time > now and created_at <= run_at:
                catch_up = True
            continue
        scheduler.add_job(
            fire_underfill,
            "date",
            run_date=run_at,
            args=[event_id, hours, hours == resurface_hours],
            id=job_id,
            replace_existing=True,
        )
        log.info(f"scheduled T-{hours}h underfill check for event {event_id} at {run_at.isoformat()}")

    if catch_up:
        scheduler.add_job(
            fire_underfill,
            "date",
            run_date=now + timedelta(seconds=CATCH_UP_DELAY_S),
            args=[event_id, resurface_hours, False],
            id=f"pod-underfill-catchup-{event_id}",
            replace_existing=True,
        )
        log.info(f"scheduled catch-up underfill check for event {event_id} (missed a check to downtime)")


async def fire_underfill(event_id: str, hours_before: int, resurface: bool = False) -> None:
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

    if event_time <= datetime.now(timezone.utc):
        log.info(f"fire_underfill: event {event_id} already started; skipping")
        return

    if sesh_message_id is not None:
        rsvps = await fetch_sesh_rsvps(_bot, sesh_message_id)
        if rsvps is None:
            log.info(f"fire_underfill: sesh message {sesh_message_id} gone for event {event_id}; skipping")
            return
        jump_url = _sesh_jump_url(sesh_message_id)
    else:
        rsvps = await event_rsvps(event_id, None)
        jump_url = await asyncio.to_thread(_card_jump_url, event_id)
        if jump_url is None:
            log.info(f"fire_underfill: no scheduled card for event {event_id}; skipping")
            return
    yes_count = len(rsvps[0])
    target = settings.pod_draft_target_players

    channel = resolve_pod_chat_channel(_bot)
    if channel is None:
        log.warning("fire_underfill: pod-draft-chat channel unavailable")
        return

    nudge = await _find_nudge(channel, jump_url)

    if yes_count >= target:
        if nudge is not None:
            await _safe_delete(nudge)
        log.info(f"T-{hours_before}h check for {event_id}: {yes_count}/{target} Yes; nudge cleared")
        return

    body = build_underfill_message(name, yes_count, target, event_time, jump_url)
    if resurface and nudge is not None:
        await _safe_delete(nudge)
        nudge = None
    if nudge is not None:
        await _safe_edit(nudge, body)
    else:
        await _safe_post(channel, body)
    log.info(f"T-{hours_before}h underfill nudge for {event_id}: {yes_count}/{target} Yes")


async def refresh_underfill_nudge(bot: commands.Bot, sesh_message_id: str, yes_count: int) -> None:
    """Edit the live underfill nudge in place when sesh RSVPs change; delete it once the pod hits
    the target.

    No-op until a check has posted a nudge — this only ever edits or deletes an existing message, never
    creates one.
    """
    loaded = await asyncio.to_thread(_load_event_for_nudge, str(sesh_message_id))
    if loaded is None:
        return
    await _sync_nudge(bot, loaded, _sesh_jump_url(str(sesh_message_id)), yes_count)


async def refresh_underfill_nudge_for_event(bot: commands.Bot, event_id: str, yes_count: int) -> None:
    """Signal-keyed twin of refresh_underfill_nudge, fed the Yes count by the RSVP card handler."""
    loaded = await asyncio.to_thread(_load_event_by_id_for_nudge, event_id)
    if loaded is None:
        return
    jump_url = await asyncio.to_thread(_card_jump_url, event_id)
    if jump_url is None:
        return
    await _sync_nudge(bot, loaded, jump_url, yes_count)


async def _sync_nudge(
    bot: commands.Bot, loaded: tuple[str, datetime, str], jump_url: str, yes_count: int,
) -> None:
    name, event_time, status = loaded
    if status != "pending":
        return

    channel = resolve_pod_chat_channel(bot)
    if channel is None:
        return

    nudge = await _find_nudge(channel, jump_url)
    if nudge is None:
        return

    target = settings.pod_draft_target_players
    if yes_count >= target:
        await _safe_delete(nudge)
        return
    body = build_underfill_message(name, yes_count, target, event_time, jump_url)
    await _safe_edit(nudge, body)


def _load_event_for_nudge(sesh_message_id: str) -> tuple[str, datetime, str] | None:
    with SessionLocal() as session:
        event = session.execute(
            select(PodDraftEvent).where(PodDraftEvent.sesh_message_id == sesh_message_id)
        ).scalar_one_or_none()
        if event is None:
            return None
        return event.name, event.event_time, event.socket_status


def _load_event_by_id_for_nudge(event_id: str) -> tuple[str, datetime, str] | None:
    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is None:
            return None
        return event.name, event.event_time, event.socket_status


async def _find_nudge(channel: discord.abc.Messageable, signup_url: str) -> discord.Message | None:
    """The bot's own underfill nudge for an event, located by the signup link it carries."""
    try:
        async for message in channel.history(limit=NUDGE_SEARCH_LIMIT):
            if message.author.id == _bot.user.id and signup_url in message.content:
                return message
    except discord.HTTPException:
        log.warning("could not scan pod-draft-chat channel for the underfill nudge", exc_info=True)
    return None


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


def _sesh_jump_url(sesh_message_id: str) -> str:
    return (
        f"https://discord.com/channels/{settings.discord_guild_id}"
        f"/{settings.pod_draft_channel_id}/{sesh_message_id}"
    )


def _card_jump_url(event_id: str) -> str | None:
    """Jump link to the scheduled card that created this pod, or None for a pod with no card."""
    with SessionLocal() as session:
        row = session.execute(
            select(PodSignal.guild_id, PodSignal.channel_id, PodSignal.message_id).where(
                PodSignal.event_id == event_id, PodSignal.kind == KIND_SCHEDULED
            )
        ).first()
    if row is None:
        return None
    guild_id, channel_id, message_id = row
    return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
