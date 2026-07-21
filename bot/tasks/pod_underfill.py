"""Time-anchored recruiting nudge fired by APScheduler date jobs, plus live RSVP-driven updates.

The check offsets live in POD_UNDERFILL_CHECK_HOURS (default 3, 2, 1). T-3h posts a silent nudge in the
pod-draft-chat channel carrying the signup link back to the RSVP message; T-2h is the catch-up beat for
a pod born after T-3h; T-1h (the min offset) deletes and reposts the nudge so it resurfaces near the
event, and pings the slot role when the pod is close to its aim — see `_nudge_ping_role`. Every other
post stays silent. Each check re-fetches the Yes list at fire time — the sesh embed for sesh-born pods,
the signal members for card-born pods.

Unfired launcher slots run the same beats through `fire_slot_underfill`, aiming at the fire threshold
and linking to the launcher — the slot's signup surface until it fires. On fire the slot's nudge is
cleared and recruiting hands over to the scheduled card's own checks, now aiming at the target.

The nudge is one living message: it is never deleted on a player count, so an 8 -> 7 drop flips the text
back to "looking for 1 more" instead of vanishing, and reaching the aim shows the ready line silently.
It is deleted only when the pod starts (the lobby opens) via `clear_underfill_nudge`, or for a launcher
slot when it fires or expires via `clear_slot_nudge`. While the nudge is up, RSVP changes keep the count
current. The nudge is located by scanning channel history for the bot's own message carrying the signup
link (plus the pod name for launcher slots, which share one launcher URL) — nothing is persisted.

A pod pushes at most one last-call ping, claimed on `pod_signals.last_call_pinged_at`, so a caught-up
T-1h beat after a restart can never ping the slot role twice.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands
from sqlalchemy import select, update

from bot.config import settings
from bot.database import SessionLocal
from bot.discord_helpers import resolve_pod_chat_channel
from bot.models import PodDraftEvent, PodSignal
from bot.services.pod_roles import find_role
from bot.services.pod_schedule import build_underfill_message, short_event_name
from bot.services.pod_signals import KIND_SCHEDULED, STATUS_OPEN, slot_role_name_for_event_time
from bot.services.pod_slot import pod_display_name
from bot.sets import active_set_code
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
    """Arm the scheduled card's T-3h / T-2h / T-1h checks — see `_arm_underfill_beats`."""
    _arm_underfill_beats(scheduler, fire_underfill, event_id, "pod-underfill", event_time, created_at)


def schedule_slot_underfill_checks(scheduler, signal_id: str, slot_time: datetime, created_at: datetime) -> None:
    """Arm an unfired launcher slot's T-3h / T-2h / T-1h checks — see `_arm_underfill_beats`."""
    _arm_underfill_beats(scheduler, fire_slot_underfill, signal_id, "pod-slot-underfill", slot_time, created_at)


def _arm_underfill_beats(
    scheduler, fire, key: str, id_prefix: str, event_time: datetime, created_at: datetime,
) -> None:
    """Arm the T-3h / T-2h / T-1h checks, firing an immediate catch-up for any beat missed to downtime.

    A past beat is only caught up when the pod predates it (`created_at <= run_at`): that means the
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
        job_id = f"{id_prefix}{hours}-{key}"
        if run_at <= now:
            with contextlib.suppress(Exception):
                scheduler.remove_job(job_id)
            if event_time > now and created_at <= run_at:
                catch_up_hours = hours
            continue
        scheduler.add_job(
            fire,
            "date",
            run_date=run_at,
            args=[key, hours, hours == resurface_hours],
            id=job_id,
            replace_existing=True,
        )
        log.info(f"scheduled T-{hours}h underfill check for {key} at {run_at.isoformat()}")

    if catch_up_hours is not None:
        scheduler.add_job(
            fire,
            "date",
            run_date=now + timedelta(seconds=CATCH_UP_DELAY_S),
            args=[key, catch_up_hours, catch_up_hours == resurface_hours],
            id=f"{id_prefix}-catchup-{key}",
            replace_existing=True,
        )
        log.info(f"scheduled T-{catch_up_hours}h catch-up underfill check for {key} (missed to downtime)")


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
        signal_id = None
        if sesh_message_id is None:
            signal_id = await asyncio.to_thread(_scheduled_signal_id, event_id)
        role = await _claimed_ping_role(channel, signal_id, event_time, yes_count, target, hours_before)
        post_body = f"{body} {role.mention}" if role is not None else body
        await _safe_post(channel, post_body, mention_role=role is not None)
    log.info(f"T-{hours_before}h underfill nudge for {event_id}: {yes_count}/{target} Yes")


async def fire_slot_underfill(signal_id: str, hours_before: int, resurface: bool = False) -> None:
    """The launcher-slot twin of `fire_underfill`, running while the slot is still open: it aims at the
    fire threshold and its signup link is the launcher. A fired or expired slot is skipped — the card's
    own checks recruit a fired slot's last seats. An empty slot stays silent: there is no pod-in-waiting
    to rally around, and the launcher already advertises the open slot."""
    if _bot is None:
        log.error(f"fire_slot_underfill for {signal_id}: bot reference is not initialised")
        return
    slot = await asyncio.to_thread(_load_slot_for_nudge, signal_id)
    if slot is None:
        log.warning(f"fire_slot_underfill: pod_signal {signal_id} not found")
        return
    if slot.status != STATUS_OPEN:
        log.info(f"fire_slot_underfill: slot {signal_id} is {slot.status}; skipping")
        return
    if slot.slot_time <= datetime.now(timezone.utc):
        return
    aim = settings.pod_signal_fire_threshold
    if slot.count == 0 or slot.count >= aim:
        log.info(f"fire_slot_underfill: slot {signal_id} has {slot.count} signups; skipping")
        return

    channel = resolve_pod_chat_channel(_bot)
    if channel is None:
        log.warning("fire_slot_underfill: pod-draft-chat channel unavailable")
        return

    name = pod_display_name(active_set_code(), slot.slot_time)
    nudge = await _find_nudge(channel, slot.jump_url, marker=_name_marker(name))

    body = build_underfill_message(name, slot.count, aim, slot.slot_time, slot.jump_url)
    if resurface and nudge is not None:
        await _safe_delete(nudge)
        nudge = None
    if nudge is not None:
        await _safe_edit(nudge, body)
    else:
        role = await _claimed_ping_role(channel, signal_id, slot.slot_time, slot.count, aim, hours_before)
        post_body = f"{body} {role.mention}" if role is not None else body
        await _safe_post(channel, post_body, mention_role=role is not None)
    log.info(f"T-{hours_before}h slot underfill nudge for {signal_id}: {slot.count}/{aim} signed up")


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


async def refresh_slot_nudge(bot: commands.Bot, signal_id: str) -> None:
    """Edit the live slot nudge in place when launcher signups change, keeping the count current
    between beats. Only ever edits an existing message — `fire_slot_underfill` owns creation and
    `clear_slot_nudge` owns removal."""
    slot = await asyncio.to_thread(_load_slot_for_nudge, signal_id)
    if slot is None or slot.status != STATUS_OPEN:
        return
    channel = resolve_pod_chat_channel(bot)
    if channel is None:
        return
    name = pod_display_name(active_set_code(), slot.slot_time)
    nudge = await _find_nudge(channel, slot.jump_url, marker=_name_marker(name))
    if nudge is None:
        return
    aim = settings.pod_signal_fire_threshold
    body = build_underfill_message(name, slot.count, aim, slot.slot_time, slot.jump_url)
    await _safe_edit(nudge, body)


async def clear_slot_nudge(bot: commands.Bot, signal_id: str) -> None:
    """Delete a launcher slot's standing nudge when its window ends: the slot fired into a card (whose
    own checks take over) or expired unfired. No-op when no nudge is up."""
    slot = await asyncio.to_thread(_load_slot_for_nudge, signal_id)
    if slot is None:
        return
    channel = resolve_pod_chat_channel(bot)
    if channel is None:
        return
    name = pod_display_name(active_set_code(), slot.slot_time)
    nudge = await _find_nudge(channel, slot.jump_url, marker=_name_marker(name))
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


@dataclass(frozen=True)
class _SlotNudgeContext:
    status: str
    slot_time: datetime
    count: int
    jump_url: str


def _load_slot_for_nudge(signal_id: str) -> _SlotNudgeContext | None:
    with SessionLocal() as session:
        signal = session.get(PodSignal, signal_id)
        if signal is None or signal.slot_time is None:
            return None
        jump_url = (
            f"https://discord.com/channels/{signal.guild_id}/{signal.channel_id}/{signal.message_id}"
        )
        return _SlotNudgeContext(signal.status, signal.slot_time, len(signal.members), jump_url)


def _name_marker(name: str) -> str:
    """The bolded pod name as the nudge body renders it, disambiguating slot nudges that share the one
    launcher URL."""
    return f"**{short_event_name(name)}**"


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


async def _find_nudge(
    channel: discord.abc.Messageable, signup_url: str, marker: str | None = None,
) -> discord.Message | None:
    """The bot's own underfill nudge for a pod, located by the signup link it carries. `marker` narrows
    the match for launcher slots, whose nudges all link to the one launcher message."""
    try:
        async for message in channel.history(limit=NUDGE_SEARCH_LIMIT):
            if message.author.id != _bot.user.id or signup_url not in message.content:
                continue
            if marker is None or marker in message.content:
                return message
    except discord.HTTPException:
        log.warning("could not scan pod-draft-chat channel for the underfill nudge", exc_info=True)
    return None


async def _claimed_ping_role(
    channel: discord.abc.Messageable, signal_id: str | None, event_time: datetime, yes_count: int,
    aim: int, hours_before: int,
) -> discord.Role | None:
    """`_nudge_ping_role` with the last-call claim on top: the role only survives when this signal has
    not pinged before. Sesh-born pods carry no signal and ping unclaimed."""
    role = _nudge_ping_role(channel, event_time, yes_count, aim, hours_before)
    if role is None:
        return None
    if signal_id is not None and not await asyncio.to_thread(claim_last_call_ping_sync, signal_id):
        return None
    return role


def _nudge_ping_role(
    channel: discord.abc.Messageable, event_time: datetime, yes_count: int, aim: int, hours_before: int,
) -> discord.Role | None:
    """The slot role to ping on a fresh nudge, or None to stay silent.

    Pinging is gated to the check hours in POD_UNDERFILL_PING_HOURS and to a pod that is close to its
    aim — it needs at most POD_UNDERFILL_PING_CLOSE_GAP more players. A pod still far from the aim, or one
    already at it, stays silent. The role resolves off the daily poll buckets, so weekly and launcher
    slots both ping; an off-grid custom time resolves no role and stays silent.
    """
    if hours_before not in settings.pod_underfill_ping_hours_set:
        return None
    needed = aim - yes_count
    if needed <= 0 or needed > settings.pod_underfill_ping_close_gap:
        return None
    role_name = slot_role_name_for_event_time(event_time)
    if role_name is None:
        return None
    guild = getattr(channel, "guild", None)
    return find_role(guild, role_name)


def claim_last_call_ping_sync(signal_id: str) -> bool:
    """Atomically claim the one last-call ping a signal gets, so a caught-up or re-armed T-1h beat can
    never ping the slot role twice for one pod."""
    with SessionLocal() as session:
        result = session.execute(
            update(PodSignal)
            .where(PodSignal.id == signal_id, PodSignal.last_call_pinged_at.is_(None))
            .values(last_call_pinged_at=datetime.now(timezone.utc))
        )
        session.commit()
        return result.rowcount == 1


def _scheduled_signal_id(event_id: str) -> str | None:
    with SessionLocal() as session:
        return session.execute(
            select(PodSignal.id).where(
                PodSignal.event_id == event_id, PodSignal.kind == KIND_SCHEDULED
            )
        ).scalar_one_or_none()


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
