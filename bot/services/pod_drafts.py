"""Pod draft persistence and matching logic — pure SQLAlchemy, no Discord or websocket deps."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import any_, func, select
from sqlalchemy.orm import Session

from bot.config import settings
from bot.database import SessionLocal
from bot.models import (
    MagicSet,
    Player,
    PodDraftDmMessage,
    PodDraftEvent,
    PodDraftMatch,
    PodDraftParticipant,
)
from bot.services import pod_format


log = logging.getLogger(__name__)


DM_KIND_ROUND = "round_pairing"
DM_KIND_SUBMIT_DECK = "submit_deck"
DM_KIND_SUBMIT_DECK_FINAL = "submit_deck_final"


@dataclass(frozen=True)
class ParticipantDmInfo:
    """Per-participant info for round-start DMs. Keyed by normalized draftmancer_name."""
    participant_id: str
    discord_id: str | None
    display_name: str
    arena_name: str | None


@dataclass(frozen=True)
class ParsedSeshEvent:
    """Input to record_event. event_number is used only for draftmancer_session naming, not stored."""
    event_date: date
    event_time: datetime
    set_code: str
    event_number: int | None
    name: str
    attendees: Sequence[str]
    sesh_message_id: str
    discord_thread_id: str
    discord_event_id: str | None = None


@dataclass(frozen=True)
class FinalStanding:
    """One participant's outcome at champion finalization."""
    draftmancer_name: str
    placement: int
    record: str
    eliminated_round: int | None


def _lookup_set_id(session: Session, set_code: str) -> str | None:
    return session.execute(
        select(MagicSet.id).where(func.upper(MagicSet.code) == set_code.upper())
    ).scalar_one_or_none()


def _build_draftmancer_session(session: Session, parsed: ParsedSeshEvent) -> str:
    """Compose a stable session id; prefer #N from the title, fall back to Month-Day; suffix collisions A/B/C.

    Custom formats drop the LLU prefix and lead with their own slug instead of a set code.
    """
    slug = pod_format.session_slug_for(parsed.set_code)
    if slug is not None:
        head = f"{slug}-{parsed.event_date:%y}"
    else:
        head = f"{settings.pod_draft_session_prefix}-{parsed.set_code}"

    if parsed.event_number is not None:
        suffix = f"D{parsed.event_number}" if slug is not None else str(parsed.event_number)
        base = f"{head}-{suffix}"
    else:
        base = f"{head}-{parsed.event_date:%b}-{parsed.event_date.day}"

    taken = set(session.execute(
        select(PodDraftEvent.draftmancer_session).where(PodDraftEvent.draftmancer_session.like(f"{base}%"))
    ).scalars().all())
    if base not in taken:
        return base
    for i in range(26):
        candidate = f"{base}-{chr(ord('A') + i)}"
        if candidate not in taken:
            return candidate
    # >26 collisions is implausible; fall back to a numeric suffix beyond Z
    n = 27
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


_ARENA_ID_RE = re.compile(r"#\d+$")
_ARENA_ID_SQL = r"#\d+$"
_NAME_TOKEN_RE = re.compile(r"[\s()/\\,|-]+")


def normalize_player_name(name: str) -> str:
    """Strip trailing MTG Arena suffix (`#NNNN`) and lowercase for matching."""
    return _ARENA_ID_RE.sub("", name).lower()


def _normalized_column(col):
    """SQL expression: lowercase a column and strip the trailing `#NNNN` MTG Arena suffix."""
    return func.regexp_replace(func.lower(col), _ARENA_ID_SQL, "")


def classify_lobby_names(session: Session, names: Sequence[str]) -> list[tuple[str, str | None]]:
    """For each Draftmancer userName, return (arena_name, display_name) if linked else (arena_name, None)."""
    result = []
    for n in names:
        player = _player_for_name(session, n)
        result.append((n, player.display_name if player else None))
    return result


def _player_for_name(session: Session, name: str) -> Player | None:
    """Resolve a Draftmancer/Discord name to a Player.

    Matching tiers (first hit wins):
      1. Exact match against any arena_aliases entry (normalized).
      2. Longest-prefix match against arena_aliases.
      3. Exact normalized display_name or discord_username.
      4. norm is a word token within display_name or discord_username
         (e.g. display "Alice (Wonderland)" matches Draftmancer name "Wonderland#12345").
    """
    norm = normalize_player_name(name)
    if not norm:
        return None

    found = session.execute(
        select(Player)
        .where(Player.active.is_(True), norm == any_(Player.arena_aliases))
        .limit(1)
    ).scalar_one_or_none()
    if found is not None:
        return found

    candidates = session.execute(
        select(Player).where(Player.active.is_(True))
    ).scalars().all()

    best: tuple[Player, str] | None = None
    for p in candidates:
        for alias in (p.arena_aliases or []):
            if alias and norm.startswith(alias):
                if best is None or len(alias) > len(best[1]):
                    best = (p, alias)
    if best is not None:
        return best[0]

    found = session.execute(
        select(Player)
        .where(
            Player.active.is_(True),
            (_normalized_column(Player.display_name) == norm)
            | (_normalized_column(Player.discord_username) == norm),
        )
        .limit(1)
    ).scalar_one_or_none()
    if found is not None:
        return found

    if len(norm) >= 3:
        for p in candidates:
            for field in (p.display_name or "", p.discord_username or ""):
                if norm in _NAME_TOKEN_RE.split(field.lower()):
                    return p

    return None


def record_event(session: Session, parsed: ParsedSeshEvent) -> PodDraftEvent:
    """Insert a pod_draft_event row plus one participant per sesh attendee."""
    set_id = _lookup_set_id(session, parsed.set_code) if parsed.set_code else None
    session_id = _build_draftmancer_session(session, parsed)
    url = f"https://draftmancer.com/?session={session_id}"

    event = PodDraftEvent(
        event_date=parsed.event_date,
        event_time=parsed.event_time,
        set_id=set_id,
        set_code=parsed.set_code,
        format_label=pod_format.label_for(parsed.set_code),
        name=parsed.name,
        draftmancer_session=session_id,
        draftmancer_url=url,
        discord_thread_id=parsed.discord_thread_id,
        sesh_message_id=parsed.sesh_message_id,
        socket_status="pending",
        discord_event_id=parsed.discord_event_id,
    )
    session.add(event)
    session.flush()

    for attendee in parsed.attendees:
        _add_attendee(session, event.id, attendee)
    session.flush()
    return event


def update_event_time_if_changed(
    session: Session,
    sesh_message_id: str,
    new_event_time: datetime,
    new_event_date: date,
) -> tuple[PodDraftEvent, bool, bool] | None:
    """Sync event_time/event_date from a re-parsed sesh embed.

    Returns None if the row is missing or already finalized as draft_done or complete.
    Otherwise returns (event, needs_reschedule, was_active):
        - event: the matching PodDraftEvent row.
        - needs_reschedule: True when the parsed time differs from the stored value.
            False means the caller can skip the re-arm regardless of status.
        - was_active: True when the bot had already advanced past 'pending'.
            Caller must tear down any live manager before re-arming.

    Sesh re-edits the embed at the scheduled start to strip RSVP reactions, and that edit is not a reschedule.
    """
    event = session.execute(
        select(PodDraftEvent).where(PodDraftEvent.sesh_message_id == sesh_message_id)
    ).scalar_one_or_none()
    if event is None or event.socket_status in ("draft_done", "complete"):
        return None
    was_active = event.socket_status != "pending"
    time_changed = event.event_time != new_event_time or event.event_date != new_event_date
    if not time_changed:
        return event, False, was_active
    event.event_time = new_event_time
    event.event_date = new_event_date
    if was_active:
        event.socket_status = "pending"
    session.flush()
    return event, True, was_active


def update_event_format(session: Session, event_id: str, code: str) -> bool:
    """Repoint a pre-draft pod event's set_code, set_id and format label; False if missing or already finalized."""
    event = session.get(PodDraftEvent, event_id)
    if event is None or event.socket_status in ("draft_done", "complete"):
        return False
    event.set_code = code
    event.set_id = _lookup_set_id(session, code)
    event.format_label = pod_format.label_for(code)
    return True


def load_event_set_code_sync(event_id: str) -> str | None:
    """Current set_code (format code) for a pod event, or None when missing."""
    with SessionLocal() as session:
        return session.execute(
            select(PodDraftEvent.set_code).where(PodDraftEvent.id == event_id)
        ).scalar_one_or_none()


def load_event_pairing_mode_sync(event_id: str) -> str | None:
    """Current pairing_mode for a pod event, or None when missing."""
    with SessionLocal() as session:
        return session.execute(
            select(PodDraftEvent.pairing_mode).where(PodDraftEvent.id == event_id)
        ).scalar_one_or_none()


def load_event_name_sync(event_id: str) -> str:
    with SessionLocal() as session:
        return session.execute(
            select(PodDraftEvent.name).where(PodDraftEvent.id == event_id)
        ).scalar_one_or_none() or "Pod Draft"


def load_event_id_by_thread_sync(thread_id: str) -> str | None:
    with SessionLocal() as session:
        return session.execute(
            select(PodDraftEvent.id).where(PodDraftEvent.discord_thread_id == thread_id)
        ).scalar_one_or_none()


def load_event_id_by_name_sync(name: str) -> str | None:
    with SessionLocal() as session:
        return session.execute(
            select(PodDraftEvent.id).where(PodDraftEvent.name == name)
        ).scalar_one_or_none()


def load_event_thread_id_sync(event_id: str) -> str | None:
    with SessionLocal() as session:
        return session.execute(
            select(PodDraftEvent.discord_thread_id).where(PodDraftEvent.id == event_id)
        ).scalar_one_or_none()


def search_event_names_sync(query: str, limit: int = 25) -> list[str]:
    """Most-recent-first event names matching a case-insensitive substring of `query`; empty query returns the most recent."""
    with SessionLocal() as session:
        stmt = select(PodDraftEvent.name).order_by(PodDraftEvent.event_date.desc().nulls_last())
        if query:
            stmt = stmt.where(PodDraftEvent.name.ilike(f"%{query}%"))
        return [n for n in session.execute(stmt.limit(limit)).scalars().all() if n]


def seed_event_participants(session: Session, event_id: str, roster: list[str]) -> None:
    """Upsert one pod_draft_participants row per Draftmancer userName in `roster`. Idempotent —
    safe to call multiple times on the same event; existing rows get backfilled instead of
    duplicated."""
    for name in roster:
        upsert_participant(session, event_id, display_name=name, draftmancer_name=name)


def _add_attendee(session: Session, event_id: str, display_name: str) -> PodDraftParticipant:
    player = _player_for_name(session, display_name)
    participant = PodDraftParticipant(
        event_id=event_id,
        display_name=display_name,
        player_id=player.id if player else None,
    )
    session.add(participant)
    return participant


def upsert_participant(
    session: Session,
    event_id: str,
    display_name: str,
    draftmancer_name: str | None = None,
) -> PodDraftParticipant:
    """Find-or-create a participant for this event.

    Match priority: existing draftmancer_name (normalized), existing display_name vs supplied draftmancer_name 
    (normalized), existing display_name vs supplied display_name (normalized).
    Backfills draftmancer_name and player_id when previously null.
    Arena-name mismatches fall through to /pod-link-arena.
    """
    rows = session.execute(
        select(PodDraftParticipant).where(PodDraftParticipant.event_id == event_id)
    ).scalars().all()

    target_dn = normalize_player_name(display_name)
    target_dm = normalize_player_name(draftmancer_name) if draftmancer_name else None

    found: PodDraftParticipant | None = None
    if target_dm:
        for row in rows:
            if row.draftmancer_name and normalize_player_name(row.draftmancer_name) == target_dm:
                found = row
                break
        if found is None:
            for row in rows:
                if normalize_player_name(row.display_name) == target_dm:
                    found = row
                    break
    if found is None:
        for row in rows:
            if normalize_player_name(row.display_name) == target_dn:
                found = row
                break

    if found is None:
        found = PodDraftParticipant(event_id=event_id, display_name=display_name)
        session.add(found)

    if draftmancer_name and not found.draftmancer_name:
        found.draftmancer_name = draftmancer_name

    if found.player_id is None:
        candidate = _player_for_name(session, draftmancer_name or display_name)
        if candidate is None and draftmancer_name:
            candidate = _player_for_name(session, display_name)
        if candidate is not None:
            found.player_id = candidate.id

    session.flush()
    return found


def add_pairing(
    session: Session,
    event_id: str,
    round_num: int,
    player_a_name: str,
    player_b_name: str,
    pairing_index: int = 0,
) -> PodDraftMatch:
    """Insert a pending match (no winner yet); returns the row with its generated id."""
    match = PodDraftMatch(
        event_id=event_id,
        round=round_num,
        pairing_index=pairing_index,
        player_a_name=player_a_name,
        player_b_name=player_b_name,
    )
    session.add(match)
    session.flush()
    return match


def set_match_result(
    session: Session,
    match_id: str,
    winner_name: str,
    score: str,
) -> PodDraftMatch:
    """Fill winner + score on a pending match. Raises if no row matches."""
    match = session.get(PodDraftMatch, match_id)
    if match is None:
        raise ValueError(f"pod_draft_match {match_id} not found")
    match.winner_name = winner_name
    match.score = score
    match.reported_at = datetime.now(timezone.utc)
    session.flush()
    return match


def record_match(
    session: Session,
    event_id: str,
    round_num: int,
    player_a_name: str,
    player_b_name: str,
    winner_name: str,
    score: str,
) -> PodDraftMatch:
    """Idempotent on (event_id, round, names) so debounce re-commits collapse to one row."""
    existing = session.execute(
        select(PodDraftMatch).where(
            PodDraftMatch.event_id == event_id,
            PodDraftMatch.round == round_num,
            PodDraftMatch.player_a_name == player_a_name,
            PodDraftMatch.player_b_name == player_b_name,
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing is None:
        existing = PodDraftMatch(
            event_id=event_id,
            round=round_num,
            player_a_name=player_a_name,
            player_b_name=player_b_name,
            winner_name=winner_name,
            score=score,
            reported_at=now,
        )
        session.add(existing)
    else:
        existing.winner_name = winner_name
        existing.score = score
        existing.reported_at = now
    session.flush()
    return existing


def finalize_champion(
    session: Session,
    event_id: str,
    standings: Sequence[FinalStanding],
) -> PodDraftEvent:
    """Apply placements/records to participants and mark socket_status='complete'. Draft-log URLs are written mid-draft by pod_draft_manager and intentionally left untouched here."""
    event = session.get(PodDraftEvent, event_id)
    if event is None:
        raise ValueError(f"pod_draft_event {event_id} not found")

    for standing in standings:
        participant = upsert_participant(
            session,
            event_id,
            display_name=standing.draftmancer_name,
            draftmancer_name=standing.draftmancer_name,
        )
        participant.placement = standing.placement
        participant.record = standing.record
        participant.eliminated_round = standing.eliminated_round

    event.socket_status = "complete"
    if event.finalized_at is None:
        event.finalized_at = datetime.now(timezone.utc)
    session.flush()
    return event


def upsert_dm_message(
    session: Session,
    *,
    event_id: str,
    participant_id: str,
    kind: str,
    round_num: int | None,
    match_id: str | None,
    dm_channel_id: str,
    dm_message_id: str,
) -> None:
    """Upsert a DM message ref. Unique key is (participant_id, kind, round_num)."""
    existing = session.execute(
        select(PodDraftDmMessage).where(
            PodDraftDmMessage.participant_id == participant_id,
            PodDraftDmMessage.kind == kind,
            PodDraftDmMessage.round_num.is_(round_num) if round_num is None
            else PodDraftDmMessage.round_num == round_num,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.match_id = match_id
        existing.dm_channel_id = dm_channel_id
        existing.dm_message_id = dm_message_id
        return
    session.add(PodDraftDmMessage(
        event_id=event_id,
        participant_id=participant_id,
        kind=kind,
        round_num=round_num,
        match_id=match_id,
        dm_channel_id=dm_channel_id,
        dm_message_id=dm_message_id,
    ))


def dm_messages_for_match(session: Session, match_id: str) -> list[PodDraftDmMessage]:
    """All round_pairing DM messages tracked for a given match (both opponents)."""
    return list(session.execute(
        select(PodDraftDmMessage).where(
            PodDraftDmMessage.match_id == match_id,
            PodDraftDmMessage.kind == DM_KIND_ROUND,
        )
    ).scalars().all())


def dm_messages_for_round(session: Session, event_id: str, round_num: int) -> list[PodDraftDmMessage]:
    """All round_pairing DM messages tracked for a given (event, round)."""
    return list(session.execute(
        select(PodDraftDmMessage).where(
            PodDraftDmMessage.event_id == event_id,
            PodDraftDmMessage.round_num == round_num,
            PodDraftDmMessage.kind == DM_KIND_ROUND,
        )
    ).scalars().all())


def submit_deck_dm_for_participant(session: Session, participant_id: str) -> PodDraftDmMessage | None:
    return session.execute(
        select(PodDraftDmMessage).where(
            PodDraftDmMessage.participant_id == participant_id,
            PodDraftDmMessage.kind == DM_KIND_SUBMIT_DECK,
        )
    ).scalar_one_or_none()


def final_submit_deck_dm_for_participant(
    session: Session, participant_id: str,
) -> PodDraftDmMessage | None:
    return session.execute(
        select(PodDraftDmMessage).where(
            PodDraftDmMessage.participant_id == participant_id,
            PodDraftDmMessage.kind == DM_KIND_SUBMIT_DECK_FINAL,
        )
    ).scalar_one_or_none()


def participant_id_for_discord_user(
    session: Session, event_id: str, discord_id: str,
) -> str | None:
    return session.execute(
        select(PodDraftParticipant.id)
        .join(Player, Player.id == PodDraftParticipant.player_id)
        .where(
            PodDraftParticipant.event_id == event_id,
            Player.discord_id == discord_id,
        )
    ).scalar_one_or_none()


def participants_with_discord_for_event(session: Session, event_id: str) -> list[dict]:
    """Participant rows joined to Player.discord_id, with deck-state fields for Submit Deck DMs.
    Skips participants whose Player row isn't linked (no real Discord user)."""
    rows = session.execute(
        select(
            PodDraftParticipant.id,
            PodDraftParticipant.deck_colors,
            PodDraftParticipant.wants_draft_review,
            Player.discord_id,
        )
        .join(Player, Player.id == PodDraftParticipant.player_id)
        .where(PodDraftParticipant.event_id == event_id)
    ).all()
    return [
        {"participant_id": pid, "deck_colors": dc, "wants_draft_review": wr, "discord_id": did}
        for pid, dc, wr, did in rows
        if did
    ]


def thread_id_for_event(session: Session, event_id: str) -> str | None:
    return session.execute(
        select(PodDraftEvent.discord_thread_id).where(PodDraftEvent.id == event_id)
    ).scalar_one_or_none()


DM_SUBMISSION_WINDOW = timedelta(hours=24)


def active_event_for_discord_user_in_dm(session: Session, discord_id: str) -> tuple[str, str] | None:
    """Return (event_id, discord_thread_id) for the most recent pod-draft this user is in within the
    DM submission window, so deck-color/screenshot DMs route to the right pod. Window is finalization-
    agnostic: late deck submissions stay accepted (and stored) after the tournament finalizes; newest
    pod wins so a stale pod can't shadow a fresh one."""
    cutoff = datetime.now(timezone.utc) - DM_SUBMISSION_WINDOW
    row = session.execute(
        select(PodDraftEvent.id, PodDraftEvent.discord_thread_id)
        .join(PodDraftParticipant, PodDraftParticipant.event_id == PodDraftEvent.id)
        .join(Player, Player.id == PodDraftParticipant.player_id)
        .where(
            Player.discord_id == discord_id,
            PodDraftEvent.event_time >= cutoff,
        )
        .order_by(PodDraftEvent.event_time.desc())
        .limit(1)
    ).first()
    return (row[0], row[1]) if row else None


def is_pod_thread_champion(session: Session, thread_id: str, discord_id: str) -> bool:
    """True if (thread_id, discord_id) maps to a participant with placement=1."""
    row = session.execute(
        select(PodDraftParticipant.placement)
        .join(Player, Player.id == PodDraftParticipant.player_id)
        .join(PodDraftEvent, PodDraftEvent.id == PodDraftParticipant.event_id)
        .where(
            PodDraftEvent.discord_thread_id == thread_id,
            Player.discord_id == discord_id,
        )
    ).first()
    return bool(row and row[0] == 1)


def list_champions(session: Session, set_code: str | None = None) -> list[dict]:
    """Champions across all finalized events, ordered by event_date; caller partitions by set/format."""
    query = (
        select(PodDraftEvent, PodDraftParticipant, Player)
        .join(PodDraftParticipant, PodDraftParticipant.event_id == PodDraftEvent.id)
        .outerjoin(Player, Player.id == PodDraftParticipant.player_id)
        .where(PodDraftParticipant.placement == 1)
        .order_by(PodDraftEvent.event_date)
    )
    if set_code:
        query = query.where(func.upper(PodDraftEvent.set_code) == set_code.upper())

    rows = session.execute(query).all()
    return [
        {
            "event_name": event.name,
            "event_date": event.event_date,
            "set_code": event.set_code,
            "format_label": event.format_label,
            "champion_display_name": player.display_name if player else participant.display_name,
            "champion_draftmancer_name": participant.draftmancer_name,
            "player_slug": player.slug if player else None,
            "discord_id": player.discord_id if player else None,
            "draft_log_url": participant.draft_log_url,
        }
        for event, participant, player in rows
    ]


def participant_dm_info(session: Session, event_id: str) -> dict[str, ParticipantDmInfo]:
    """Map normalized draftmancer_name → ParticipantDmInfo for every participant in the event.

    arena_name sources from PodDraftParticipant.draftmancer_name — the handle the player actually
    set in the Draftmancer client for THIS session. For multi-account users this can differ from
    Player.arena_name (their stored display primary); the opponent DM should report the session-
    specific name so they look for the right Arena handle.
    """
    rows = session.execute(
        select(
            PodDraftParticipant.id,
            PodDraftParticipant.draftmancer_name,
            PodDraftParticipant.display_name,
            Player.discord_id,
        )
        .outerjoin(Player, Player.id == PodDraftParticipant.player_id)
        .where(PodDraftParticipant.event_id == event_id)
    ).all()
    info: dict[str, ParticipantDmInfo] = {}
    for participant_id, dm_name, display_name, discord_id in rows:
        key = normalize_player_name(dm_name) if dm_name else normalize_player_name(display_name)
        info[key] = ParticipantDmInfo(
            participant_id=participant_id,
            discord_id=discord_id,
            display_name=display_name,
            arena_name=dm_name,
        )
    return info


def set_participant_deck_colors(
    session: Session,
    discord_thread_id: str,
    discord_id: str,
    deck_colors: str,
) -> bool:
    """Save deck_colors on the (event, player) participant row. Returns False if the user isn't in this pod."""
    participant = session.execute(
        select(PodDraftParticipant)
        .join(Player, Player.id == PodDraftParticipant.player_id)
        .join(PodDraftEvent, PodDraftEvent.id == PodDraftParticipant.event_id)
        .where(
            PodDraftEvent.discord_thread_id == discord_thread_id,
            Player.discord_id == discord_id,
        )
    ).scalar_one_or_none()
    if participant is None:
        return False
    participant.deck_colors = deck_colors
    session.flush()
    return True


_RECORD_PATTERN = re.compile(r"\b[0-3]\s*[-:\s]\s*[0-3]\b")


def caption_has_record_pattern(caption: str | None) -> bool:
    return bool(caption and _RECORD_PATTERN.search(caption))


def capture_deck_screenshot(
    session: Session,
    discord_thread_id: str,
    discord_id: str,
    image_url: str,
    caption: str | None = None,
) -> str | None:
    """Capture (or overwrite) a participant's deck screenshot. Returns event_id on capture.

    Gating:
      - Picks must be done — event.current_round IS NOT NULL.
      - A stored caption that already matches the record-pattern locks the slot; a new image with
        no record-pattern is ignored. A new image WITH a record-pattern overwrites unconditionally
        (latest-record-wins).
      - Otherwise last-wins.
    """
    row = session.execute(
        select(PodDraftParticipant, PodDraftEvent.id, PodDraftEvent.current_round)
        .join(Player, Player.id == PodDraftParticipant.player_id)
        .join(PodDraftEvent, PodDraftEvent.id == PodDraftParticipant.event_id)
        .where(
            PodDraftEvent.discord_thread_id == discord_thread_id,
            Player.discord_id == discord_id,
        )
    ).first()
    if row is None:
        return None
    participant, event_id, current_round = row
    if current_round is None:
        log.info(f"[DECK] screenshot.too_early event={event_id} discord_id={discord_id} caption={caption!r}")
        return None
    new_has_record = caption_has_record_pattern(caption)
    existing_locked = caption_has_record_pattern(participant.deck_screenshot_caption)
    if not new_has_record and existing_locked:
        log.info(
            f"[DECK] screenshot.locked_ignored event={event_id} discord_id={discord_id} "
            f"locked_caption={participant.deck_screenshot_caption!r} new_caption={caption!r}"
        )
        return None
    replaced = participant.deck_screenshot_url is not None
    participant.deck_screenshot_url = image_url
    participant.deck_screenshot_caption = caption or None
    session.flush()
    log.info(
        f"[DECK] screenshot.stored event={event_id} discord_id={discord_id} round={current_round} "
        f"caption={caption!r} has_record={new_has_record} replaced={replaced}"
    )
    return event_id


def get_participant_deck_state(
    session: Session,
    discord_thread_id: str,
    discord_id: str,
) -> tuple[bool, str | None, bool | None]:
    """Return (is_participant, deck_colors, wants_draft_review). is_participant=False short-circuits the gate."""
    row = session.execute(
        select(PodDraftParticipant.deck_colors, PodDraftParticipant.wants_draft_review)
        .join(Player, Player.id == PodDraftParticipant.player_id)
        .join(PodDraftEvent, PodDraftEvent.id == PodDraftParticipant.event_id)
        .where(
            PodDraftEvent.discord_thread_id == discord_thread_id,
            Player.discord_id == discord_id,
        )
    ).first()
    if row is None:
        return False, None, None
    colors, wants_review = row
    return True, colors, wants_review


def set_participant_review_choice(
    session: Session,
    discord_thread_id: str,
    discord_id: str,
    wants_review: bool,
) -> bool:
    """Save wants_draft_review on the (event, player) participant row. Returns False if the user isn't in this pod."""
    participant = session.execute(
        select(PodDraftParticipant)
        .join(Player, Player.id == PodDraftParticipant.player_id)
        .join(PodDraftEvent, PodDraftEvent.id == PodDraftParticipant.event_id)
        .where(
            PodDraftEvent.discord_thread_id == discord_thread_id,
            Player.discord_id == discord_id,
        )
    ).scalar_one_or_none()
    if participant is None:
        return False
    participant.wants_draft_review = wants_review
    session.flush()
    return True




def player_pod_stats(session: Session, discord_id: str) -> dict | None:
    """Lifetime + per-set pod stats for a registered player; None if the discord_id isn't registered."""
    player = session.execute(
        select(Player).where(Player.discord_id == discord_id)
    ).scalar_one_or_none()
    if player is None:
        return None

    rows = session.execute(
        select(PodDraftEvent, PodDraftParticipant)
        .join(PodDraftParticipant, PodDraftParticipant.event_id == PodDraftEvent.id)
        .where(PodDraftParticipant.player_id == player.id)
    ).all()

    by_set: dict[str, dict] = {}
    lifetime_trophies = 0
    events_played = 0
    wins = 0
    losses = 0
    for event, participant in rows:
        if participant.placement is None:
            continue
        events_played += 1
        bucket = by_set.setdefault(event.set_code, {"events": 0, "wins": 0, "losses": 0, "trophies": 0})
        bucket["events"] += 1
        if participant.placement == 1:
            lifetime_trophies += 1
            bucket["trophies"] += 1
        if participant.record and "-" in participant.record:
            try:
                w_str, l_str = participant.record.split("-", 1)
                w, l = int(w_str), int(l_str)
                wins += w
                losses += l
                bucket["wins"] += w
                bucket["losses"] += l
            except ValueError:
                pass

    return {
        "player": player,
        "lifetime_trophies": lifetime_trophies,
        "trophies_by_set": {code: b["trophies"] for code, b in by_set.items() if b["trophies"]},
        "by_set": by_set,
        "events_played": events_played,
        "wins": wins,
        "losses": losses,
    }
