"""Time-anchored recruiting nudge fired by APScheduler date jobs, plus live RSVP-driven updates.

The check offsets live in POD_UNDERFILL_CHECK_HOURS (default 3, 2, 1). T-3h posts a silent nudge in the
pod-draft-chat channel carrying the signup link back to the RSVP message; T-2h is the catch-up beat for
a pod born after T-3h; T-1h (the min offset) deletes and reposts the nudge so it resurfaces near the
event, and pings the slot role when the pod is close to its aim — see `_nudge_ping_role`. Every other
post stays silent. Each check re-fetches the Yes list at fire time — the sesh embed for sesh-born pods,
the signal members for card-born pods.

The nudge is one living message: it is never deleted on a player count, so an 8 -> 7 drop flips the text
back to "looking for 1 more" instead of vanishing, and reaching the aim shows the ready line silently.
It is deleted only when the pod starts (the lobby opens) via `clear_underfill_nudge`. While the nudge is
up, RSVP changes keep the count current. The nudge is located by scanning channel history for the bot's
own message carrying the signup link — nothing is persisted.
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
from bot.services.pod_roles import find_role
from bot.services.pod_schedule import build_underfill_message, slot_for_event_time
from bot.services.pod_signals import KIND_SCHEDULED
from bot.tasks.pod_draft_reminder import event_rsvps, fetch_sesh_rsvps, register_underfill_clear


NUDGE_SEARCH_LIMIT = 100
CATCH_UP_DELAY_S = 5

log = logging.getLogger(__name__)

_bot: commands.Bot | None = None


def init_underfill(bot: commands.Bot) -> None:
    """Wire the bot reference so the APScheduler callbacks can dispatch Discord work."""
    global _bot
    _bot = bot
    register_underfill_clear(clear_underfill_nudge)


def schedule_underfill_checks(scheduler, event_id: str, event_time: datetime, created_at: datetime) -> None:
    """Arm the T-3h / T-2h / T-1h checks, firing an immediate catch-up for any beat missed to downtime.

    A past beat is only caught up when the event predates it (`created_at <= run_at`): that means the
    beat was missed to downtime, not that the pod was created short-notice. A short-notice pod born after
    T-3h simply skips the silent step it was never around for and picks up its first future beat.

    The catch-up carries the most recent missed beat's offset, so it inherits that beat's behaviour — a
    caught-up T-1h resurfaces and can ping, an earlier caught-up beat stays silent.
    """
    check_hours = settings.pod_underfill_check_hours_tuple
    now = datetime.now(timezone.utc)
    resurface_hours = min(check_hours)
    catch_up_hours: int | None = None
    for hours in check_hours:
        run_at = event_time - timedelta(hours=hours)
        job_id = f"pod-underfill{hours}-{event_id}"
        if run_at <= now:
            with contextlib.suppress(Exception):
                scheduler.remove_job(job_id)
            if event_time > now and created_at <= run_at:
                catch_up_hours = hours
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

    if catch_up_hours is not None:
        scheduler.add_job(
            fire_underfill,
            "date",
            run_date=now + timedelta(seconds=CATCH_UP_DELAY_S),
            args=[event_id, catch_up_hours, catch_up_hours == resurface_hours],
            id=f"pod-underfill-catchup-{event_id}",
            replace_existing=True,
        )
        log.info(f"scheduled T-{catch_up_hours}h catch-up underfill check for {event_id} (missed to downtime)")


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

    body = build_underfill_message(name, yes_count, target, event_time, jump_url)
    if resurface and nudge is not None:
        await _safe_delete(nudge)
        nudge = None
    if nudge is not None:
        await _safe_edit(nudge, body)
    else:
        role = _nudge_ping_role(channel, event_time, yes_count, hours_before)
        post_body = f"{body} {role.mention}" if role is not None else body
        await _safe_post(channel, post_body, mention_role=role is not None)
    log.info(f"T-{hours_before}h underfill nudge for {event_id}: {yes_count}/{target} Yes")


async def refresh_underfill_nudge(bot: commands.Bot, sesh_message_id: str, yes_count: int) -> None:
    """Edit the live underfill nudge in place when sesh RSVPs change, flipping between the count line and
    the ready line as the count crosses the aim.

    No-op until a check has posted a nudge — this only ever edits an existing message, never creates or
    deletes one; `clear_underfill_nudge` owns removal at lobby open.
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


async def clear_underfill_nudge(bot: commands.Bot, event_id: str) -> None:
    """Delete the standing underfill nudge when the pod starts. Called from both lobby-open paths
    (card-born `open_ondemand_lobby`, sesh-born `fire_reminder`). No-op when no nudge is up."""
    jump_url = await asyncio.to_thread(_jump_url_for_event, event_id)
    if jump_url is None:
        return
    channel = resolve_pod_chat_channel(bot)
    if channel is None:
        return
    nudge = await _find_nudge(channel, jump_url)
    if nudge is not None:
        await _safe_delete(nudge)


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


def _nudge_ping_role(
    channel: discord.abc.Messageable, event_time: datetime, yes_count: int, hours_before: int,
) -> discord.Role | None:
    """The slot role to ping on a fresh nudge, or None to stay silent.

    Pinging is gated to the check hours in POD_UNDERFILL_PING_HOURS and to a pod that is close to its
    aim — it needs at most POD_UNDERFILL_PING_CLOSE_GAP more players. A pod still far from the aim, or one
    already at it, stays silent. Off-grid pods resolve no slot role and fall through to silent, so day-of
    launcher pods keep their own launcher ping and never double-fire here.
    """
    if hours_before not in settings.pod_underfill_ping_hours_set:
        return None
    needed = settings.pod_draft_target_players - yes_count
    if needed <= 0 or needed > settings.pod_underfill_ping_close_gap:
        return None
    slot = slot_for_event_time(event_time)
    if slot is None:
        return None
    guild = getattr(channel, "guild", None)
    return find_role(guild, slot.mentions.lstrip("@"))


async def _safe_post(channel: discord.abc.Messageable, body: str, *, mention_role: bool = False) -> None:
    allowed = discord.AllowedMentions(roles=True) if mention_role else discord.AllowedMentions.none()
    try:
        await channel.send(body, allowed_mentions=allowed)
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


def _jump_url_for_event(event_id: str) -> str | None:
    """The signup link the event's nudge carries — the sesh message for sesh-born pods, the scheduled
    card for card-born pods. None when neither exists."""
    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is None:
            return None
        sesh_message_id = event.sesh_message_id
    if sesh_message_id is not None:
        return _sesh_jump_url(str(sesh_message_id))
    return _card_jump_url(event_id)


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
