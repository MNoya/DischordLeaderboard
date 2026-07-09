"""Pod draft persistence and matching logic — pure SQLAlchemy, no Discord or websocket deps."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import NamedTuple, Sequence

from sqlalchemy import any_, delete, func, select
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
from bot.slug import disambiguate_slug, slugify


log = logging.getLogger(__name__)


DM_KIND_ROUND = "round_pairing"
DM_KIND_SUBMIT_DECK = "submit_deck"
DM_KIND_SUBMIT_DECK_FINAL = "submit_deck_final"

FINALIZED_STATUSES = ("draft_done", "complete")


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


@dataclass(frozen=True)
class FinalStanding:
    """One participant's outcome at champion finalization."""
    draftmancer_name: str
    placement: int
    record: str
    eliminated_round: int | None


def is_championship(name: str | None) -> bool:
    """The season-closing Set Championship pod, recognized by its event name."""
    return bool(name) and "championship" in name.lower()


def _lookup_set_id(session: Session, set_code: str) -> str | None:
    return session.execute(
        select(MagicSet.id).where(func.upper(MagicSet.code) == set_code.upper())
    ).scalar_one_or_none()


def _build_draftmancer_session(session: Session, parsed: ParsedSeshEvent) -> str:
    """Compose a stable session id; prefer #N from the title, fall back to Month-Day; suffix collisions A/B/C.

    Custom formats drop the LLU prefix and lead with their own slug instead of a set code. The Set
    Championship gets a fixed `-Championship` base so its lobby URL stays clean across re-creates.
    """
    slug = pod_format.session_slug_for(parsed.set_code)
    if slug is not None:
        head = f"{slug}-{parsed.event_date:%y}"
    else:
        head = f"{settings.pod_draft_session_prefix}-{parsed.set_code}"

    if is_championship(parsed.name):
        base = f"{head}-Championship"
    elif parsed.event_number is not None:
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


_ARENA_ID_RE = re.compile(r"#[0-9?]+$")
_ARENA_ID_SQL = r"#[0-9?]+$"
_NAME_TOKEN_RE = re.compile(r"[\s()/\\,|-]+")


def normalize_player_name(name: str) -> str:
    """Strip markdown escape backslashes and the trailing MTG Arena suffix, lowercase for matching.
    The suffix may be a `#?????` placeholder typed by players who don't know their Arena number."""
    return _ARENA_ID_RE.sub("", name.replace("\\", "")).lower()


_ARENA_TOKEN_RE = re.compile(r"\s*#[0-9?]+(?=$|\s|\))")


def strip_arena_suffix(name: str) -> str:
    """Display name with the MTG Arena `#12345` discriminator removed, case preserved. For surfaces that
    show the friendly name (standings, reported results) rather than the pre-match Arena reference.
    Handles a trailing suffix (`Alice#48087`) and one embedded before a nickname (`Alias#13488 (Bob)`)."""
    stripped = _ARENA_TOKEN_RE.sub("", name).strip()
    return stripped or name


def has_arena_suffix(name: str) -> bool:
    return bool(name and _ARENA_TOKEN_RE.search(name))


def name_token_match(norm: str, field: str) -> bool:
    """True when norm appears as a standalone word token of field, e.g. `wonderland`
    in `Alice (Wonderland)`."""
    return len(norm) >= 3 and norm in _NAME_TOKEN_RE.split(field.lower())


_FUZZY_MIN_LEN = 5
_SUGGEST_MAX_EDITS = 2


def within_one_edit(a: str, b: str) -> bool:
    """True when `a` and `b` are within a single insertion, deletion, or substitution
    (Levenshtein distance ≤ 1). Catches the off-by-one Arena handle typo `jineteroj0` vs `jineterojo`."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    shorter, longer = (a, b) if len(a) < len(b) else (b, a)
    i = j = 0
    edited = False
    while i < len(shorter) and j < len(longer):
        if shorter[i] == longer[j]:
            i += 1
            j += 1
        elif edited:
            return False
        else:
            edited = True
            j += 1
    return True


def levenshtein(a: str, b: str) -> int:
    """Edit distance between two strings; a transposition counts as two edits."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def suggest_lobby_name(declared: str, live_names: Sequence[str]) -> str | None:
    """Closest live Draftmancer name to `declared` within a few edits, for a did-you-mean hint
    when /link-arena resolves to no seat in any active lobby. Catches transpositions like
    `sytlish`→`stylish` that within_one_edit rejects."""
    norm = normalize_player_name(declared)
    if len(norm) < _FUZZY_MIN_LEN:
        return None
    best_name = None
    best_dist = _SUGGEST_MAX_EDITS + 1
    for name in live_names:
        candidate = normalize_player_name(name)
        if len(candidate) < _FUZZY_MIN_LEN:
            continue
        dist = levenshtein(norm, candidate)
        if dist < best_dist:
            best_dist = dist
            best_name = name
    return best_name if best_dist <= _SUGGEST_MAX_EDITS else None


def _normalized_column(col):
    """SQL expression: lowercase a column and strip the trailing MTG Arena suffix."""
    return func.regexp_replace(func.lower(col), _ARENA_ID_SQL, "")


def classify_lobby_names(session: Session, names: Sequence[str]) -> list[tuple[str, str | None]]:
    """For each Draftmancer userName, return (arena_name, display_name) if linked else (arena_name, None)."""
    result = []
    for n in names:
        player = player_for_name(session, n)
        result.append((n, player.display_name if player else None))
    return result


def players_for_names(session: Session, names: Sequence[str]) -> list[tuple[str, Player | None]]:
    """Resolve each sesh attendee name to its Player (or None if unmatched), preserving order."""
    return [(n, player_for_name(session, n)) for n in names]


def player_for_name(session: Session, name: str) -> Player | None:
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

    for p in candidates:
        for field in (p.display_name or "", p.discord_username or ""):
            if name_token_match(norm, field):
                return p

    if len(norm) >= _FUZZY_MIN_LEN:
        near: list[Player] = []
        for p in candidates:
            for alias in (p.arena_aliases or []):
                if len(alias) >= _FUZZY_MIN_LEN and within_one_edit(norm, alias):
                    near.append(p)
                    break
        if len(near) == 1:
            return near[0]

    return None


def lobby_match_status(declared: str, player_id: str, live_names: Sequence[str]) -> tuple[bool, str | None]:
    """Whether a live lobby seat now resolves to `player_id`, plus a did-you-mean name when it doesn't.

    Mirrors the lobby-card classifier: matched is True exactly when some Draftmancer name in
    `live_names` resolves via player_for_name to the just-linked player. When unmatched, the second
    element is the closest live name to `declared` (or None), surfaced as a /link-arena typo hint."""
    with SessionLocal() as session:
        for name in live_names:
            player = player_for_name(session, name)
            if player is not None and player.id == player_id:
                return True, None
    return False, suggest_lobby_name(declared, live_names)


def attach_arena_alias(
    session: Session,
    *,
    discord_id: str,
    discord_username: str,
    display_name: str,
    avatar_hash: str | None,
    arena_name: str,
    overwrite: bool = False,
) -> tuple[str | None, str | None]:
    """Find-or-create the active player for `discord_id` and bind `arena_name` as a normalized alias.

    Returns (player_id, collision_player_id). On a clean link collision_player_id is None; when the
    alias already belongs to a different active player, player_id is None and collision_player_id
    names the owner. Shared by /link-arena and the lobby claim-seat button so the two never drift.

    Player.arena_name only ever holds a full ArenaID#12345 handle — a bare Draftmancer nickname is
    stored as an alias only, so it can't shadow the real handle in pairing displays. `overwrite` is
    the explicit /link-arena path: the user is declaring their handle, so it replaces whatever is
    stored.
    """
    normalized = normalize_player_name(arena_name)

    collision = session.execute(
        select(Player).where(
            Player.active.is_(True),
            Player.discord_id != discord_id,
            normalized == any_(Player.arena_aliases),
        ).limit(1)
    ).scalar_one_or_none()
    if collision is not None:
        return None, collision.id

    player = session.execute(
        select(Player).where(Player.discord_id == discord_id)
    ).scalar_one_or_none()
    if player is None:
        taken_slugs = set(session.execute(select(Player.slug)).scalars().all())
        player = Player(
            slug=disambiguate_slug(slugify(display_name), taken_slugs),
            discord_id=discord_id,
            discord_username=discord_username,
            display_name=display_name,
            avatar_hash=avatar_hash,
            arena_name=arena_name if full_arena_handle(arena_name) else None,
            arena_aliases=[normalized],
            active=True,
            leaderboard_opt_in=False,
        )
        session.add(player)
    else:
        if overwrite or (full_arena_handle(arena_name) and not full_arena_handle(player.arena_name)):
            player.arena_name = arena_name
        if normalized not in player.arena_aliases:
            player.arena_aliases = [*player.arena_aliases, normalized]
    session.flush()
    return player.id, None


def full_arena_handle(name: str | None) -> bool:
    """Whether `name` is a complete ArenaID#12345 handle rather than a bare Draftmancer nickname."""
    return "#" in (name or "")


def build_mock_session(session: Session, set_code: str) -> tuple[str, int]:
    """`LLU-<SET>-Mock-<N>` with N the next free per-set mock number. Collisions bump N, so two
    mocks opened back to back never share a Draftmancer lobby."""
    base = f"{settings.pod_draft_session_prefix}-{set_code.upper()}-Mock"
    taken = set(session.execute(
        select(PodDraftEvent.draftmancer_session).where(PodDraftEvent.draftmancer_session.like(f"{base}-%"))
    ).scalars().all())
    n = 1
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}", n


def record_mock_event(
    session: Session, *, set_code: str, event_time: datetime, discord_thread_id: str,
) -> PodDraftEvent:
    """Insert a kind='mock' pod event — an on-demand draft with no sesh post, no RSVPs, no rounds.
    Participants and draft logs are written by the manager once the Draftmancer draft completes."""
    code = set_code.upper()
    session_id, number = build_mock_session(session, code)
    event = PodDraftEvent(
        event_date=event_time.date(),
        event_time=event_time,
        set_id=_lookup_set_id(session, code),
        set_code=code,
        format_label=pod_format.label_for(code),
        name=f"{code} Mock Draft {number}",
        draftmancer_session=session_id,
        discord_thread_id=discord_thread_id,
        sesh_message_id=None,
        socket_status="pending",
        kind="mock",
    )
    session.add(event)
    session.flush()
    return event


_TABLE_SUFFIX_RE = re.compile(r"\s+(?:[-–]\s+)?Table\s+\d+\s*$", re.IGNORECASE)


def split_base_name(name: str) -> str:
    """The event name with any trailing ` - Table N` stripped, so splitting a Table 2 still bases new
    tables on the original pod name rather than nesting `... Table 2 - Table 3`."""
    return _TABLE_SUFFIX_RE.sub("", name).strip()


def next_table_index(session: Session, base_name: str) -> int:
    """Next free table number for `base_name`; the original pod is table 1, so the first split is 2."""
    names = session.execute(
        select(PodDraftEvent.name).where(PodDraftEvent.name.ilike(f"{base_name}%Table %"))
    ).scalars().all()
    highest = 1
    for name in names:
        match = re.search(r"Table\s+(\d+)\s*$", name or "", re.IGNORECASE)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def build_split_session(session: Session, source_session_id: str, table_index: int) -> str:
    """`<source session>-T<index>`, suffixing A/B/… on collision so re-creates never share a lobby."""
    base = f"{source_session_id}-T{table_index}"
    taken = set(session.execute(
        select(PodDraftEvent.draftmancer_session).where(PodDraftEvent.draftmancer_session.like(f"{base}%"))
    ).scalars().all())
    if base not in taken:
        return base
    for i in range(26):
        candidate = f"{base}-{chr(ord('A') + i)}"
        if candidate not in taken:
            return candidate
    n = 27
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def record_split_event(session: Session, *, source_event_id: str) -> PodDraftEvent:
    """Insert a kind='tournament' overflow table cloned from `source_event_id` — same set, format,
    pairings, seating, and event date, but its own Draftmancer session and no sesh RSVP. The roster
    arrives from the new lobby. `discord_thread_id` is a placeholder the caller overwrites once the
    thread exists (as record_mock_event does)."""
    source = session.get(PodDraftEvent, source_event_id)
    if source is None:
        raise ValueError(f"source pod event {source_event_id} not found")
    base_name = split_base_name(source.name)
    table_index = next_table_index(session, base_name)
    session_id = build_split_session(session, source.draftmancer_session, table_index)
    event = PodDraftEvent(
        event_date=source.event_date,
        event_time=datetime.now(timezone.utc),
        set_id=source.set_id,
        set_code=source.set_code,
        format_label=source.format_label,
        name=f"{base_name} - Table {table_index}",
        draftmancer_session=session_id,
        discord_thread_id="pending",
        sesh_message_id=None,
        socket_status="pending",
        kind="tournament",
        pairing_mode=source.pairing_mode,
        seating_mode=source.seating_mode,
    )
    session.add(event)
    session.flush()
    return event


def preview_split_target_sync(source_event_id: str) -> tuple[str, int] | None:
    """(base name, next table index) for the split claim card, or None when the source is gone."""
    with SessionLocal() as session:
        source = session.get(PodDraftEvent, source_event_id)
        if source is None:
            return None
        base = split_base_name(source.name)
        return base, next_table_index(session, base)


def draftmancer_url_for(session_id: str) -> str:
    """Compose the player-facing session URL from current settings at send time, so a host change
    reaches already-recorded events instead of fossilizing in the row."""
    return f"{settings.draftmancer_web_url}/?session={session_id}"


def record_event(session: Session, parsed: ParsedSeshEvent) -> PodDraftEvent:
    """Insert a pod_draft_event row plus one participant per sesh attendee."""
    set_id = _lookup_set_id(session, parsed.set_code) if parsed.set_code else None
    session_id = _build_draftmancer_session(session, parsed)

    event = PodDraftEvent(
        event_date=parsed.event_date,
        event_time=parsed.event_time,
        set_id=set_id,
        set_code=parsed.set_code,
        format_label=pod_format.label_for(parsed.set_code),
        name=parsed.name,
        draftmancer_session=session_id,
        discord_thread_id=parsed.discord_thread_id,
        sesh_message_id=parsed.sesh_message_id,
        socket_status="pending",
    )
    if is_championship(parsed.name):
        event.seating_mode = "leaderboard"
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
    if event is None or event.socket_status in FINALIZED_STATUSES:
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
    if event is None or event.socket_status in FINALIZED_STATUSES:
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


def load_event_seating_mode_sync(event_id: str) -> str | None:
    """Current seating_mode for a pod event, or None when missing."""
    with SessionLocal() as session:
        return session.execute(
            select(PodDraftEvent.seating_mode).where(PodDraftEvent.id == event_id)
        ).scalar_one_or_none()


def load_event_name_sync(event_id: str) -> str:
    with SessionLocal() as session:
        return session.execute(
            select(PodDraftEvent.name).where(PodDraftEvent.id == event_id)
        ).scalar_one_or_none() or "Pod Draft"


def load_event_sesh_message_id_sync(event_id: str) -> str | None:
    """sesh message id whose RSVP reactions drive a pod event, or None when missing."""
    with SessionLocal() as session:
        return session.execute(
            select(PodDraftEvent.sesh_message_id).where(PodDraftEvent.id == event_id)
        ).scalar_one_or_none()


def event_for_sesh_message_sync(sesh_message_id: str) -> tuple[str, str] | None:
    """(event_id, socket_status) for the event tracking this sesh message, or None when none does."""
    with SessionLocal() as session:
        row = session.execute(
            select(PodDraftEvent.id, PodDraftEvent.socket_status)
            .where(PodDraftEvent.sesh_message_id == sesh_message_id)
        ).first()
    return (row[0], row[1]) if row else None


def delete_event_sync(event_id: str) -> None:
    """Delete a pod event row; the cascade drops participants, matches, replays, and DM trackers."""
    with SessionLocal() as session:
        session.execute(delete(PodDraftEvent).where(PodDraftEvent.id == event_id))
        session.commit()


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


def load_event_seeding_context_sync(event_id: str) -> tuple[str | None, str | None, str]:
    """(seating_mode, thread_id, name) in one query — the fields the seeding-table refresh reads on every
    fire. name falls back to 'Pod Draft', the others to None when the event is missing."""
    with SessionLocal() as session:
        row = session.execute(
            select(PodDraftEvent.seating_mode, PodDraftEvent.discord_thread_id, PodDraftEvent.name)
            .where(PodDraftEvent.id == event_id)
        ).one_or_none()
    if row is None:
        return None, None, "Pod Draft"
    return row.seating_mode, row.discord_thread_id, row.name or "Pod Draft"


def search_event_names_sync(query: str, limit: int = 25) -> list[str]:
    """Most-recent-first event names matching a case-insensitive substring of `query`; empty query
    returns the most recent."""
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
    player = player_for_name(session, display_name)
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
        candidate = player_for_name(session, draftmancer_name or display_name)
        if candidate is None and draftmancer_name:
            candidate = player_for_name(session, display_name)
        if candidate is not None:
            found.player_id = candidate.id
            _adopt_session_arena_handle(candidate, draftmancer_name)

    session.flush()
    return found


def _adopt_session_arena_handle(player: Player, draftmancer_name: str | None) -> None:
    """Record the Draftmancer session handle on a matched Player that lacks one. Players who joined
    through 17lands carry no Arena handle (17lands exposes none), so their first pod — played under a
    full ArenaID#12345 name — is where we learn it. A handle already stored is never overwritten."""
    if not full_arena_handle(draftmancer_name):
        return
    if not full_arena_handle(player.arena_name):
        player.arena_name = draftmancer_name
    normalized = normalize_player_name(draftmancer_name)
    if normalized and normalized not in player.arena_aliases:
        player.arena_aliases = [*player.arena_aliases, normalized]


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
    """Apply placements/records to participants and mark socket_status='complete'. Draft-log URLs
    are written mid-draft by pod_draft_manager and intentionally left untouched here."""
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


def finalize_mock_event(session: Session, event_id: str) -> PodDraftEvent | None:
    """Mark a mock pod complete: no placements or records, just the done timestamp so the public view
    treats it as final. The site renders its seating + draft logs; there are no rounds to score."""
    event = session.get(PodDraftEvent, event_id)
    if event is None:
        return None
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


def delete_submit_deck_dm(session: Session, participant_id: str) -> None:
    row = submit_deck_dm_for_participant(session, participant_id)
    if row is not None:
        session.delete(row)


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
            Player.discord_id,
        )
        .join(Player, Player.id == PodDraftParticipant.player_id)
        .where(PodDraftParticipant.event_id == event_id)
    ).all()
    return [
        {"participant_id": pid, "deck_colors": dc, "discord_id": did}
        for pid, dc, did in rows
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
        }
        for event, participant, player in rows
    ]


def participant_dm_info(session: Session, event_id: str) -> dict[str, ParticipantDmInfo]:
    """Map normalized draftmancer_name → ParticipantDmInfo for every participant in the event.

    display_name prefers Player.display_name (the resolved Discord server nickname) over the
    participant row's display_name, which can carry a stale Arena-style handle. Pod DMs have no
    guild context, so the opponent line renders this name as text rather than a `<@id>` mention —
    a mention would resolve to the global username instead of the LLU server nickname.

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
            Player.display_name,
            Player.discord_id,
        )
        .outerjoin(Player, Player.id == PodDraftParticipant.player_id)
        .where(PodDraftParticipant.event_id == event_id)
    ).all()
    info: dict[str, ParticipantDmInfo] = {}
    for participant_id, dm_name, participant_dn, player_dn, discord_id in rows:
        key = normalize_player_name(dm_name) if dm_name else normalize_player_name(participant_dn)
        raw = player_dn or participant_dn
        info[key] = ParticipantDmInfo(
            participant_id=participant_id,
            discord_id=discord_id,
            display_name=strip_arena_suffix(raw) if raw else raw,
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


_RECORD_PATTERN = re.compile(r"\b([0-3])\s*[-:\s]\s*([0-3])\b")


def caption_has_record_pattern(caption: str | None) -> bool:
    return parse_caption_record(caption) is not None


def parse_caption_record(caption: str | None) -> str | None:
    """Normalized 'W-L' record from a deck caption ('2-1 rakdos stuff' -> '2-1'), or None."""
    if not caption:
        return None
    m = _RECORD_PATTERN.search(caption)
    if m is None:
        return None
    return f"{m.group(1)}-{m.group(2)}"


def capture_deck_screenshot(
    session: Session,
    discord_thread_id: str,
    discord_id: str,
    image_url: str,
    caption: str | None = None,
    colors: str | None = None,
) -> str | None:
    """Capture (or overwrite) a participant's deck screenshot. Returns event_id on capture.

    Gating:
      - Picks must be done — tournament pods set current_round once pairings begin; mock pods never
        run rounds, so draft completion (socket_status draft_done/complete) opens the slot instead.
      - A stored caption that already matches the record-pattern locks the slot; a new image with
        no record-pattern is ignored. A new image WITH a record-pattern overwrites unconditionally
        (latest-record-wins).
      - Once the championship has posted, a participant with a deck already on file is done — new
        images are ignored unless the caption carries a record pattern (intentional replacement).
      - Otherwise last-wins.

    `colors` (parsed from the caption by the caller) backfills deck_colors only when the player
    hasn't already reported them — an explicit color report always wins over a caption guess.
    """
    row = session.execute(
        select(
            PodDraftParticipant,
            PodDraftEvent.id,
            PodDraftEvent.kind,
            PodDraftEvent.current_round,
            PodDraftEvent.socket_status,
            PodDraftEvent.championship_posted_at,
        )
        .join(Player, Player.id == PodDraftParticipant.player_id)
        .join(PodDraftEvent, PodDraftEvent.id == PodDraftParticipant.event_id)
        .where(
            PodDraftEvent.discord_thread_id == discord_thread_id,
            Player.discord_id == discord_id,
        )
    ).first()
    if row is None:
        return None
    participant, event_id, kind, current_round, socket_status, championship_posted_at = row
    if kind == "mock":
        picks_done = socket_status in ("draft_done", "complete")
    else:
        picks_done = current_round is not None
    if not picks_done:
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
    if not new_has_record and championship_posted_at is not None and participant.deck_screenshot_url is not None:
        log.info(
            f"[DECK] screenshot.post_championship_ignored event={event_id} discord_id={discord_id} "
            f"caption={caption!r}"
        )
        return None
    replaced = participant.deck_screenshot_url is not None
    participant.deck_screenshot_url = image_url
    participant.deck_screenshot_caption = caption or None
    if colors and not participant.deck_colors:
        participant.deck_colors = colors
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
) -> tuple[bool, str | None]:
    """Return (is_participant, deck_colors). is_participant=False short-circuits the gate."""
    row = session.execute(
        select(PodDraftParticipant.deck_colors)
        .join(Player, Player.id == PodDraftParticipant.player_id)
        .join(PodDraftEvent, PodDraftEvent.id == PodDraftParticipant.event_id)
        .where(
            PodDraftEvent.discord_thread_id == discord_thread_id,
            Player.discord_id == discord_id,
        )
    ).first()
    if row is None:
        return False, None
    return True, row[0]




class PodSetSummary(NamedTuple):
    """A player's pod results for one set. ``trophies`` counts a 3-0 record OR a pod win
    (placement 1) — multiple per large pod, and a small pod's 2-1 winner still earns one.
    A 2-1 that won the pod is a trophy, not a ``wins_2_1``."""
    events: int
    wins: int
    losses: int
    trophies: int
    wins_2_1: int


def pod_scoring_counts(session: Session, set_code: str) -> dict[str, tuple[int, int]]:
    """Per active player: (trophy count, 2-1 count) for the set, keyed by player_id. 
    Pods are always public, no opt-in gate."""
    rows = session.execute(
        select(PodDraftParticipant.player_id, PodDraftParticipant.record, PodDraftParticipant.placement)
        .join(PodDraftEvent, PodDraftEvent.id == PodDraftParticipant.event_id)
        .join(Player, Player.id == PodDraftParticipant.player_id)
        .where(
            PodDraftEvent.set_code == set_code,
            Player.active.is_(True),
            PodDraftParticipant.placement.isnot(None),
        )
    ).all()
    by_player: dict[str, list[tuple[str | None, int | None]]] = {}
    for player_id, record, placement in rows:
        by_player.setdefault(player_id, []).append((record, placement))
    summaries = {pid: _summarize_pod_records(finishes) for pid, finishes in by_player.items()}
    return {pid: (s.trophies, s.wins_2_1) for pid, s in summaries.items()}


def pod_summary_by_set_for_player(session: Session, player_id: str) -> dict[str, PodSetSummary]:
    """One player's pod summary per set_code; no opt-in filter since it's their own stats."""
    rows = session.execute(
        select(PodDraftEvent.set_code, PodDraftParticipant.record, PodDraftParticipant.placement)
        .join(PodDraftParticipant, PodDraftParticipant.event_id == PodDraftEvent.id)
        .where(
            PodDraftParticipant.player_id == player_id,
            PodDraftParticipant.placement.isnot(None),
        )
    ).all()
    by_set: dict[str, list[tuple[str | None, int | None]]] = {}
    for set_code, record, placement in rows:
        by_set.setdefault(set_code, []).append((record, placement))
    return {sc: _summarize_pod_records(finishes) for sc, finishes in by_set.items()}


def _summarize_pod_records(finishes: list[tuple[str | None, int | None]]) -> PodSetSummary:
    """A trophy is a 3-0 record or a pod win (placement 1); a 2-1 that won is a trophy, not a 2-1."""
    wins = losses = trophies = wins_2_1 = 0
    for record, placement in finishes:
        won, lost = parse_record(record)
        wins += won
        losses += lost
        if record == "3-0" or placement == 1:
            trophies += 1
        elif record == "2-1":
            wins_2_1 += 1
    return PodSetSummary(len(finishes), wins, losses, trophies, wins_2_1)


def parse_record(record: str | None) -> tuple[int, int]:
    if not record or "-" not in record:
        return 0, 0
    w_str, l_str = record.split("-", 1)
    try:
        return int(w_str), int(l_str)
    except ValueError:
        return 0, 0
