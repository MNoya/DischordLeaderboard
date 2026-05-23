"""Pull 17lands drafts and refresh derived aggregates.

``draft_events`` is the source of truth (additive, keyed on
``(player_id, seventeenlands_event_id)``). ``player_stats`` and the score
tables are derived — rebuilt from ``draft_events`` after each ingest.

Entry points:

* ``refresh_active_players`` — periodic + ``!refresh`` DM. Fetch window
  is ``min(today - PERIODIC_WINDOW_DAYS, ACTIVE_SET.start_date)``.
* ``refresh_active_players_all_sets`` — console-only full-history pull
  via ``bot/scripts/refresh_stats.py``. Used for formula changes, backfills,
  or suspected drift.
"""
from __future__ import annotations

import logging
import time as _time
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Protocol

import requests
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
from bot.services.seventeenlands import SUPPORTED_FORMATS, extract_event_row
from bot.sets import ACTIVE_SET_CODE

PERIODIC_WINDOW_DAYS = 7


_RAW_FORMAT_TO_LABEL: dict[str, str] = {
    fmt: g.label for g in DEFAULT_QUEUE_GROUPS for fmt in g.formats
}

logger = logging.getLogger(__name__)


class _DraftClient(Protocol):
    def fetch_drafts(self, token: str, start_date=..., end_date=..., expansion=...) -> list[dict]: ...


def _resolve_set_id(expansion: str, codes: list[str], sets_by_code: dict[str, MagicSet]) -> str | None:
    """First registered set whose code substring-matches the normalized expansion."""
    for code in codes:
        if code in expansion:
            return sets_by_code[code].id
    return None


def bulk_upsert_draft_events(
    session: Session,
    player_id: str,
    drafts: Iterable[dict],
    sets: Iterable[MagicSet],
) -> dict:
    """Persist every draft 17lands returned for one player. Single round-trip.

    Routes each draft to a registered set when expansion substring-matches;
    leaves ``set_id`` NULL otherwise (claimed later by ``/add-set``). Format is
    never filtered — unknown formats are persisted and reported so the owner
    can decide whether to add them to a ``QueueGroup``.

    Returns:
        ``{"touched_pairs": set[(player_id, set_id)],
           "unknown_formats": {fmt: count, ...},
           "unrouted_expansions": {expansion: count, ...},
           "events": int}``
    """
    sets_list = list(sets)
    sets_by_code = {s.code: s for s in sets_list}
    codes = list(sets_by_code.keys())

    rows: list[dict] = []
    touched_pairs: set[tuple[str, str]] = set()
    unknown_formats: dict[str, int] = {}
    unrouted_expansions: dict[str, int] = {}

    for draft in drafts:
        row = extract_event_row(draft)
        if row is None:
            continue
        set_id = _resolve_set_id(row["expansion"], codes, sets_by_code)
        row["player_id"] = player_id
        row["set_id"] = set_id

        rows.append(row)

        if set_id is None:
            unrouted_expansions[row["expansion"]] = unrouted_expansions.get(row["expansion"], 0) + 1
        else:
            touched_pairs.add((player_id, set_id))

        fmt = row["format"]
        if fmt not in SUPPORTED_FORMATS:
            unknown_formats[fmt] = unknown_formats.get(fmt, 0) + 1

    if rows:
        stmt = pg_insert(DraftEvent).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["player_id", "seventeenlands_event_id"],
            set_={
                "set_id": stmt.excluded.set_id,
                "format": stmt.excluded.format,
                "expansion": stmt.excluded.expansion,
                "wins": stmt.excluded.wins,
                "losses": stmt.excluded.losses,
                "is_trophy": stmt.excluded.is_trophy,
                "colors": stmt.excluded.colors,
                "start_rank": stmt.excluded.start_rank,
                "end_rank": stmt.excluded.end_rank,
                "started_at": stmt.excluded.started_at,
                "finished_at": stmt.excluded.finished_at,
                "fetched_at": func.now(),
            },
        )
        session.execute(stmt)

    return {
        "touched_pairs": touched_pairs,
        "unknown_formats": unknown_formats,
        "unrouted_expansions": unrouted_expansions,
        "events": len(rows),
    }


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

    upsert = bulk_upsert_draft_events(session, player.id, drafts, sets)
    touched_set_ids = {set_id for (_pid, set_id) in upsert["touched_pairs"]}

    active = next((s for s in sets if s.code == ACTIVE_SET_CODE), None)
    if active is not None:
        touched_set_ids.add(active.id)

    session.flush()
    for set_id in touched_set_ids:
        rebuild_player_stats(session, player.id, set_id)
        recompute_player_set_score(session, player.id, set_id)
        recompute_player_archetype_scores(session, player.id, set_id)
        recompute_player_format_archetype_scores(session, player.id, set_id)

    return {
        "status": "updated",
        "events": upsert["events"],
        "rows": len(touched_set_ids),
        "unknown_formats": upsert["unknown_formats"],
        "unrouted_expansions": upsert["unrouted_expansions"],
    }


def claim_orphan_drafts(session: Session, magic_set: MagicSet) -> set[str]:
    """Attach unrouted ``draft_events`` rows to ``magic_set`` when their expansion now matches.

    Run this after adding a set to ``bot/sets.py`` (and seeding it). Returns
    the set of player_ids that gained events, so the caller can rebuild
    ``player_stats`` and scores for each.

    Match rule mirrors the ingest path: ``magic_set.code`` substring of the
    normalized expansion. ``expansion_match`` aliases are normalized at ingest,
    so by the time the row is here ``expansion`` already equals the canonical code.
    """
    affected = session.execute(
        select(DraftEvent.player_id).where(
            DraftEvent.set_id.is_(None),
            DraftEvent.expansion.contains(magic_set.code),
        ).distinct()
    ).scalars().all()

    session.execute(
        text(
            """
            UPDATE draft_events
            SET set_id = :sid, fetched_at = now()
            WHERE set_id IS NULL AND expansion LIKE :pat
            """
        ),
        {"sid": magic_set.id, "pat": f"%{magic_set.code}%"},
    )
    session.expire_all()  # raw UPDATE bypassed the identity map
    return set(affected)


def rebuild_player_stats(session: Session, player_id: str, set_id: str) -> int:
    """Rebuild ``player_stats`` for one (player, set) from ``draft_events``.

    Source of truth for aggregates is ``draft_events``; this DELETE+INSERT-FROM-SELECT
    keeps the derived table fully consistent and is the only safe way to recompute
    after a partial-window fetch. Returns the row count written.
    """
    session.execute(
        delete(PlayerStats).where(
            PlayerStats.player_id == player_id,
            PlayerStats.set_id == set_id,
        )
    )
    result = session.execute(
        text(
            """
            INSERT INTO player_stats
                (id, player_id, set_id, format, expansion, events, wins, losses, games_played, trophies, last_fetched_at)
            SELECT gen_random_uuid()::text, player_id, set_id, format, expansion,
                   COUNT(*)::int, SUM(wins)::int, SUM(losses)::int, SUM(wins + losses)::int,
                   SUM(CASE WHEN is_trophy THEN 1 ELSE 0 END)::int,
                   now()
            FROM draft_events
            WHERE player_id = :pid AND set_id = :sid
            GROUP BY player_id, set_id, format, expansion
            """
        ),
        {"pid": player_id, "sid": set_id},
    )
    return result.rowcount or 0


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
        existing.score = score
        existing.trophies = total_trophies
        # Set explicitly so the 'Last updated' footer tracks every refresh, not just score changes
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
    """Recompute per-(player, set, archetype) scores from draft_events.

    Subset-replay: for each WUBRG-sorted main-color archetype the player has
    events in, run compute_score over just that subset and store the result.
    Plus a synthetic MULTI bucket for events with ≥4 effective colors.

    Wipes and rebuilds in one transaction — three round-trips total regardless
    of archetype count.
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
    rows_to_insert: list[dict] = []
    for arch, buckets in grouped.items():
        rows = list(buckets.values())
        rows_to_insert.append({
            "player_id": player_id,
            "set_id": set_id,
            "archetype": arch,
            "score": compute_score(rows),
            "trophies": sum(r["trophies"] for r in rows),
            "events": sum(r["events"] for r in rows),
            "wins": sum(r["wins"] for r in rows),
            "losses": sum(r["losses"] for r in rows),
            "last_calculated_at": now,
        })

    session.execute(
        delete(PlayerArchetypeScore).where(
            PlayerArchetypeScore.player_id == player_id,
            PlayerArchetypeScore.set_id == set_id,
        )
    )
    if rows_to_insert:
        session.execute(pg_insert(PlayerArchetypeScore).values(rows_to_insert))


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
    rows_to_insert: list[dict] = []
    for (label, arch), buckets in grouped.items():
        rows = list(buckets.values())
        rows_to_insert.append({
            "player_id": player_id,
            "set_id": set_id,
            "format_label": label,
            "archetype": arch,
            "score": compute_score(rows),
            "trophies": sum(r["trophies"] for r in rows),
            "events": sum(r["events"] for r in rows),
            "wins": sum(r["wins"] for r in rows),
            "losses": sum(r["losses"] for r in rows),
            "last_calculated_at": now,
        })

    session.execute(
        delete(PlayerFormatArchetypeScore).where(
            PlayerFormatArchetypeScore.player_id == player_id,
            PlayerFormatArchetypeScore.set_id == set_id,
        )
    )
    if rows_to_insert:
        session.execute(pg_insert(PlayerFormatArchetypeScore).values(rows_to_insert))


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
            "invalidated_players": [], "per_player": [], "unknown_formats": {},
            "unrouted_expansions": {}, "elapsed_s": 0.0,
            "status": "no_active_set",
        }
    fetch_start = min(date.today() - timedelta(days=PERIODIC_WINDOW_DAYS), active.start_date)
    return _refresh_active_with_window(session, client, fetch_start)


def refresh_active_players_all_sets(session: Session, client: _DraftClient) -> dict:
    """Full-history rebuild from the earliest registered set. Expensive — used by ``!refresh`` and the seed
    script when schema or scoring logic changes; not the scheduled tick.
    """
    sets = session.execute(select(MagicSet).order_by(MagicSet.start_date.asc())).scalars().all()
    if not sets:
        return {
            "updated": 0, "invalidated": 0, "errors": 0,
            "invalidated_players": [], "per_player": [], "unknown_formats": {},
            "unrouted_expansions": {}, "elapsed_s": 0.0,
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
        "unknown_formats": {},
        "unrouted_expansions": {},
        "elapsed_s": 0.0,
    }
    n_total = len(players)
    logger.info(f"refresh: {n_total} active player(s), fetch_start={fetch_start}")
    t_total = _time.monotonic()
    for idx, player in enumerate(players, start=1):
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
        for fmt, count in (result.get("unknown_formats") or {}).items():
            summary["unknown_formats"][fmt] = summary["unknown_formats"].get(fmt, 0) + count
        for exp, count in (result.get("unrouted_expansions") or {}).items():
            summary["unrouted_expansions"][exp] = summary["unrouted_expansions"].get(exp, 0) + count
        events_count = result.get("events", 0)
        extra = "" if status == "updated" else f" ({result.get('error', '')})".rstrip()
        logger.info(
            f"refresh: [{idx}/{n_total}] {player.display_name} "
            f"status={status} events={events_count} {elapsed:.1f}s{extra}"
        )
        summary["per_player"].append({
            "display_name": player.display_name,
            "status": status,
            "seconds": round(elapsed, 2),
        })
    summary["elapsed_s"] = round(_time.monotonic() - t_total, 2)
    logger.info(
        f"refresh: done. updated={summary['updated']} "
        f"invalidated={summary['invalidated']} errors={summary['errors']} "
        f"elapsed={summary['elapsed_s']:.1f}s "
        f"unknown_formats={summary['unknown_formats'] or '{}'} "
        f"unrouted_expansions={summary['unrouted_expansions'] or '{}'}"
    )
    return summary
