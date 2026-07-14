"""Bot-native on-demand pod creation, shared by the daily poll and /pod-queue.

Two layers:
  - sync SQLAlchemy CRUD over pod_signals / pod_signal_members (run via asyncio.to_thread)
  - async Discord orchestration: create the thread + PodDraftEvent and open the Draftmancer lobby
    (now, or armed for a slot time) without any sesh coupling.

`fire_reminder` is sesh-only (it re-parses the sesh embed), so open_ondemand_lobby reimplements the
lobby-open reading the roster back off the signal. Fire is claimed atomically (UPDATE … WHERE
status='open') so concurrent clicks or a restart mid-fire can't create two pods for one slot.

Signals never close to signups while a pod can still happen: a fired signal keeps accepting joins
(over-signups cover unexpected drops), and only an expired one — its slot time passed unfired —
refuses, enforced here in the DB so a persistent button that outlives it is inert on click.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import discord
from discord.ext import commands
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from bot import emojis
from bot.config import settings
from bot.database import SessionLocal
from bot.models import Player, PodDraftEvent, PodDraftParticipant, PodSignal, PodSignalMember
from bot.services import pod_signals
from bot.services.pod_draft_manager import start_manager
from bot.services.pod_drafts import draftmancer_url_for, record_ondemand_event
from bot.services.pod_schedule import highest_event_number
from bot.services.pod_signals import SCHEDULE_TZ, slot_event_time
from bot.tasks.pod_draft_reminder import schedule_team_vote_offer


log = logging.getLogger(__name__)

REMINDER_LEAD_MIN = 10


@dataclass(frozen=True)
class SignalState:
    signal_id: str
    kind: str
    bucket: str
    status: str
    count: int
    slot_time: datetime | None
    event_id: str | None


@dataclass(frozen=True)
class ToggleResult:
    state: SignalState
    names: list[str]
    joined: bool
    changed: bool
    closed: bool
    first_contact: bool = False


def create_poll_signals(
    session: Session, *, guild_id: str, channel_id: str, message_id: str, signal_date: date,
) -> list[tuple[str, datetime]]:
    """Insert the EU + NA poll rows; return (signal_id, slot_time) per row so the caller arms expiry."""
    created: list[tuple[str, datetime]] = []
    for bucket in pod_signals.POLL_BUCKETS:
        slot_time = slot_event_time(signal_date, bucket.key)
        signal = PodSignal(
            kind=pod_signals.KIND_POLL,
            bucket=bucket.key,
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            signal_date=signal_date,
            slot_time=slot_time,
        )
        session.add(signal)
        session.flush()
        created.append((signal.id, slot_time))
    return created


def create_poll_signals_sync(
    *, guild_id: str, channel_id: str, message_id: str, signal_date: date,
) -> list[tuple[str, datetime]]:
    with SessionLocal() as session:
        created = create_poll_signals(
            session, guild_id=guild_id, channel_id=channel_id, message_id=message_id, signal_date=signal_date,
        )
        session.commit()
        return created


def create_queue_signal_sync(
    *, guild_id: str, channel_id: str, message_id: str, signal_date: date, opened_by: str,
) -> str:
    with SessionLocal() as session:
        signal = PodSignal(
            kind=pod_signals.KIND_QUEUE,
            bucket=pod_signals.QUEUE_BUCKET,
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            signal_date=signal_date,
            opened_by=opened_by,
        )
        session.add(signal)
        session.commit()
        return signal.id


def toggle_member(
    session: Session, message_id: str, bucket: str, discord_user_id: str, display_name: str,
    action: str = "toggle",
) -> ToggleResult | None:
    """Change the user's membership of a bucket. `action` is 'toggle' (poll), 'join', or 'leave'
    (queue). Returns None when no such signal exists; a closed result (no mutation) when the signal
    has expired. A fired signal still accepts joins — over-signups ride along and are in the roster
    when the lobby opens. `joined` is True only on a fresh add; `changed` is True when the roster
    actually moved. Bumps last_activity_at on an add so queue teardown resets. Does not commit."""
    signal = _signal_by_message_bucket(session, message_id, bucket)
    if signal is None:
        return None
    if signal.status == pod_signals.STATUS_EXPIRED:
        names = _member_names(session, signal.id)
        return ToggleResult(_state(signal, len(names)), names, joined=False, changed=False, closed=True)

    existing = session.execute(
        select(PodSignalMember).where(
            PodSignalMember.signal_id == signal.id,
            PodSignalMember.discord_user_id == discord_user_id,
        )
    ).scalar_one_or_none()
    add = existing is None if action == "toggle" else action == "join"
    joined = changed = first_contact = False
    if add and existing is None:
        first_contact = not _has_pod_history(session, discord_user_id)
        session.add(PodSignalMember(
            signal_id=signal.id, discord_user_id=discord_user_id, display_name=display_name,
        ))
        signal.last_activity_at = datetime.now(timezone.utc)
        joined = changed = True
    elif not add and existing is not None:
        session.delete(existing)
        changed = True
    session.flush()
    names = _member_names(session, signal.id)
    return ToggleResult(
        _state(signal, len(names)), names,
        joined=joined, changed=changed, closed=False, first_contact=first_contact,
    )


def toggle_member_sync(
    message_id: str, bucket: str, discord_user_id: str, display_name: str, action: str = "toggle",
) -> ToggleResult | None:
    with SessionLocal() as session:
        result = toggle_member(session, message_id, bucket, discord_user_id, display_name, action)
        session.commit()
        return result


def claim_fire(session: Session, signal_id: str) -> bool:
    """Atomically flip status open→fired; True only for the caller that won the race. No commit."""
    result = session.execute(
        update(PodSignal)
        .where(PodSignal.id == signal_id, PodSignal.status == pod_signals.STATUS_OPEN)
        .values(status=pod_signals.STATUS_FIRED)
    )
    return result.rowcount == 1


def claim_fire_sync(signal_id: str) -> bool:
    with SessionLocal() as session:
        claimed = claim_fire(session, signal_id)
        session.commit()
        return claimed


def release_fire_sync(signal_id: str) -> None:
    """Revert a claimed fire back to open when pod creation fails, so it can fire again."""
    with SessionLocal() as session:
        session.execute(
            update(PodSignal)
            .where(PodSignal.id == signal_id, PodSignal.status == pod_signals.STATUS_FIRED)
            .values(status=pod_signals.STATUS_OPEN)
        )
        session.commit()


def claim_nudge_sync(signal_id: str, quiet_minutes: int) -> bool:
    """Atomically claim the one almost-full nudge a signal gets. True only for a still-open signal
    that is older than the quiet window and hasn't nudged yet, so fast-filling queues stay silent
    and concurrent joins can't double-ping."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=quiet_minutes)
    with SessionLocal() as session:
        result = session.execute(
            update(PodSignal)
            .where(
                PodSignal.id == signal_id,
                PodSignal.status == pod_signals.STATUS_OPEN,
                PodSignal.nudged_at.is_(None),
                PodSignal.created_at <= cutoff,
            )
            .values(nudged_at=datetime.now(timezone.utc))
        )
        session.commit()
        return result.rowcount == 1


def link_event_sync(signal_id: str, event_id: str) -> None:
    with SessionLocal() as session:
        session.execute(
            update(PodSignal).where(PodSignal.id == signal_id).values(event_id=event_id)
        )
        session.commit()


def expire_signal_sync(signal_id: str) -> bool:
    """Flip an open signal to expired; True only if it was still open."""
    with SessionLocal() as session:
        result = session.execute(
            update(PodSignal)
            .where(PodSignal.id == signal_id, PodSignal.status == pod_signals.STATUS_OPEN)
            .values(status=pod_signals.STATUS_EXPIRED)
        )
        session.commit()
        return result.rowcount == 1


def poll_exists_for_date_sync(signal_date: date) -> bool:
    with SessionLocal() as session:
        return session.execute(
            select(PodSignal.id).where(
                PodSignal.kind == pod_signals.KIND_POLL, PodSignal.signal_date == signal_date
            ).limit(1)
        ).scalar_one_or_none() is not None


def event_thread_id_sync(event_id: str) -> str | None:
    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        return event.discord_thread_id if event else None


def signal_message_ref_sync(signal_id: str) -> tuple[str, str] | None:
    with SessionLocal() as session:
        row = session.execute(
            select(PodSignal.channel_id, PodSignal.message_id).where(PodSignal.id == signal_id)
        ).first()
    return (row[0], row[1]) if row else None


def poll_snapshot_sync(message_id: str) -> list[tuple[str, str, int, datetime | None, list[str]]]:
    """(bucket, status, count, slot_time, member names) per poll slot on a message, in POLL_BUCKETS order."""
    order = {bucket.key: i for i, bucket in enumerate(pod_signals.POLL_BUCKETS)}
    with SessionLocal() as session:
        signals = session.execute(
            select(PodSignal).where(PodSignal.message_id == message_id, PodSignal.kind == pod_signals.KIND_POLL)
        ).scalars().all()
        rows = []
        for s in signals:
            names = _member_names(session, s.id)
            rows.append((s.bucket, s.status, len(names), s.slot_time, names))
    rows.sort(key=lambda r: order.get(r[0], 99))
    return rows


def roster_for_event_sync(event_id: str) -> list[tuple[str, str]]:
    """(discord_user_id, display_name) for the signal that created this pod, in join order."""
    with SessionLocal() as session:
        signal = session.execute(
            select(PodSignal).where(PodSignal.event_id == event_id)
        ).scalar_one_or_none()
        if signal is None:
            return []
        rows = session.execute(
            select(PodSignalMember.discord_user_id, PodSignalMember.display_name)
            .where(PodSignalMember.signal_id == signal.id)
            .order_by(PodSignalMember.created_at)
        ).all()
        return [(did, name) for did, name in rows]


def ondemand_event_name_sync(set_code: str, event_time: datetime) -> str:
    """The standard `SET Pod Draft #N - date` name, numbered after the set's highest existing pod.
    Gaps against numbers the weekly schedule has reserved but not yet created are fine."""
    with SessionLocal() as session:
        names = session.execute(
            select(PodDraftEvent.name).where(PodDraftEvent.set_code == set_code.upper())
        ).scalars()
        number = highest_event_number(names) + 1
    return f"{set_code} Pod Draft #{number} - {event_time.astimezone(SCHEDULE_TZ):%b %-d}"


async def launch_from_signal(
    bot: commands.Bot, signal_id: str, *, set_code: str, event_time: datetime,
    name: str, open_now: bool,
) -> str | None:
    """Create the thread + PodDraftEvent for a claimed signal, then open (or arm) the lobby. Returns
    the event id, or None if the coordination channel is unreachable. Participants are not pre-seeded:
    the live Draftmancer session is authoritative, matching record_mock_event.

    An open-now pod skips the anchor message — the lobby-open post inside the thread is the whole
    announcement. A scheduled pod anchors its thread on the message carrying the start time."""
    channel = await _fetch_text_channel(bot, settings.pod_draft_channel_id)
    if channel is None:
        log.error(f"launch_from_signal: coordination channel {settings.pod_draft_channel_id} unreachable")
        return None

    try:
        if open_now:
            thread = await channel.create_thread(name=name[:100], type=discord.ChannelType.public_thread)
        else:
            unix = int(event_time.timestamp())
            intro = f"🚀 **{name}** is set for <t:{unix}:F> (<t:{unix}:R>)."
            anchor = await channel.send(intro)
            thread = await anchor.create_thread(name=name[:100])
    except discord.HTTPException:
        log.warning("launch_from_signal: could not create pod thread", exc_info=True)
        return None

    def _create() -> str:
        with SessionLocal() as session:
            event = record_ondemand_event(
                session, set_code=set_code, event_time=event_time, name=name,
                discord_thread_id=str(thread.id),
            )
            session.commit()
            return event.id

    event_id = await asyncio.to_thread(_create)
    await asyncio.to_thread(link_event_sync, signal_id, event_id)

    if open_now:
        await open_ondemand_lobby(bot, event_id)
    else:
        _arm_open(bot, event_id, event_time)
        schedule_team_vote_offer(bot.pod_scheduler, event_id, event_time)
    return event_id


async def open_ondemand_lobby(bot: commands.Bot, event_id: str) -> None:
    """Sesh-less analogue of fire_reminder: post the Draftmancer link, ping the roster, start_manager."""
    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is None:
            log.warning(f"open_ondemand_lobby: event {event_id} not found")
            return
        if event.socket_status not in ("pending", "reminded"):
            log.info(f"open_ondemand_lobby: event {event_id} is {event.socket_status}; skipping")
            return
        thread_id = int(event.discord_thread_id)
        session_id = event.draftmancer_session
        set_code = event.set_code
        event_name = event.name

    roster = await asyncio.to_thread(roster_for_event_sync, event_id)
    display_names = [name for _, name in roster]
    draftmancer_url = draftmancer_url_for(session_id)

    thread = await _fetch_thread(bot, thread_id)
    if thread is None:
        log.warning(f"open_ondemand_lobby: thread {thread_id} unreachable")
        return

    mention_block = " ".join(f"<@{did}>" for did, _ in roster)
    body = (
        f"{emojis.get('draftmancer')} Lobby opening now!\n"
        f"**Join the Draftmancer session:** <{draftmancer_url}>\n"
        "Set your Arena Name (e.g., `ArenaID#12345`) as your name in Draftmancer so pairings work smoothly."
        + (f"\n\n{mention_block}" if mention_block else "")
    )
    try:
        await thread.send(body, allowed_mentions=discord.AllowedMentions(users=True))
    except discord.HTTPException:
        log.warning(f"open_ondemand_lobby: could not post in thread {thread_id}", exc_info=True)
        return

    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is not None and event.socket_status == "pending":
            event.socket_status = "reminded"
            session.commit()

    manager = await start_manager(
        bot, event_id, session_id, thread_id, set_code, len(display_names),
        event_name=event_name, draftmancer_url=draftmancer_url, rsvps_yes=display_names,
    )
    if manager is not None:
        manager.arm_team_vote_offer(len(display_names))


def _arm_open(bot: commands.Bot, event_id: str, event_time: datetime) -> None:
    scheduler = getattr(bot, "pod_scheduler", None)
    if scheduler is None:
        log.error(f"_arm_open: pod_scheduler missing; open for {event_id} lost")
        return
    now = datetime.now(timezone.utc)
    run_at = event_time - timedelta(minutes=REMINDER_LEAD_MIN)
    if run_at < now:
        run_at = now + timedelta(seconds=2)
    scheduler.add_job(
        open_ondemand_lobby, "date", run_date=run_at, args=[bot, event_id],
        id=f"pod-ondemand-open-{event_id}", replace_existing=True,
    )
    log.info(f"armed on-demand lobby open for {event_id} at {run_at.isoformat()}")


def arm_slot_expiry(bot: commands.Bot, signal_id: str, slot_time: datetime) -> None:
    scheduler = getattr(bot, "pod_scheduler", None)
    if scheduler is None:
        return
    scheduler.add_job(
        fire_slot_expiry, "date", run_date=slot_time, args=[signal_id],
        id=f"pod-slot-expiry-{signal_id}", replace_existing=True,
    )


async def fire_slot_expiry(signal_id: str) -> None:
    """At slot time, close an unfired poll slot. DB-only — its button stays but toggle_member_sync
    now refuses it, so a late click gets a graceful ephemeral and never joins a dead slot."""
    if await asyncio.to_thread(expire_signal_sync, signal_id):
        log.info(f"poll slot {signal_id} expired unfired")


def arm_queue_teardown(bot: commands.Bot, signal_id: str, teardown_time: datetime) -> None:
    scheduler = getattr(bot, "pod_scheduler", None)
    if scheduler is None:
        return
    scheduler.add_job(
        fire_queue_teardown, "date", run_date=teardown_time, args=[signal_id],
        id=f"pod-queue-teardown-{signal_id}", replace_existing=True,
    )


async def fire_queue_teardown(signal_id: str) -> None:
    """Close an idle queue: swap the card for its closed state, which carries no buttons."""
    from bot.commands.pod_queue import PodQueueView, queue_role_mention

    if not await asyncio.to_thread(expire_signal_sync, signal_id):
        return
    ref = await asyncio.to_thread(signal_message_ref_sync, signal_id)
    if ref is None or _bot is None:
        return
    channel_id, message_id = ref
    channel = await _fetch_text_channel(_bot, int(channel_id))
    if channel is None:
        return
    try:
        message = await channel.fetch_message(int(message_id))
        closed_view = PodQueueView(role_mention=queue_role_mention(channel.guild), closed=True)
        await message.edit(view=closed_view)
    except discord.HTTPException:
        log.warning(f"fire_queue_teardown: could not edit queue message {message_id}", exc_info=True)


async def rearm_signals(bot: commands.Bot) -> None:
    """Startup sweep: re-arm slot expiries, on-demand lobby opens, and queue teardowns from the DB so a
    restart loses nothing. Past-due opens fire immediately; past-due open signals are expired."""
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        signals = session.execute(
            select(PodSignal).where(PodSignal.status.in_([pod_signals.STATUS_OPEN, pod_signals.STATUS_FIRED]))
        ).scalars().all()
        pending = [
            (s.id, s.kind, s.status, s.slot_time, s.last_activity_at, s.event_id) for s in signals
        ]

    for signal_id, kind, status, slot_time, last_activity, event_id in pending:
        if status == pod_signals.STATUS_FIRED and event_id is not None:
            if _rearm_open_if_pending(bot, event_id):
                continue
        if status != pod_signals.STATUS_OPEN:
            continue
        if kind == pod_signals.KIND_POLL and slot_time is not None:
            if slot_time <= now:
                await asyncio.to_thread(expire_signal_sync, signal_id)
            else:
                arm_slot_expiry(bot, signal_id, slot_time)
        elif kind == pod_signals.KIND_QUEUE:
            teardown = pod_signals.teardown_at(last_activity, settings.pod_queue_inactivity_minutes)
            if teardown <= now:
                await asyncio.to_thread(expire_signal_sync, signal_id)
            else:
                arm_queue_teardown(bot, signal_id, teardown)


def _rearm_open_if_pending(bot: commands.Bot, event_id: str) -> bool:
    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is None or event.socket_status not in ("pending", "reminded"):
            return False
        event_time = event.event_time
    _arm_open(bot, event_id, event_time)
    schedule_team_vote_offer(bot.pod_scheduler, event_id, event_time)
    return True


_bot: commands.Bot | None = None


def init_launch(bot: commands.Bot) -> None:
    """Wire the bot reference so scheduler callbacks (queue teardown) can edit Discord messages."""
    global _bot
    _bot = bot


def _has_pod_history(session: Session, discord_user_id: str) -> bool:
    """Whether this Discord user has ever joined a pod signal or played in a pod. Gates the one-time
    first-contact tip; must run before the member row is inserted."""
    prior_signal = session.execute(
        select(PodSignalMember.id)
        .where(PodSignalMember.discord_user_id == discord_user_id)
        .limit(1)
    ).scalar_one_or_none()
    if prior_signal is not None:
        return True
    prior_participation = session.execute(
        select(PodDraftParticipant.id)
        .join(Player, Player.id == PodDraftParticipant.player_id)
        .where(Player.discord_id == discord_user_id)
        .limit(1)
    ).scalar_one_or_none()
    return prior_participation is not None


def _signal_by_message_bucket(session: Session, message_id: str, bucket: str) -> PodSignal | None:
    return session.execute(
        select(PodSignal).where(PodSignal.message_id == message_id, PodSignal.bucket == bucket)
    ).scalar_one_or_none()


def _member_names(session: Session, signal_id: str) -> list[str]:
    return list(session.execute(
        select(PodSignalMember.display_name)
        .where(PodSignalMember.signal_id == signal_id)
        .order_by(PodSignalMember.created_at)
    ).scalars().all())


def _state(signal: PodSignal, count: int) -> SignalState:
    return SignalState(
        signal.id, signal.kind, signal.bucket, signal.status, count, signal.slot_time, signal.event_id,
    )


async def _fetch_thread(bot: commands.Bot, thread_id: int) -> discord.Thread | None:
    try:
        channel = await bot.fetch_channel(thread_id)
    except discord.HTTPException as e:
        log.warning(f"fetch_channel({thread_id}) failed: {e}")
        return None
    return channel if isinstance(channel, discord.Thread) else None


async def _fetch_text_channel(bot: commands.Bot, channel_id: int) -> discord.TextChannel | None:
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.HTTPException as e:
            log.warning(f"fetch_channel({channel_id}) failed: {e}")
            return None
    return channel if isinstance(channel, discord.TextChannel) else None
