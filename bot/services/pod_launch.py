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
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from bot.config import PRODUCTION_GUILD_ID, settings
from bot.database import SessionLocal
from bot.models import PodDraftEvent, PodSignal, PodSignalMember
from bot.services import pod_format_interest as fi
from bot.services import pod_signals
from bot.services.pod_draft_manager import set_card_cancel_hook, set_card_close_hook, start_manager
from bot.services.pod_drafts import (
    draftmancer_url_for,
    event_member_interests_sync,
    get_flashback_ranking,
    get_format_interests,
    record_ondemand_event,
    set_flashback_ranking,
    set_format_interests,
)
from bot.services.pod_join_button import build_join_view
from bot.services.pod_link_dm import send_lobby_link_dms
from bot.services.pod_signals import SCHEDULE_TZ, slot_event_time
from bot.services.pod_slot import COLLISION_INDEX_RE, next_collision_index, pod_display_name
from bot.tasks.pod_draft_reminder import (
    build_lobby_open_body,
    schedule_roster_reminder,
    schedule_team_vote_offer,
    signal_rsvps_sync,
)
from bot.tasks.pod_underfill import (
    clear_slot_nudge,
    clear_underfill_nudge,
    schedule_slot_underfill_checks,
    schedule_underfill_checks,
)


log = logging.getLogger(__name__)

REMINDER_LEAD_MIN = 10
CARD_CLOSE_WINDOW_H = 48
SLOT_OCCUPANCY_WINDOW = timedelta(hours=2)
TABLE_SUFFIX_SQL_RE = r"Table[[:space:]]+[0-9]+[[:space:]]*$"


@dataclass(frozen=True)
class SignalState:
    signal_id: str
    kind: str
    bucket: str
    status: str
    count: int
    slot_time: datetime | None
    event_id: str | None
    set_code: str | None
    created_at: datetime | None = None
    opened_by: str | None = None
    notify_role: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class ToggleResult:
    state: SignalState
    names: list[str]
    joined: bool
    changed: bool
    closed: bool


@dataclass(frozen=True)
class LeaveResolution:
    """Outcome of the last-player Leave confirmation. `cancelled` when the confirmer was still the only
    member and the queue was closed; `left` when others joined during the prompt so the confirmer was
    just removed and the queue stays open; `gone` when the signal had already closed. `names`, `set_code`,
    `created_at`, `opened_by`, `notify_role`, and `description` re-render the still-open card on the
    `left` path."""
    outcome: str
    names: list[str]
    set_code: str | None
    created_at: datetime | None
    opened_by: str | None
    notify_role: str | None = None
    description: str | None = None


LEAVE_CANCELLED = "cancelled"
LEAVE_LEFT = "left"
LEAVE_GONE = "gone"


@dataclass(frozen=True)
class RsvpResult:
    state: SignalState
    rosters: dict[str, list[str]]
    rsvp: str | None
    joined: bool
    closed: bool
    yes_changed: bool = False
    roster_interests: dict[str, list[tuple[str, tuple[str, ...]]]] | None = None


@dataclass(frozen=True)
class LauncherSlot:
    """One rendered launcher slot. `committed` is a locked scheduled pod the slot reflects: `count`/
    `thread_id`/`slot_time` are read off the event and `names` projects the card's Yes roster read-only
    (empty for sesh pods, which have no signal roster). A lazy slot carries its own poll `signal_id`,
    roster `names`, and `status`."""
    bucket_key: str
    committed: bool
    status: str
    count: int
    slot_time: datetime | None
    names: list[str]
    thread_id: str | None
    signal_id: str | None
    thread_message_id: str | None = None
    interests: tuple[tuple[str, ...], ...] = ()
    set_code: str | None = None


def create_poll_signals(
    session: Session, *, guild_id: str, channel_id: str, message_id: str, signal_date: date,
) -> list[tuple[str, datetime]]:
    """Insert a lazy poll row per open slot of the day; return (signal_id, slot_time) per row so the
    caller arms expiry. A slot whose time already carries a locked scheduled pod is reflected, not
    reopened — it gets no signal here, so the launcher binds to the scheduled card instead of doubling
    it."""
    created: list[tuple[str, datetime]] = []
    for bucket in pod_signals.poll_buckets_for(signal_date):
        slot_time = slot_event_time(signal_date, bucket.key)
        if _event_id_for_slot(session, slot_time) is not None:
            continue
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
    set_code: str | None = None, pairing_mode: str | None = None, seating_mode: str | None = None,
    pick_timer: int | None = None, notify_role: str | None = None, description: str | None = None,
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
            set_code=set_code,
            pairing_mode=pairing_mode,
            seating_mode=seating_mode,
            pick_timer=pick_timer,
            notify_role=notify_role,
            description=description,
        )
        session.add(signal)
        session.commit()
        return signal.id


@dataclass(frozen=True)
class QueuePresets:
    set_code: str | None
    pairing_mode: str | None
    seating_mode: str | None
    pick_timer: int | None


def queue_presets_sync(signal_id: str) -> QueuePresets:
    """The set + pairing / seating / pick-timer chosen in the /draft launcher, applied to the pod once
    its queue fires. All None when the pod was opened without presets (defaults to the active set)."""
    with SessionLocal() as session:
        signal = session.get(PodSignal, signal_id)
        if signal is None:
            return QueuePresets(None, None, None, None)
        return QueuePresets(
            signal.set_code, signal.pairing_mode, signal.seating_mode, signal.pick_timer,
        )


def queue_opener_sync(signal_id: str) -> tuple[datetime | None, str | None]:
    """(opened_at, opened_by) for a queue signal, so a closed card can still credit who opened it."""
    with SessionLocal() as session:
        signal = session.get(PodSignal, signal_id)
        if signal is None:
            return None, None
        return signal.created_at, signal.opened_by


def queue_member_names_sync(signal_id: str) -> list[str]:
    """Display names still in the queue, so a timed-out card keeps showing who was around."""
    with SessionLocal() as session:
        return _member_names(session, signal_id)


def set_discussion_thread_sync(signal_id: str, thread_id: str) -> None:
    with SessionLocal() as session:
        signal = session.get(PodSignal, signal_id)
        if signal is not None:
            signal.discussion_thread_id = thread_id
            session.commit()


def discussion_thread_id_sync(message_id: str) -> str | None:
    """The standalone discussion thread's id for a queue card, keyed by the card message id."""
    with SessionLocal() as session:
        return session.execute(
            select(PodSignal.discussion_thread_id).where(
                PodSignal.message_id == message_id,
                PodSignal.bucket == pod_signals.QUEUE_BUCKET,
            )
        ).scalar_one_or_none()


@dataclass(frozen=True)
class JoinableSignal:
    kind: str
    channel_id: str
    message_id: str
    slot_time: datetime | None
    count: int
    set_code: str | None


def joinable_signals_sync(guild_id: str, *, now: datetime, within: timedelta) -> list[JoinableSignal]:
    """Open queues and soon-to-fire poll slots in the guild — what a /draft caller could join instead
    of starting a fresh pod. Poll slots past `within` from now are too far off to divert to."""
    with SessionLocal() as session:
        signals = session.execute(
            select(PodSignal).where(
                PodSignal.guild_id == guild_id,
                PodSignal.status == pod_signals.STATUS_OPEN,
                PodSignal.kind.in_([pod_signals.KIND_QUEUE, pod_signals.KIND_POLL]),
            ).order_by(PodSignal.created_at)
        ).scalars().all()
        joinable: list[JoinableSignal] = []
        for signal in signals:
            if signal.slot_time is not None and not (now < signal.slot_time <= now + within):
                continue
            joinable.append(JoinableSignal(
                signal.kind, signal.channel_id, signal.message_id, signal.slot_time, len(signal.members),
                signal.set_code,
            ))
        return joinable


def create_scheduled_signal_sync(
    *, guild_id: str, channel_id: str, message_id: str, event_time: datetime,
    pick_timer: int | None = None,
) -> str:
    """A scheduled pod's signal is born fired with the caller linking its event right after: RSVPs
    stay open forever for over-signups and expiry never applies. Pairing and seating live on the
    event; only the pick timer rides the signal, since it is live-only and applied at lobby open."""
    with SessionLocal() as session:
        signal = PodSignal(
            kind=pod_signals.KIND_SCHEDULED,
            bucket=pod_signals.SCHEDULED_BUCKET,
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            signal_date=event_time.astimezone(SCHEDULE_TZ).date(),
            slot_time=event_time,
            status=pod_signals.STATUS_FIRED,
            pick_timer=pick_timer,
        )
        session.add(signal)
        session.commit()
        return signal.id


def scheduled_pick_timer_for_event_sync(event_id: str) -> int | None:
    with SessionLocal() as session:
        return session.execute(
            select(PodSignal.pick_timer).where(
                PodSignal.event_id == event_id, PodSignal.kind == pod_signals.KIND_SCHEDULED
            )
        ).scalar_one_or_none()


def set_rsvp(
    session: Session, message_id: str, discord_user_id: str, display_name: str, rsvp: str,
) -> RsvpResult | None:
    """RSVP on a scheduled card: Yes or Maybe move the member there; No removes their signup entirely,
    since No is not a tracked roster. Clicking the state they already hold is a no-op. `rsvp` in the
    result is the recorded state, None once removed; `joined` is True only when the member freshly
    entered Yes. Scheduled signals are born fired and never expire, so only a stray expired row
    refuses. Does not commit."""
    signal = _scheduled_signal_by_surface(session, message_id)
    if signal is None:
        return None
    if signal.status == pod_signals.STATUS_EXPIRED:
        rosters = _members_by_rsvp(session, signal.id)
        yes_count = len(rosters[pod_signals.RSVP_YES])
        return RsvpResult(
            _state(signal, yes_count), rosters, rsvp=None, joined=False, closed=True,
            roster_interests=_members_by_rsvp_with_interest(session, signal.id),
        )

    existing = session.execute(
        select(PodSignalMember).where(
            PodSignalMember.signal_id == signal.id,
            PodSignalMember.discord_user_id == discord_user_id,
        )
    ).scalar_one_or_none()
    was_yes = existing is not None and existing.rsvp == pod_signals.RSVP_YES
    joined = False
    if rsvp == pod_signals.RSVP_NO:
        recorded: str | None = None
        if existing is not None:
            session.delete(existing)
    else:
        recorded = rsvp
        if existing is None:
            session.add(PodSignalMember(
                signal_id=signal.id, discord_user_id=discord_user_id, display_name=display_name, rsvp=rsvp,
                format_interest=get_format_interests(session, discord_user_id),
            ))
            signal.last_activity_at = datetime.now(timezone.utc)
            joined = rsvp == pod_signals.RSVP_YES
        elif existing.rsvp != rsvp:
            joined = rsvp == pod_signals.RSVP_YES
            existing.rsvp = rsvp
            existing.display_name = display_name
    session.flush()
    rosters = _members_by_rsvp(session, signal.id)
    roster_interests = _members_by_rsvp_with_interest(session, signal.id)
    yes_count = len(rosters[pod_signals.RSVP_YES])
    yes_changed = was_yes != (recorded == pod_signals.RSVP_YES)
    return RsvpResult(
        _state(signal, yes_count), rosters, rsvp=recorded, joined=joined, closed=False,
        yes_changed=yes_changed, roster_interests=roster_interests,
    )


def set_rsvp_sync(
    message_id: str, discord_user_id: str, display_name: str, rsvp: str,
) -> RsvpResult | None:
    with SessionLocal() as session:
        result = set_rsvp(session, message_id, discord_user_id, display_name, rsvp)
        session.commit()
        return result


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
    now = datetime.now(timezone.utc)
    if _lazy_status(signal.status, signal.slot_time, now) == pod_signals.STATUS_EXPIRED:
        names = _member_names(session, signal.id)
        return ToggleResult(_state(signal, len(names)), names, joined=False, changed=False, closed=True)

    existing = session.execute(
        select(PodSignalMember).where(
            PodSignalMember.signal_id == signal.id,
            PodSignalMember.discord_user_id == discord_user_id,
        )
    ).scalar_one_or_none()
    add = existing is None if action == "toggle" else action == "join"
    joined = changed = False
    if add and existing is None:
        session.add(PodSignalMember(
            signal_id=signal.id, discord_user_id=discord_user_id, display_name=display_name,
            format_interest=get_format_interests(session, discord_user_id),
        ))
        signal.last_activity_at = datetime.now(timezone.utc)
        joined = changed = True
    elif not add and existing is not None:
        session.delete(existing)
        changed = True
    session.flush()
    names = _member_names(session, signal.id)
    return ToggleResult(
        _state(signal, len(names)), names, joined=joined, changed=changed, closed=False,
    )


def toggle_member_sync(
    message_id: str, bucket: str, discord_user_id: str, display_name: str, action: str = "toggle",
) -> ToggleResult | None:
    with SessionLocal() as session:
        result = toggle_member(session, message_id, bucket, discord_user_id, display_name, action)
        session.commit()
        return result


def queue_member_count(session: Session, message_id: str, discord_user_id: str) -> tuple[bool, int] | None:
    """(is_member, count) for an open queue by its card message id, or None if the signal is gone or
    closed — lets the Leave button decide whether the click would empty the queue."""
    signal = _signal_by_message_bucket(session, message_id, pod_signals.QUEUE_BUCKET)
    if signal is None or signal.status != pod_signals.STATUS_OPEN:
        return None
    member_ids = session.execute(
        select(PodSignalMember.discord_user_id).where(PodSignalMember.signal_id == signal.id)
    ).scalars().all()
    return discord_user_id in member_ids, len(member_ids)


def queue_member_count_sync(message_id: str, discord_user_id: str) -> tuple[bool, int] | None:
    with SessionLocal() as session:
        return queue_member_count(session, message_id, discord_user_id)


def resolve_last_leave(session: Session, message_id: str, discord_user_id: str) -> LeaveResolution:
    """Settle a confirmed last-player Leave. Cancels the queue only if the confirmer is still the sole
    member; if anyone joined during the prompt the confirmer is just removed and the queue stays open.
    Does not commit."""
    signal = _signal_by_message_bucket(session, message_id, pod_signals.QUEUE_BUCKET)
    if signal is None or signal.status != pod_signals.STATUS_OPEN:
        return LeaveResolution(LEAVE_GONE, [], None, None, None)
    member_ids = session.execute(
        select(PodSignalMember.discord_user_id).where(PodSignalMember.signal_id == signal.id)
    ).scalars().all()
    if discord_user_id in member_ids and len(member_ids) > 1:
        session.execute(
            delete(PodSignalMember).where(
                PodSignalMember.signal_id == signal.id,
                PodSignalMember.discord_user_id == discord_user_id,
            )
        )
        session.flush()
        names = _member_names(session, signal.id)
        return LeaveResolution(
            LEAVE_LEFT, names, signal.set_code, signal.created_at, signal.opened_by,
            signal.notify_role, signal.description,
        )
    signal.status = pod_signals.STATUS_EXPIRED
    return LeaveResolution(
        LEAVE_CANCELLED, [], signal.set_code, signal.created_at, signal.opened_by,
        signal.notify_role, signal.description,
    )


def resolve_last_leave_sync(message_id: str, discord_user_id: str) -> LeaveResolution:
    with SessionLocal() as session:
        resolution = resolve_last_leave(session, message_id, discord_user_id)
        session.commit()
        return resolution


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


def claim_one_more_ping_sync(signal_id: str, quiet_minutes: int) -> bool:
    """Atomically claim the one one-short-of-firing ping a queue gets. True only for a still-open
    signal that is older than the quiet window and hasn't pinged yet, so fast-filling queues stay
    silent and concurrent joins can't double-ping."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=quiet_minutes)
    with SessionLocal() as session:
        result = session.execute(
            update(PodSignal)
            .where(
                PodSignal.id == signal_id,
                PodSignal.status == pod_signals.STATUS_OPEN,
                PodSignal.one_more_pinged_at.is_(None),
                PodSignal.created_at <= cutoff,
            )
            .values(one_more_pinged_at=datetime.now(timezone.utc))
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


def reset_ondemand_signals_sync(guild_id: str) -> dict[str, int]:
    """Test-only: clear every on-demand pod signal (poll / queue / scheduled) and its members for a
    guild, plus the bot-native pods those signals staged, so the `!test` surfaces start from a clean
    slate. Reflection reads events by slot time, so a stale event row keeps reflecting as a committed
    slot until it is dropped too. Only unfinalized bot-native events go — finalized played pods (their
    leaderboard page) and sesh pods are left untouched, as is any live lobby.

    The event delete is global (pods carry no guild), so this refuses outright unless it is scoped to a
    known non-production guild: an empty guild or the production guild is a hard no-op, guarding against
    ever wiping real pods from the prod deployment."""
    if not guild_id or guild_id == str(PRODUCTION_GUILD_ID):
        return {"signals": 0, "members": 0, "events": 0}
    with SessionLocal() as session:
        signal_ids = list(
            session.execute(select(PodSignal.id).where(PodSignal.guild_id == guild_id)).scalars()
        )
        members = 0
        if signal_ids:
            members = session.execute(
                delete(PodSignalMember).where(PodSignalMember.signal_id.in_(signal_ids))
            ).rowcount
        signals = session.execute(delete(PodSignal).where(PodSignal.guild_id == guild_id)).rowcount
        events = session.execute(
            delete(PodDraftEvent).where(
                PodDraftEvent.sesh_message_id.is_(None), PodDraftEvent.finalized_at.is_(None)
            )
        ).rowcount
        session.commit()
        return {"signals": signals, "members": members, "events": events}


def poll_exists_for_date_sync(signal_date: date) -> bool:
    with SessionLocal() as session:
        return session.execute(
            select(PodSignal.id).where(
                PodSignal.kind == pod_signals.KIND_POLL, PodSignal.signal_date == signal_date
            ).limit(1)
        ).scalar_one_or_none() is not None


def launcher_message_id_for_date_sync(signal_date: date) -> str | None:
    """The launcher message posted that day, if any. Every poll-bucket signal shares it, so any one
    resolves it; None means no launcher was posted (a card can exist without one)."""
    with SessionLocal() as session:
        return session.execute(
            select(PodSignal.message_id).where(
                PodSignal.kind == pod_signals.KIND_POLL, PodSignal.signal_date == signal_date
            ).limit(1)
        ).scalar_one_or_none()


def past_launcher_dates_sync(before_date: date, since_date: date) -> list[date]:
    """Distinct launcher dates in [since_date, before_date) — the recently-posted launchers a new day's
    post closes out. Bounded to a short window so each daily post re-touches only a handful, never the
    full history."""
    with SessionLocal() as session:
        rows = session.execute(
            select(PodSignal.signal_date)
            .where(
                PodSignal.kind == pod_signals.KIND_POLL,
                PodSignal.signal_date < before_date,
                PodSignal.signal_date >= since_date,
            )
            .distinct()
        ).scalars().all()
    return sorted(rows)


def launcher_ref_for_date_sync(signal_date: date) -> tuple[str, str] | None:
    """(channel_id, message_id) of the launcher posted that day, if any. Resolving the channel off the
    signal rather than a fixed setting keeps `!test` (posted in the test channel) and prod correct."""
    with SessionLocal() as session:
        row = session.execute(
            select(PodSignal.channel_id, PodSignal.message_id).where(
                PodSignal.kind == pod_signals.KIND_POLL, PodSignal.signal_date == signal_date
            ).limit(1)
        ).first()
    return (row[0], row[1]) if row else None


def launcher_date_for_message_sync(message_id: str) -> date | None:
    """The signal_date a launcher message was posted for. `!test poll` posts tomorrow's launcher once
    today's slots have passed, so the message timestamp is not a safe date source."""
    with SessionLocal() as session:
        return session.execute(
            select(PodSignal.signal_date).where(
                PodSignal.kind == pod_signals.KIND_POLL, PodSignal.message_id == message_id
            ).limit(1)
        ).scalar_one_or_none()


def latest_launcher_sync() -> tuple[str, date] | None:
    """The newest launcher's (message_id, signal_date), for surfaces that open the preference picker
    without a launcher message in hand."""
    with SessionLocal() as session:
        row = session.execute(
            select(PodSignal.message_id, PodSignal.signal_date)
            .where(PodSignal.kind == pod_signals.KIND_POLL)
            .order_by(PodSignal.signal_date.desc(), PodSignal.created_at.desc())
            .limit(1)
        ).first()
    return (row[0], row[1]) if row else None


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


def slot_occupied_by_any_pod_sync(slot_time: datetime) -> bool:
    """Whether a pod of any set already sits at this slot, so an auto-scheduler stands down instead of
    stacking a second pod onto the same window."""
    with SessionLocal() as session:
        return _event_id_for_slot(session, slot_time) is not None


def launcher_snapshot_sync(message_id: str, signal_date: date) -> list[LauncherSlot]:
    """The day's launcher slots in bucket order, each resolved to committed / lazy / expired.

    A slot whose time carries a locked pod reflects it — sesh-created or bot-native: count, thread, and
    real start time are read off the event (the card is the truth; a little render-time staleness is
    fine). Otherwise the slot is lazy — its own poll signal, or an empty open slot before signals exist.
    Committed wins outright, so a lazy slot that fires and posts its card renders as committed next pass."""
    now = datetime.now(timezone.utc)
    slots: list[LauncherSlot] = []
    with SessionLocal() as session:
        for bucket in pod_signals.poll_buckets_for(signal_date):
            slot_time = slot_event_time(signal_date, bucket.key)
            event_id = _event_id_for_slot(session, slot_time)
            if event_id is not None:
                slots.append(_committed_slot(session, bucket.key, event_id))
                continue
            signal = _signal_by_message_bucket(session, message_id, bucket.key)
            if signal is None:
                slots.append(LauncherSlot(
                    bucket.key, committed=False, status=_lazy_status(pod_signals.STATUS_OPEN, slot_time, now),
                    count=0, slot_time=slot_time, names=[], thread_id=None, signal_id=None,
                ))
                continue
            names = _member_names(session, signal.id)
            slots.append(LauncherSlot(
                bucket.key, committed=False, status=_lazy_status(signal.status, signal.slot_time, now),
                count=len(names), slot_time=signal.slot_time, names=names, thread_id=None, signal_id=signal.id,
                interests=_member_interests(session, signal.id),
            ))
    return slots


def _lazy_status(status: str, slot_time: datetime | None, now: datetime) -> str:
    """An open slot past its time is closed even if its expiry job never fired, so the render never
    offers a join the toggle would refuse."""
    if status == pod_signals.STATUS_OPEN and slot_time is not None and slot_time <= now:
        return pod_signals.STATUS_EXPIRED
    return status


def _committed_slot(session: Session, bucket_key: str, event_id: str) -> LauncherSlot:
    event = session.get(PodDraftEvent, event_id)
    signal = session.execute(
        select(PodSignal).where(
            PodSignal.event_id == event_id, PodSignal.kind == pod_signals.KIND_SCHEDULED
        )
    ).scalar_one_or_none()
    yes_names = _members_by_rsvp(session, signal.id)[pod_signals.RSVP_YES] if signal else []
    interests = _member_interests(session, signal.id) if signal else ()
    return LauncherSlot(
        bucket_key, committed=True, status=pod_signals.STATUS_FIRED, count=len(yes_names),
        slot_time=event.event_time if event else None,
        names=yes_names, thread_id=event.discord_thread_id if event else None, signal_id=None,
        thread_message_id=signal.thread_message_id if signal else None, interests=interests,
        set_code=event.set_code if event else None,
    )


def roster_for_event_sync(event_id: str) -> list[tuple[str, str]]:
    """(discord_user_id, display_name) of the Yes roster for the signal that created this pod, in
    join order. Poll and queue members are implicit Yes."""
    return _roster_for_event_sync(event_id, pod_signals.RSVP_YES)


def maybe_roster_for_event_sync(event_id: str) -> list[tuple[str, str]]:
    """(discord_user_id, display_name) of the Maybe roster for the signal that created this pod, in
    join order."""
    return _roster_for_event_sync(event_id, pod_signals.RSVP_MAYBE)


def _roster_for_event_sync(event_id: str, rsvp: str) -> list[tuple[str, str]]:
    with SessionLocal() as session:
        signal = session.execute(
            select(PodSignal).where(PodSignal.event_id == event_id)
        ).scalar_one_or_none()
        if signal is None:
            return []
        rows = session.execute(
            select(PodSignalMember.discord_user_id, PodSignalMember.display_name)
            .where(
                PodSignalMember.signal_id == signal.id,
                PodSignalMember.rsvp == rsvp,
            )
            .order_by(PodSignalMember.created_at)
        ).all()
        return [(did, name) for did, name in rows]


def poll_yes_members_sync(signal_id: str) -> list[tuple[str, str]]:
    """(discord_user_id, display_name) of a poll slot's signups, in join order. Poll members are all
    implicit Yes, so this is the set to carry over when the slot graduates to an RSVP card."""
    with SessionLocal() as session:
        rows = session.execute(
            select(PodSignalMember.discord_user_id, PodSignalMember.display_name)
            .where(PodSignalMember.signal_id == signal_id)
            .order_by(PodSignalMember.created_at)
        ).all()
        return [(did, name) for did, name in rows]


def seed_yes_members_sync(signal_id: str, members: list[tuple[str, str]]) -> None:
    """Insert a batch of Yes members onto a fresh signal — poll signups carried onto their RSVP card.
    Skips anyone already present so a retry is idempotent."""
    with SessionLocal() as session:
        present = set(session.execute(
            select(PodSignalMember.discord_user_id).where(PodSignalMember.signal_id == signal_id)
        ).scalars())
        for user_id, display_name in members:
            if user_id in present:
                continue
            session.add(PodSignalMember(
                signal_id=signal_id, discord_user_id=user_id, display_name=display_name,
                rsvp=pod_signals.RSVP_YES, format_interest=get_format_interests(session, user_id),
            ))
        session.commit()


def second_table_candidates_sync(event_id: str) -> list[tuple[str, str]]:
    """(discord_user_id, display_name) of the Yes then Maybe roster for the scheduled card that
    created this pod, Yes first and each in join order — the pool to offer a follow-up table to once
    the first pod locks its seats. Empty for poll/queue pods, which carry no standing roster."""
    with SessionLocal() as session:
        signal = session.execute(
            select(PodSignal).where(
                PodSignal.event_id == event_id, PodSignal.kind == pod_signals.KIND_SCHEDULED
            )
        ).scalar_one_or_none()
        if signal is None:
            return []
        rows = session.execute(
            select(PodSignalMember.discord_user_id, PodSignalMember.display_name, PodSignalMember.rsvp)
            .where(
                PodSignalMember.signal_id == signal.id,
                PodSignalMember.rsvp.in_([pod_signals.RSVP_YES, pod_signals.RSVP_MAYBE]),
            )
            .order_by(PodSignalMember.created_at)
        ).all()
    rank = {pod_signals.RSVP_YES: 0, pod_signals.RSVP_MAYBE: 1}
    ordered = sorted(rows, key=lambda row: rank.get(row[2], 2))
    return [(did, name) for did, name, _ in ordered]


def scheduled_card_ref_sync(event_id: str) -> tuple[str, str, str, datetime | None] | None:
    """(signal_id, channel_id, message_id, slot_time) of the scheduled card that created this pod.
    slot_time keeps the original slot through postpones, so slot-keyed rendering stays stable."""
    with SessionLocal() as session:
        row = session.execute(
            select(PodSignal.id, PodSignal.channel_id, PodSignal.message_id, PodSignal.slot_time).where(
                PodSignal.event_id == event_id, PodSignal.kind == pod_signals.KIND_SCHEDULED
            )
        ).first()
    return (row[0], row[1], row[2], row[3]) if row else None


def set_thread_message_sync(signal_id: str, thread_message_id: str) -> None:
    with SessionLocal() as session:
        session.execute(
            update(PodSignal).where(PodSignal.id == signal_id).values(thread_message_id=thread_message_id)
        )
        session.commit()


def rsvp_rosters_sync(message_id: str) -> dict[str, list[str]] | None:
    """Display names per RSVP state for a scheduled card or its mirror, in join order; None when
    no surface matches."""
    with SessionLocal() as session:
        signal = _scheduled_signal_by_surface(session, message_id)
        if signal is None:
            return None
        return _members_by_rsvp(session, signal.id)


def rsvp_rosters_with_interest_sync(
    message_id: str,
) -> dict[str, list[tuple[str, tuple[str, ...]]]] | None:
    """Interest-carrying twin of `rsvp_rosters_sync` for the card render, so the roster can group by
    format. None when no surface matches."""
    with SessionLocal() as session:
        signal = _scheduled_signal_by_surface(session, message_id)
        if signal is None:
            return None
        return _members_by_rsvp_with_interest(session, signal.id)


def scheduled_event_for_message_sync(message_id: str) -> str | None:
    """The pod event behind an RSVP surface, from the card's or the mirror's message id."""
    with SessionLocal() as session:
        signal = _scheduled_signal_by_surface(session, message_id)
        return signal.event_id if signal else None


def native_event_ref_by_surface_sync(message_id: str) -> tuple[str, str, str, str] | None:
    """(native_event_id, guild_id, channel_id, card_message_id) for the native Discord event behind
    an RSVP surface, so its description tally can be re-synced on a click. None when the signal, its
    pod event, or the native event id is missing."""
    with SessionLocal() as session:
        signal = _scheduled_signal_by_surface(session, message_id)
        if signal is None or signal.event_id is None:
            return None
        event = session.get(PodDraftEvent, signal.event_id)
        if event is None or event.discord_scheduled_event_id is None:
            return None
        return event.discord_scheduled_event_id, signal.guild_id, signal.channel_id, signal.message_id


def ondemand_event_name_sync(set_code: str, event_time: datetime) -> str:
    """The `SET Mon Day Slot Pod` name, fixed at creation and never renumbered. The website's `#N`
    milestone is a separate execution-ordered projection in `public_pod_draft_events`, not baked in
    here, so a scheduled card posted days ahead can never carry an out-of-order number."""
    return pod_display_name(set_code, event_time)


def dedupe_thread_name(channel: discord.TextChannel, base_name: str) -> str:
    """`base_name`, or `base_name #N` when a live thread of the same name already exists in `channel`.

    Reads the guild's cached active threads only — no API call — and reuses the collision-index scheme
    behind ` - Table N`, so back-to-back queues for one slot stay distinguishable without ever
    renumbering past a finished, archived thread. Used for queue discussion threads, which carry no
    pod_draft_events row; pod events dedupe against the DB via `dedupe_pod_name`.
    """
    live = [
        thread.name for thread in channel.threads
        if not thread.archived and (thread.name == base_name or thread.name.startswith(f"{base_name} #"))
    ]
    if base_name not in live:
        return base_name
    return f"{base_name} #{next_collision_index(live, COLLISION_INDEX_RE)}"


def dedupe_pod_name_sync(base_name: str, live_names: list[str] | None = None, session: Session | None = None) -> str:
    """`base_name`, or `base_name #N` when a pod of that name already exists.

    Keys off persisted pod_draft_events names so a same-slot pod launched after the previous one's
    thread has archived still numbers correctly — the DB remembers finished pods that a live-thread
    scan cannot see. `live_names` folds in threads created this instant whose event row has not yet
    committed, covering pods that launch concurrently.
    """
    if session is None:
        with SessionLocal() as owned:
            return dedupe_pod_name_sync(base_name, live_names, session=owned)
    persisted = session.execute(
        select(PodDraftEvent.name).where(
            or_(PodDraftEvent.name == base_name, PodDraftEvent.name.like(f"{base_name} #%"))
        )
    ).scalars().all()
    taken = set(persisted)
    for name in live_names or []:
        if name == base_name or name.startswith(f"{base_name} #"):
            taken.add(name)
    if base_name not in taken:
        return base_name
    return f"{base_name} #{next_collision_index(taken, COLLISION_INDEX_RE)}"


async def dedupe_pod_name(channel: discord.TextChannel, base_name: str) -> str:
    live_names = [thread.name for thread in channel.threads if not thread.archived]
    return await asyncio.to_thread(dedupe_pod_name_sync, base_name, live_names)


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

    name = await dedupe_pod_name(channel, name)
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
            signal = session.get(PodSignal, signal_id)
            if signal is not None:
                event.description = signal.description
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
    rsvps = await asyncio.to_thread(signal_rsvps_sync, event_id)
    maybe_names = rsvps[1] if rsvps else []
    draftmancer_url = draftmancer_url_for(session_id)

    thread = await _fetch_thread(bot, thread_id)
    if thread is None:
        log.warning(f"open_ondemand_lobby: thread {thread_id} unreachable")
        return

    mention_block = " ".join(f"<@{did}>" for did, _ in roster)

    manager = await start_manager(
        bot, event_id, session_id, thread_id, set_code, len(display_names),
        event_name=event_name, draftmancer_url=draftmancer_url,
        rsvps_yes=display_names, rsvps_maybe=maybe_names,
    )
    if manager is not None:
        await manager.await_ownership()

    body = build_lobby_open_body(draftmancer_url, mention_block)
    try:
        await thread.send(
            body, view=build_join_view(session_id),
            allowed_mentions=discord.AllowedMentions(users=True),
        )
    except discord.HTTPException:
        log.warning(f"open_ondemand_lobby: could not post in thread {thread_id}", exc_info=True)
        return

    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is not None and event.socket_status == "pending":
            event.socket_status = "reminded"
            session.commit()

    maybe_roster = await asyncio.to_thread(maybe_roster_for_event_sync, event_id)
    recipients = (
        [(did, name, "yes") for did, name in roster]
        + [(did, name, "maybe") for did, name in maybe_roster]
    )
    await send_lobby_link_dms(
        bot, session_id=session_id, thread=thread, recipients=recipients,
    )

    if manager is not None:
        manager.arm_team_vote_offer(len(display_names))
        interests = await asyncio.to_thread(event_member_interests_sync, event_id)
        if fi.should_offer_format_poll(fi.composition(interests)):
            await manager.offer_format_poll()
        pick_timer = await asyncio.to_thread(scheduled_pick_timer_for_event_sync, event_id)
        if pick_timer is not None:
            await manager.apply_pick_timer(pick_timer)


def arm_scheduled_pod_jobs(
    bot: commands.Bot, event_id: str, event_time: datetime, created_at: datetime,
) -> None:
    """Every timed job a scheduled card carries: T-10 lobby open, at-start team vote, underfill
    checks, and the roster reminder. Creation, /pod-postpone, and the startup sweep all arm here."""
    _arm_open(bot, event_id, event_time)
    schedule_team_vote_offer(bot.pod_scheduler, event_id, event_time)
    schedule_underfill_checks(bot.pod_scheduler, event_id, event_time, created_at)
    schedule_roster_reminder(bot.pod_scheduler, event_id, event_time)


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
    """At slot time, close an unfired poll slot and drop its standing nudge — the recruiting window is
    over. The slot's button stays but toggle_member_sync now refuses it, so a late click gets a graceful
    ephemeral and never joins a dead slot."""
    if await asyncio.to_thread(expire_signal_sync, signal_id):
        log.info(f"poll slot {signal_id} expired unfired")
        if _bot is not None:
            await clear_slot_nudge(_bot, signal_id)


def past_pod_cards_sync(now: datetime, since: datetime) -> list[tuple[str, str, str | None, str | None]]:
    """(card channel_id, card message_id, thread_id, thread-controls message_id) for scheduled pods
    whose real start is in (since, now] — the ones that have run since the last launcher. Keyed on the
    event's current start, so a pod rescheduled back into the future is skipped."""
    with SessionLocal() as session:
        rows = session.execute(
            select(PodSignal, PodDraftEvent)
            .join(PodDraftEvent, PodDraftEvent.id == PodSignal.event_id)
            .where(
                PodSignal.kind == pod_signals.KIND_SCHEDULED,
                PodDraftEvent.event_time > since,
                PodDraftEvent.event_time <= now,
            )
        ).all()
    return [(s.channel_id, s.message_id, e.discord_thread_id, s.thread_message_id) for s, e in rows]


def event_card_surfaces_sync(event_id: str) -> tuple[str, str, str | None, str | None] | None:
    """(card channel_id, card message_id, thread_id, thread-controls message_id) for one scheduled
    pod, or None when the pod has no card (poll/queue-born pods carry no RSVP card)."""
    with SessionLocal() as session:
        row = session.execute(
            select(
                PodSignal.channel_id, PodSignal.message_id, PodSignal.thread_message_id,
                PodDraftEvent.discord_thread_id,
            )
            .join(PodDraftEvent, PodDraftEvent.id == PodSignal.event_id)
            .where(PodSignal.event_id == event_id, PodSignal.kind == pod_signals.KIND_SCHEDULED)
        ).first()
    if row is None:
        return None
    channel_id, message_id, thread_message_id, thread_id = row
    return channel_id, message_id, thread_id, thread_message_id


async def close_event_card(bot: commands.Bot, event_id: str) -> None:
    """Drop the RSVP buttons on one pod's card the moment its draft finishes. The card stays live
    through lobby fill and the ready check — including a restart that reopens the lobby — and closes
    only at draft_done, the first state a restart can no longer revert. No-op for pods without a card."""
    surfaces = await asyncio.to_thread(event_card_surfaces_sync, event_id)
    if surfaces is None or _bot is None:
        return
    channel_id, message_id, thread_id, thread_message_id = surfaces
    await _retire_message(int(channel_id), int(message_id))
    if thread_id and thread_message_id:
        await _retire_message(int(thread_id), int(thread_message_id))


CARD_CANCELED_MARKER = "🗑️ **Draft canceled**"


async def cancel_event_card(event_id: str) -> None:
    """Retire a canceled pod's card: grey it, stamp it canceled, and drop its buttons on both the
    channel card and the thread mirror. Fired from `cancel_pod_event` before the event row is deleted,
    so the card surfaces still resolve; a no-op for pods without a card."""
    if _bot is None:
        return
    await clear_underfill_nudge(_bot, event_id)
    surfaces = await asyncio.to_thread(event_card_surfaces_sync, event_id)
    if surfaces is None:
        return
    channel_id, message_id, thread_id, thread_message_id = surfaces
    await _mark_card_canceled(int(channel_id), int(message_id))
    if thread_id and thread_message_id:
        await _retire_message(int(thread_id), int(thread_message_id))


async def _mark_card_canceled(channel_id: int, message_id: int) -> None:
    channel = await _resolve_channel(channel_id)
    if channel is None:
        return
    try:
        message = await channel.fetch_message(message_id)
    except discord.HTTPException:
        log.warning(f"could not fetch card {message_id} to cancel", exc_info=True)
        return
    embed = message.embeds[0] if message.embeds else None
    if embed is not None and CARD_CANCELED_MARKER not in (embed.description or ""):
        title_line = (embed.description or "").split("\n", 1)[0]
        embed.color = discord.Color.dark_grey()
        embed.description = f"{title_line}\n{CARD_CANCELED_MARKER}"
    try:
        await message.edit(content=None, embed=embed, view=None)
    except discord.HTTPException:
        log.warning(f"could not mark card {message_id} canceled", exc_info=True)


async def close_past_pod_cards() -> None:
    """Backstop for the per-draft close: sweep RSVP buttons off cards for pods that ran but never hit
    draft_done — cancelled or no-show pods whose `close_event_card` never fired — so no card outlives
    its pod indefinitely. Runs from the daily launcher post over pods started in the last window."""
    if _bot is None:
        return
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=CARD_CLOSE_WINDOW_H)
    cards = await asyncio.to_thread(past_pod_cards_sync, now, since)
    for channel_id, message_id, thread_id, thread_message_id in cards:
        await _retire_message(int(channel_id), int(message_id))
        if thread_id and thread_message_id:
            await _retire_message(int(thread_id), int(thread_message_id))


async def _resolve_channel(channel_id: int) -> "discord.abc.Messageable | None":
    channel = _bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await _bot.fetch_channel(channel_id)
        except discord.HTTPException:
            return None
    return channel


async def _retire_message(channel_id: int, message_id: int) -> None:
    """Drop a retired pod message's buttons and clear its content ping, so a finished card carries no
    live controls and no lingering role-mention highlight. The thread mirror has no content, so clearing
    it there is a no-op."""
    channel = await _resolve_channel(channel_id)
    if channel is None:
        return
    try:
        message = await channel.fetch_message(message_id)
        await message.edit(content=None, view=None)
    except discord.HTTPException:
        log.warning(f"could not retire message {message_id}", exc_info=True)


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
    from bot.commands.pod_queue import PodQueueView, queue_inactivity_close_reason, queue_role_mention

    if not await asyncio.to_thread(expire_signal_sync, signal_id):
        return
    ref = await asyncio.to_thread(signal_message_ref_sync, signal_id)
    if ref is None or _bot is None:
        return
    channel_id, message_id = ref
    channel = await _fetch_text_channel(_bot, int(channel_id))
    if channel is None:
        return
    presets = await asyncio.to_thread(queue_presets_sync, signal_id)
    opened_at, opened_by = await asyncio.to_thread(queue_opener_sync, signal_id)
    names = await asyncio.to_thread(queue_member_names_sync, signal_id)
    try:
        message = await channel.fetch_message(int(message_id))
        closed_view = PodQueueView(
            names=names, role_mention=queue_role_mention(channel.guild),
            close_reason=queue_inactivity_close_reason(), set_code=presets.set_code,
            opened_at=opened_at, opened_by=opened_by,
        )
        await message.edit(view=closed_view)
    except discord.HTTPException:
        log.warning(f"fire_queue_teardown: could not edit queue message {message_id}", exc_info=True)


async def rearm_signals(bot: commands.Bot) -> None:
    """Startup sweep: re-arm slot expiries and underfill beats, on-demand lobby opens, and queue
    teardowns from the DB so a restart loses nothing. Past-due opens fire immediately; past-due open
    signals are expired and their standing nudges dropped."""
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        signals = session.execute(
            select(PodSignal).where(PodSignal.status.in_([pod_signals.STATUS_OPEN, pod_signals.STATUS_FIRED]))
        ).scalars().all()
        pending = [
            (s.id, s.kind, s.status, s.slot_time, s.last_activity_at, s.event_id, s.created_at)
            for s in signals
        ]

    for signal_id, kind, status, slot_time, last_activity, event_id, created_at in pending:
        if status == pod_signals.STATUS_FIRED and event_id is not None:
            scheduled = kind == pod_signals.KIND_SCHEDULED
            if _rearm_open_if_pending(bot, event_id, with_fill_jobs=scheduled):
                continue
        if status != pod_signals.STATUS_OPEN:
            continue
        if kind == pod_signals.KIND_POLL and slot_time is not None:
            if slot_time <= now:
                if await asyncio.to_thread(expire_signal_sync, signal_id):
                    await clear_slot_nudge(bot, signal_id)
            else:
                arm_slot_expiry(bot, signal_id, slot_time)
                schedule_slot_underfill_checks(bot.pod_scheduler, signal_id, slot_time, created_at)
        elif kind == pod_signals.KIND_QUEUE:
            teardown = pod_signals.teardown_at(last_activity, settings.pod_queue_inactivity_minutes)
            if teardown <= now:
                await asyncio.to_thread(expire_signal_sync, signal_id)
            else:
                arm_queue_teardown(bot, signal_id, teardown)


def _rearm_open_if_pending(bot: commands.Bot, event_id: str, with_fill_jobs: bool = False) -> bool:
    """`with_fill_jobs` re-arms the underfill and roster-reminder jobs a scheduled card carries on
    top of the lobby open; poll and queue pods fire full by construction and skip them."""
    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is None or event.socket_status not in ("pending", "reminded"):
            return False
        event_time = event.event_time
        created_at = event.created_at
    if with_fill_jobs:
        arm_scheduled_pod_jobs(bot, event_id, event_time, created_at)
    else:
        _arm_open(bot, event_id, event_time)
        schedule_team_vote_offer(bot.pod_scheduler, event_id, event_time)
    return True


_bot: commands.Bot | None = None


def init_launch(bot: commands.Bot) -> None:
    """Wire the bot reference so scheduler callbacks (queue teardown) can edit Discord messages, and
    register the draft-done card close so the manager can fire it without importing this module."""
    global _bot
    _bot = bot
    set_card_close_hook(close_event_card)
    set_card_cancel_hook(cancel_event_card)


def _signal_by_message_bucket(session: Session, message_id: str, bucket: str) -> PodSignal | None:
    return session.execute(
        select(PodSignal).where(PodSignal.message_id == message_id, PodSignal.bucket == bucket)
    ).scalar_one_or_none()


def _scheduled_signal_by_surface(session: Session, message_id: str) -> PodSignal | None:
    """The scheduled signal whose channel card or thread mirror is this message."""
    return session.execute(
        select(PodSignal).where(
            PodSignal.bucket == pod_signals.SCHEDULED_BUCKET,
            or_(PodSignal.message_id == message_id, PodSignal.thread_message_id == message_id),
        )
    ).scalar_one_or_none()


def _event_id_for_slot(session: Session, slot_time: datetime) -> str | None:
    """The pod already sitting at this slot — any set, sesh-created or bot-native — so the launcher
    reflects it as a jump-link and the weekly card stands down instead of stacking a second pod on top.
    A pod runs 2-3 hours, so occupancy is a window around the slot, not an exact-minute match; the
    window stays inside the 5-hour gap between slots so a neighbouring slot's pod never counts. Pods
    carry no guild and coordination is single-guild, so the match is by time alone. Newest wins when
    repeated test runs leave several at one slot.

    ` - Table N` spillover pods are excluded: a second table is a child of the pod already reflected
    here, opened later so its event_time lands in this window, and reflecting it would drop the original
    pod's roster off the launcher."""
    return session.execute(
        select(PodDraftEvent.id).where(
            PodDraftEvent.event_time >= slot_time - SLOT_OCCUPANCY_WINDOW,
            PodDraftEvent.event_time < slot_time + SLOT_OCCUPANCY_WINDOW,
            PodDraftEvent.name.op("!~*")(TABLE_SUFFIX_SQL_RE),
        ).order_by(PodDraftEvent.created_at.desc()).limit(1)
    ).scalar_one_or_none()


def _member_names(session: Session, signal_id: str) -> list[str]:
    return list(session.execute(
        select(PodSignalMember.display_name)
        .where(PodSignalMember.signal_id == signal_id)
        .order_by(PodSignalMember.created_at)
    ).scalars().all())


def _member_interests(session: Session, signal_id: str) -> tuple[tuple[str, ...], ...]:
    rows = session.execute(
        select(PodSignalMember.format_interest)
        .where(PodSignalMember.signal_id == signal_id)
        .order_by(PodSignalMember.created_at)
    ).scalars().all()
    return tuple(tuple(fi.normalize(interest)) for interest in rows)


def player_interest_sync(discord_user_id: str) -> list[str]:
    with SessionLocal() as session:
        return get_format_interests(session, discord_user_id)


def player_flashback_ranking_sync(discord_user_id: str) -> list[str]:
    with SessionLocal() as session:
        return get_flashback_ranking(session, discord_user_id)


def set_flashback_ranking_sync(discord_user_id: str, ranking: list[str]) -> None:
    with SessionLocal() as session:
        set_flashback_ranking(session, discord_id=discord_user_id, ranking=ranking)
        session.commit()


def set_launcher_interest_sync(
    message_id: str, discord_user_id: str, discord_username: str, display_name: str,
    avatar_hash: str | None, interests: list[str], signal_date: date,
) -> bool:
    """Set the user's format interest on every slot the launcher shows — its own lazy signals plus the
    scheduled pods it reflects — and persist it as their standing preference so the next launcher opens
    pre-seeded. Returns whether any signup moved."""
    normalized = fi.normalize(interests)
    with SessionLocal() as session:
        signal_ids = _launcher_day_signal_ids(session, message_id, signal_date)
        members = session.execute(
            select(PodSignalMember).where(
                PodSignalMember.signal_id.in_(signal_ids),
                PodSignalMember.discord_user_id == discord_user_id,
            )
        ).scalars().all() if signal_ids else []
        for member in members:
            member.format_interest = normalized
        set_format_interests(
            session, discord_id=discord_user_id, discord_username=discord_username,
            display_name=display_name, avatar_hash=avatar_hash, interests=normalized,
        )
        session.commit()
        return bool(members)


def _launcher_day_signal_ids(session: Session, message_id: str, signal_date: date) -> list[str]:
    ids = list(session.execute(
        select(PodSignal.id).where(PodSignal.message_id == message_id)
    ).scalars().all())
    for bucket in pod_signals.poll_buckets_for(signal_date):
        event_id = _event_id_for_slot(session, slot_event_time(signal_date, bucket.key))
        if event_id is None:
            continue
        scheduled_id = session.execute(
            select(PodSignal.id).where(
                PodSignal.event_id == event_id, PodSignal.kind == pod_signals.KIND_SCHEDULED
            )
        ).scalar_one_or_none()
        if scheduled_id is not None:
            ids.append(scheduled_id)
    return ids


def _members_by_rsvp(session: Session, signal_id: str) -> dict[str, list[str]]:
    rows = session.execute(
        select(PodSignalMember.rsvp, PodSignalMember.display_name)
        .where(PodSignalMember.signal_id == signal_id)
        .order_by(PodSignalMember.created_at)
    ).all()
    rosters: dict[str, list[str]] = {state: [] for state in pod_signals.RSVP_STATES}
    for state, name in rows:
        rosters.setdefault(state, []).append(name)
    return rosters


def _members_by_rsvp_with_interest(
    session: Session, signal_id: str,
) -> dict[str, list[tuple[str, tuple[str, ...]]]]:
    """Each member's (display name, format-interest codes) per RSVP state, so the card can group the
    roster by format. Same rows as `_members_by_rsvp`, carrying the interest the member signed up with."""
    rows = session.execute(
        select(PodSignalMember.rsvp, PodSignalMember.display_name, PodSignalMember.format_interest)
        .where(PodSignalMember.signal_id == signal_id)
        .order_by(PodSignalMember.created_at)
    ).all()
    rosters: dict[str, list[tuple[str, tuple[str, ...]]]] = {state: [] for state in pod_signals.RSVP_STATES}
    for state, name, interest in rows:
        rosters.setdefault(state, []).append((name, tuple(interest or ())))
    return rosters


def _state(signal: PodSignal, count: int) -> SignalState:
    return SignalState(
        signal.id, signal.kind, signal.bucket, signal.status, count, signal.slot_time, signal.event_id,
        signal.set_code, signal.created_at, signal.opened_by, signal.notify_role, signal.description,
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
