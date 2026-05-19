"""Pull 17lands drafts and refresh PlayerStats + per-set scores.

One PlayerStats row per (player, set, format, expansion); the leaderboard rolls expansions up on read. Scoring
lives in ``bot.scoring`` so the formula can vary per set.

Two entry points:

* ``refresh_active_players`` — periodic auto-tick; pulls the last ``PERIODIC_WINDOW_DAYS`` days. Cheap.
  Flashback drafts in that window land in their own set's rows via the multi-set aggregator.
* ``refresh_active_players_all_sets`` — full rebuild from the earliest registered set; used by ``!refresh``
  and the seed script when schema or scoring logic changes.
"""
from __future__ import annotations

import logging
import time as _time
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Protocol

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.models import (
    DraftEvent,
    MagicSet,
    Player,
    PlayerArchetypeScore,
    PlayerFormatArchetypeScore,
    PlayerSetScore,
    PlayerStats,
)
from bot.scoring import DEFAULT_QUEUE_GROUPS, compute_score
from bot.services.seventeenlands import SUPPORTED_FORMATS, extract_events_for_set
from bot.sets import ACTIVE_SET_CODE, normalize_expansion

PERIODIC_WINDOW_DAYS = 7


_TRAD_LABEL = "Trad"

# Mirror the SQL _FORMAT_LABEL_CASE in public_player_format_breakdown
_RAW_FORMAT_TO_LABEL: dict[str, str] = {
    fmt: (_TRAD_LABEL if g.label == "Traditional" else g.label)
    for g in DEFAULT_QUEUE_GROUPS
    for fmt in g.formats
}

logger = logging.getLogger(__name__)


class _DraftClient(Protocol):
    def fetch_drafts(self, token: str, start_date=..., end_date=..., expansion=...) -> list[dict]: ...


def aggregate_by_set_format_expansion(drafts: Iterable[dict], sets: Iterable[MagicSet]) -> list[dict]:
    """One row per (set, format, expansion). Each draft is routed to the set whose code substring-matches its
    normalized expansion (Y26ECL → ECL, "Cube - Powered" → CUBE). Drafts with no match are logged and dropped;
    unsupported formats are skipped silently.
    """
    sets_by_code: dict[str, MagicSet] = {s.code: s for s in sets}
    codes = list(sets_by_code.keys())
    buckets: dict[tuple[str, str, str], dict] = {}
    dropped: dict[str, int] = {}

    for d in drafts:
        fmt = d.get("format")
        if fmt not in SUPPORTED_FORMATS:
            continue
        expansion = normalize_expansion(d.get("expansion") or "")
        matched: MagicSet | None = None
        for code in codes:
            if code in expansion:
                matched = sets_by_code[code]
                break
        if matched is None:
            dropped[expansion] = dropped.get(expansion, 0) + 1
            continue

        key = (matched.id, fmt, expansion)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = {
                "set_id": matched.id,
                "set_code": matched.code,
                "format": fmt,
                "expansion": expansion,
                "events": 0,
                "wins": 0,
                "losses": 0,
                "games_played": 0,
                "trophies": 0,
            }
            buckets[key] = bucket
        wins = int(d.get("wins") or 0)
        losses = int(d.get("losses") or 0)
        bucket["events"] += 1
        bucket["wins"] += wins
        bucket["losses"] += losses
        bucket["games_played"] += wins + losses
        if d.get("event_wins"):
            bucket["trophies"] += 1

    for exp, count in dropped.items():
        logger.info(f"refresh: dropped {count} draft(s) with unknown expansion {exp!r}")

    return list(buckets.values())


def refresh_player(
    session: Session,
    client: _DraftClient,
    player: Player,
    drafts: list[dict] | None = None,
    fetch_start: date | None = None,
) -> dict:
    if drafts is None:
        try:
            drafts = client.fetch_drafts(
                player.seventeenlands_token,
                start_date=fetch_start,
            )
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                player.token_invalid = True
                return {"status": "invalidated"}
            logger.warning(f"refresh: HTTP error for player {player.id}: {e}")
            return {"status": "error", "error": str(e)}
        except ValueError as e:
            # Signup verifies tokens, so a malformed 200 is a 17lands-side issue, not a bad token
            logger.warning(f"refresh: malformed response for player {player.id}: {e}")
            return {"status": "error", "error": str(e)}
        except requests.RequestException as e:
            logger.warning(f"refresh: network error for player {player.id}: {e}")
            return {"status": "error", "error": str(e)}

    sets = session.execute(select(MagicSet)).scalars().all()
    rows = aggregate_by_set_format_expansion(drafts, sets)
    now = datetime.now(timezone.utc)

    for row in rows:
        existing = session.execute(
            select(PlayerStats).where(
                PlayerStats.player_id == player.id,
                PlayerStats.set_id == row["set_id"],
                PlayerStats.format == row["format"],
                PlayerStats.expansion == row["expansion"],
            )
        ).scalar_one_or_none()

        if existing is None:
            session.add(
                PlayerStats(
                    player_id=player.id,
                    set_id=row["set_id"],
                    format=row["format"],
                    expansion=row["expansion"],
                    events=row["events"],
                    wins=row["wins"],
                    losses=row["losses"],
                    games_played=row["games_played"],
                    trophies=row["trophies"],
                    last_fetched_at=now,
                )
            )
        else:
            existing.events = row["events"]
            existing.wins = row["wins"]
            existing.losses = row["losses"]
            existing.games_played = row["games_played"]
            existing.trophies = row["trophies"]
            existing.last_fetched_at = now

    touched: dict[str, str] = {}
    for row in rows:
        touched[row["set_id"]] = row["set_code"]
    for set_id, set_code in touched.items():
        upsert_draft_events(session, player.id, set_id, drafts, set_code)

    active = next((s for s in sets if s.code == ACTIVE_SET_CODE), None)
    sets_to_recompute = set(touched.keys())
    if active is not None:
        sets_to_recompute.add(active.id)

    session.flush()
    for set_id in sets_to_recompute:
        recompute_player_set_score(session, player.id, set_id)
        recompute_player_archetype_scores(session, player.id, set_id)
        recompute_player_format_archetype_scores(session, player.id, set_id)
    return {"status": "updated", "rows": len(rows)}


def upsert_draft_events(
    session: Session,
    player_id: str,
    set_id: str,
    drafts: Iterable[dict],
    set_code: str,
) -> int:
    """Insert or update one DraftEvent per 17lands draft for this (player, set).

    Idempotent on (player_id, seventeenlands_event_id). Returns the count of
    events processed (inserts + updates).
    """
    events = extract_events_for_set(drafts, set_code)
    for event in events:
        existing = session.execute(
            select(DraftEvent).where(
                DraftEvent.player_id == player_id,
                DraftEvent.seventeenlands_event_id == event["seventeenlands_event_id"],
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(DraftEvent(player_id=player_id, set_id=set_id, **event))
        else:
            for k, v in event.items():
                setattr(existing, k, v)
    return len(events)


def recompute_player_set_score(session: Session, player_id: str, set_id: str) -> PlayerSetScore:
    """Recompute and upsert the score for one (player, set) from current PlayerStats."""
    rows = session.execute(
        select(PlayerStats).where(
            PlayerStats.player_id == player_id, PlayerStats.set_id == set_id
        )
    ).scalars().all()
    stats_dicts = [
        {
            "format": r.format,
            "events": r.events,
            "wins": r.wins,
            "losses": r.losses,
            "trophies": r.trophies,
        }
        for r in rows
    ]
    score = compute_score(stats_dicts)
    total_trophies = sum(r.trophies for r in rows)
    now = datetime.now(timezone.utc)

    existing = session.execute(
        select(PlayerSetScore).where(
            PlayerSetScore.player_id == player_id,
            PlayerSetScore.set_id == set_id,
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = PlayerSetScore(
            player_id=player_id, set_id=set_id, score=score, trophies=total_trophies,
            last_calculated_at=now,
        )
        session.add(existing)
    else:
        # Force-bump last_calculated_at so 'Last updated' tracks every refresh,
        # not just refreshes that changed the score (onupdate=func.now() only fires
        # when SQLAlchemy detects an actual UPDATE, which it skips for unchanged rows)
        existing.score = score
        existing.trophies = total_trophies
        existing.last_calculated_at = now
    return existing


_WUBRG = "WUBRG"

# Heavy-multicolor bucket — effective colors (main + splash) ≥ 4
MULTI = "MULTI"


def _normalize_archetype(colors: str | None) -> str:
    """WUBRG-sorted main colors. Splashes dropped. None/empty → ''."""
    if not colors:
        return ""
    main = "".join(c for c in colors if c.isupper())
    return "".join(sorted(main, key=_WUBRG.index))


def _effective_color_count(colors: str | None) -> int:
    """Distinct colors played (main + splash deduped)."""
    if not colors:
        return 0
    return len({c.upper() for c in colors if c.upper() in _WUBRG})


def _archetype_keys(colors: str | None) -> list[str]:
    """Buckets this event contributes to: main-color always, plus MULTI when effective ≥ 4."""
    keys = [_normalize_archetype(colors)]
    if _effective_color_count(colors) >= 4:
        keys.append(MULTI)
    return keys


def recompute_player_archetype_scores(
    session: Session, player_id: str, set_id: str
) -> None:
    """Recompute and upsert per-(player, set, archetype) scores.

    Groups the player's draft_events for this set by WUBRG-normalized main-color
    archetype, then runs compute_score on each subset (treating it as if those
    were the player's only events). Subset replay — *"if UW were your only
    deck, this is your score."*

    Stale rows for archetypes the player no longer has events in are deleted so
    a player who pivots away from BG doesn't keep a stale BG row forever.
    """
    events = session.execute(
        select(DraftEvent).where(
            DraftEvent.player_id == player_id,
            DraftEvent.set_id == set_id,
        )
    ).scalars().all()

    grouped: dict[str, dict[tuple[str, str], dict]] = {}
    for ev in events:
        bucket_key = (ev.format, ev.expansion)
        for arch in _archetype_keys(ev.colors):
            bucket = grouped.setdefault(arch, {}).setdefault(
                bucket_key,
                {
                    "format": ev.format,
                    "expansion": ev.expansion,
                    "events": 0,
                    "wins": 0,
                    "losses": 0,
                    "trophies": 0,
                },
            )
            bucket["events"] += 1
            bucket["wins"] += ev.wins
            bucket["losses"] += ev.losses
            if ev.is_trophy:
                bucket["trophies"] += 1

    now = datetime.now(timezone.utc)
    seen_archetypes: set[str] = set()

    for arch, buckets in grouped.items():
        rows = list(buckets.values())
        score = compute_score(rows)
        events_count = sum(r["events"] for r in rows)
        wins = sum(r["wins"] for r in rows)
        losses = sum(r["losses"] for r in rows)
        trophies = sum(r["trophies"] for r in rows)
        seen_archetypes.add(arch)

        existing = session.execute(
            select(PlayerArchetypeScore).where(
                PlayerArchetypeScore.player_id == player_id,
                PlayerArchetypeScore.set_id == set_id,
                PlayerArchetypeScore.archetype == arch,
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                PlayerArchetypeScore(
                    player_id=player_id,
                    set_id=set_id,
                    archetype=arch,
                    score=score,
                    trophies=trophies,
                    events=events_count,
                    wins=wins,
                    losses=losses,
                    last_calculated_at=now,
                )
            )
        else:
            existing.score = score
            existing.trophies = trophies
            existing.events = events_count
            existing.wins = wins
            existing.losses = losses
            existing.last_calculated_at = now

    # Drop archetype rows the player no longer has events in
    stale = session.execute(
        select(PlayerArchetypeScore).where(
            PlayerArchetypeScore.player_id == player_id,
            PlayerArchetypeScore.set_id == set_id,
            PlayerArchetypeScore.archetype.notin_(list(seen_archetypes)) if seen_archetypes
            else PlayerArchetypeScore.archetype.is_not(None),
        )
    ).scalars().all()
    for row in stale:
        session.delete(row)


def recompute_player_format_archetype_scores(
    session: Session, player_id: str, set_id: str
) -> None:
    """Recompute per-(player, set, format_label, archetype) scores from draft_events.

    Backs the combined format+colors leaderboard. format_label uses the same
    bucketing as public_player_format_breakdown (Premier, Trad, Sealed, Quick,
    LCQ Draft 1, LCQ Draft 2).
    """
    events = session.execute(
        select(DraftEvent).where(
            DraftEvent.player_id == player_id,
            DraftEvent.set_id == set_id,
        )
    ).scalars().all()

    grouped: dict[tuple[str, str], dict[tuple[str, str], dict]] = {}
    for ev in events:
        label = _RAW_FORMAT_TO_LABEL.get(ev.format)
        if label is None:
            continue
        bucket_key = (ev.format, ev.expansion)
        for arch in _archetype_keys(ev.colors):
            bucket = grouped.setdefault((label, arch), {}).setdefault(
                bucket_key,
                {
                    "format": ev.format,
                    "expansion": ev.expansion,
                    "events": 0,
                    "wins": 0,
                    "losses": 0,
                    "trophies": 0,
                },
            )
            bucket["events"] += 1
            bucket["wins"] += ev.wins
            bucket["losses"] += ev.losses
            if ev.is_trophy:
                bucket["trophies"] += 1

    now = datetime.now(timezone.utc)
    seen: set[tuple[str, str]] = set()

    for (label, arch), buckets in grouped.items():
        rows = list(buckets.values())
        score = compute_score(rows)
        events_count = sum(r["events"] for r in rows)
        wins = sum(r["wins"] for r in rows)
        losses = sum(r["losses"] for r in rows)
        trophies = sum(r["trophies"] for r in rows)
        seen.add((label, arch))

        existing = session.execute(
            select(PlayerFormatArchetypeScore).where(
                PlayerFormatArchetypeScore.player_id == player_id,
                PlayerFormatArchetypeScore.set_id == set_id,
                PlayerFormatArchetypeScore.format_label == label,
                PlayerFormatArchetypeScore.archetype == arch,
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                PlayerFormatArchetypeScore(
                    player_id=player_id,
                    set_id=set_id,
                    format_label=label,
                    archetype=arch,
                    score=score,
                    trophies=trophies,
                    events=events_count,
                    wins=wins,
                    losses=losses,
                    last_calculated_at=now,
                )
            )
        else:
            existing.score = score
            existing.trophies = trophies
            existing.events = events_count
            existing.wins = wins
            existing.losses = losses
            existing.last_calculated_at = now

    existing_rows = session.execute(
        select(PlayerFormatArchetypeScore).where(
            PlayerFormatArchetypeScore.player_id == player_id,
            PlayerFormatArchetypeScore.set_id == set_id,
        )
    ).scalars().all()
    for row in existing_rows:
        if (row.format_label, row.archetype) not in seen:
            session.delete(row)


def refresh_one_player_for_all_sets(session: Session, client: _DraftClient, player_id: str) -> dict:
    """Refresh a single player across every registered set in one 17lands fetch."""
    player = session.execute(select(Player).where(Player.id == player_id)).scalar_one_or_none()
    if player is None:
        return {"status": "no_player"}
    sets = session.execute(select(MagicSet).order_by(MagicSet.start_date.asc())).scalars().all()
    if not sets:
        return {"status": "no_sets"}
    return refresh_player(session, client, player, fetch_start=sets[0].start_date)


def refresh_active_players(session: Session, client: _DraftClient) -> dict:
    """Periodic refresh. Window: ``max(today - PERIODIC_WINDOW_DAYS, ACTIVE_SET.start_date)`` so a fresh
    rotation doesn't widen the fetch. Flashback drafts in that window route to their own set's rows.
    """
    active = session.execute(select(MagicSet).where(MagicSet.code == ACTIVE_SET_CODE)).scalar_one_or_none()
    if active is None:
        return {
            "updated": 0, "invalidated": 0, "errors": 0,
            "invalidated_players": [], "per_player": [], "elapsed_s": 0.0,
            "status": "no_active_set",
        }
    fetch_start = max(date.today() - timedelta(days=PERIODIC_WINDOW_DAYS), active.start_date)
    return _refresh_active_with_window(session, client, fetch_start)


def refresh_active_players_all_sets(session: Session, client: _DraftClient) -> dict:
    """Full-history rebuild from the earliest registered set. Expensive — used by ``!refresh`` and the seed
    script when schema or scoring logic changes; not the scheduled tick.
    """
    sets = session.execute(select(MagicSet).order_by(MagicSet.start_date.asc())).scalars().all()
    if not sets:
        return {
            "updated": 0, "invalidated": 0, "errors": 0,
            "invalidated_players": [], "per_player": [], "elapsed_s": 0.0,
            "status": "no_sets",
        }
    return _refresh_active_with_window(session, client, sets[0].start_date)


def _refresh_active_with_window(session: Session, client: _DraftClient, fetch_start: date) -> dict:
    players = session.execute(
        select(Player).where(Player.active.is_(True), Player.token_invalid.is_(False))
    ).scalars().all()

    summary: dict = {
        "updated": 0,
        "invalidated": 0,
        "errors": 0,
        "invalidated_players": [],
        "per_player": [],
        "elapsed_s": 0.0,
    }
    t_total = _time.monotonic()
    for player in players:
        t0 = _time.monotonic()
        result = refresh_player(session, client, player, fetch_start=fetch_start)
        # Commit per-player so a mid-run crash keeps already-fetched data and the token_invalid flag persists immediately
        session.commit()
        elapsed = _time.monotonic() - t0
        status = result.get("status") or "error"
        if status == "updated":
            summary["updated"] += 1
        elif status == "invalidated":
            summary["invalidated"] += 1
            summary["invalidated_players"].append(player.id)
        else:
            summary["errors"] += 1
        summary["per_player"].append({
            "display_name": player.display_name,
            "status": status,
            "seconds": round(elapsed, 2),
        })
    summary["elapsed_s"] = round(_time.monotonic() - t_total, 2)
    return summary
