"""Pod draft persistence and matching logic — pure SQLAlchemy, no Discord or websocket deps."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bot.config import settings
from bot.models import (
    MagicSet,
    Player,
    PodDraftEvent,
    PodDraftMatch,
    PodDraftParticipant,
)


@dataclass(frozen=True)
class ParticipantDmInfo:
    """Per-participant info for round-start DMs. Keyed by normalized draftmancer_name."""
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
    format_label: str | None
    name: str
    attendees: Sequence[str]
    sesh_message_id: str
    discord_thread_id: str


@dataclass(frozen=True)
class FinalStanding:
    """One participant's outcome at champion finalization."""
    draftmancer_name: str
    placement: int
    record: str
    eliminated_round: int | None
    draft_log_url: str | None


def _lookup_set_id(session: Session, set_code: str) -> str | None:
    return session.execute(
        select(MagicSet.id).where(func.upper(MagicSet.code) == set_code.upper())
    ).scalar_one_or_none()


def _build_draftmancer_session(session: Session, parsed: ParsedSeshEvent) -> str:
    """Compose a stable session id; prefer #N from the title, fall back to Month-Day; suffix collisions A/B/C."""
    prefix = settings.pod_draft_session_prefix
    if parsed.event_number is not None:
        base = f"{prefix}-{parsed.set_code}-{parsed.event_number}"
    else:
        month = parsed.event_date.strftime("%b")
        base = f"{prefix}-{parsed.set_code}-{month}-{parsed.event_date.day}"

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


def _normalize_player_name(name: str) -> str:
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

    Priority: exact lower(arena_name), then normalized display_name, then normalized discord_username.
    Normalization strips a trailing `#NNNN` MTG Arena suffix from both sides so `Noya#12345` matches `Noya`.
    """
    raw = name.lower()
    found = session.execute(
        select(Player)
        .where(Player.active.is_(True), func.lower(Player.arena_name) == raw)
        .limit(1)
    ).scalar_one_or_none()
    if found is not None:
        return found

    norm = _normalize_player_name(name)
    return session.execute(
        select(Player)
        .where(
            Player.active.is_(True),
            (_normalized_column(Player.display_name) == norm)
            | (_normalized_column(Player.discord_username) == norm),
        )
        .limit(1)
    ).scalar_one_or_none()


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
        format_label=parsed.format_label,
        name=parsed.name,
        draftmancer_session=session_id,
        draftmancer_url=url,
        discord_thread_id=parsed.discord_thread_id,
        sesh_message_id=parsed.sesh_message_id,
        socket_status="pending",
    )
    session.add(event)
    session.flush()

    for attendee in parsed.attendees:
        _add_attendee(session, event.id, attendee)
    session.flush()
    return event


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

    target_dn = _normalize_player_name(display_name)
    target_dm = _normalize_player_name(draftmancer_name) if draftmancer_name else None

    found: PodDraftParticipant | None = None
    if target_dm:
        for row in rows:
            if row.draftmancer_name and _normalize_player_name(row.draftmancer_name) == target_dm:
                found = row
                break
        if found is None:
            for row in rows:
                if _normalize_player_name(row.display_name) == target_dm:
                    found = row
                    break
    if found is None:
        for row in rows:
            if _normalize_player_name(row.display_name) == target_dn:
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
    """Apply placements/records/draft-log URLs to participants and mark socket_status='complete'."""
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
        participant.draft_log_url = standing.draft_log_url

    event.socket_status = "complete"
    session.flush()
    return event


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
    """Map normalized draftmancer_name → ParticipantDmInfo for every participant in the event."""
    rows = session.execute(
        select(
            PodDraftParticipant.draftmancer_name,
            PodDraftParticipant.display_name,
            Player.discord_id,
            Player.arena_name,
        )
        .outerjoin(Player, Player.id == PodDraftParticipant.player_id)
        .where(PodDraftParticipant.event_id == event_id)
    ).all()
    info: dict[str, ParticipantDmInfo] = {}
    for dm_name, display_name, discord_id, arena_name in rows:
        key = _normalize_player_name(dm_name) if dm_name else _normalize_player_name(display_name)
        info[key] = ParticipantDmInfo(
            discord_id=discord_id,
            display_name=display_name,
            arena_name=arena_name,
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


def capture_first_deck_screenshot(
    session: Session,
    discord_thread_id: str,
    discord_id: str,
    image_url: str,
    caption: str | None = None,
) -> str | None:
    """First-image-per-participant. Returns event_id on capture, None otherwise.

    No-op when the participant already has a deck_screenshot_url set, or the thread/user pair
    doesn't map to a registered participant.
    """
    row = session.execute(
        select(PodDraftParticipant, PodDraftEvent.id)
        .join(Player, Player.id == PodDraftParticipant.player_id)
        .join(PodDraftEvent, PodDraftEvent.id == PodDraftParticipant.event_id)
        .where(
            PodDraftEvent.discord_thread_id == discord_thread_id,
            Player.discord_id == discord_id,
        )
    ).first()
    if row is None:
        return None
    participant, event_id = row
    if participant.deck_screenshot_url:
        return None
    participant.deck_screenshot_url = image_url
    participant.deck_screenshot_caption = caption or None
    session.flush()
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
