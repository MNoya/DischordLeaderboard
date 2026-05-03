"""Refresh `PlayerStats` rows from 17lands data.

One row per (player, set, format, expansion). The leaderboard rolls up
expansions on read; we keep them split here so per-expansion detail stays
recoverable. Rating is intentionally not computed here — the formula may
vary per set and is owned elsewhere.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, Protocol

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.models import MagicSet, Player, PlayerSetScore, PlayerStats
from bot.scoring import compute_score
from bot.services.seventeenlands import SUPPORTED_FORMATS

logger = logging.getLogger(__name__)


class _DraftClient(Protocol):
    def fetch_drafts(self, token: str, start_date=...) -> list[dict]: ...


def aggregate_by_format_and_expansion(
    drafts: Iterable[dict], set_code: str
) -> list[dict]:
    """One row per (format, expansion) present in the drafts.

    Filters: format must be in SUPPORTED_FORMATS, and ``set_code`` must be a
    substring of the draft's expansion (so Y26ECL matches set ECL — same as
    ``aggregate_for_set``). Expansion strings are preserved verbatim.
    """
    buckets: dict[tuple[str, str], dict] = {}
    for d in drafts:
        fmt = d.get("format")
        if fmt not in SUPPORTED_FORMATS:
            continue
        expansion = d.get("expansion") or ""
        if set_code not in expansion:
            continue
        key = (fmt, expansion)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = {
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
    return list(buckets.values())


def refresh_player(
    session: Session,
    client: _DraftClient,
    player: Player,
    magic_set: MagicSet,
) -> dict:
    try:
        drafts = client.fetch_drafts(
            player.seventeenlands_token, start_date=magic_set.start_date
        )
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            player.token_invalid = True
            return {"status": "invalidated"}
        logger.warning("refresh: HTTP error for player %s: %s", player.id, e)
        return {"status": "error", "error": str(e)}
    except ValueError as e:
        # Signup verifies tokens, so a malformed 200 is a 17lands-side issue, not a bad token
        logger.warning("refresh: malformed response for player %s: %s", player.id, e)
        return {"status": "error", "error": str(e)}
    except requests.RequestException as e:
        logger.warning("refresh: network error for player %s: %s", player.id, e)
        return {"status": "error", "error": str(e)}

    rows = aggregate_by_format_and_expansion(drafts, magic_set.code)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for row in rows:
        existing = session.execute(
            select(PlayerStats).where(
                PlayerStats.player_id == player.id,
                PlayerStats.set_id == magic_set.id,
                PlayerStats.format == row["format"],
                PlayerStats.expansion == row["expansion"],
            )
        ).scalar_one_or_none()

        if existing is None:
            session.add(
                PlayerStats(
                    player_id=player.id,
                    set_id=magic_set.id,
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

    session.flush()
    recompute_player_set_score(session, player.id, magic_set.id)
    return {"status": "updated", "rows": len(rows)}


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

    existing = session.execute(
        select(PlayerSetScore).where(
            PlayerSetScore.player_id == player_id,
            PlayerSetScore.set_id == set_id,
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = PlayerSetScore(
            player_id=player_id, set_id=set_id, score=score, trophies=total_trophies,
        )
        session.add(existing)
    else:
        existing.score = score
        existing.trophies = total_trophies
    return existing


def refresh_one_player_for_current_set(
    session: Session, client: _DraftClient, player_id: str
) -> dict:
    """Refresh a single player's stats for whatever set is currently active.

    "Current" is resolved from ACTIVE_SET_CODE in bot/sets.py.
    """
    from bot.sets import ACTIVE_SET_CODE

    magic_set = session.execute(
        select(MagicSet).where(MagicSet.code == ACTIVE_SET_CODE)
    ).scalar_one_or_none()
    if magic_set is None:
        return {"status": "no_current_set"}
    player = session.execute(
        select(Player).where(Player.id == player_id)
    ).scalar_one_or_none()
    if player is None:
        return {"status": "no_player"}
    return refresh_player(session, client, player, magic_set)


def refresh_active_players(
    session: Session, client: _DraftClient, magic_set: MagicSet
) -> dict:
    players = session.execute(
        select(Player).where(Player.active.is_(True), Player.token_invalid.is_(False))
    ).scalars().all()

    summary: dict = {"updated": 0, "invalidated": 0, "errors": 0, "invalidated_players": []}
    for player in players:
        result = refresh_player(session, client, player, magic_set)
        # Commit per-player so a mid-run crash keeps already-fetched data and the token_invalid flag persists immediately
        session.commit()
        status = result.get("status")
        if status == "updated":
            summary["updated"] += 1
        elif status == "invalidated":
            summary["invalidated"] += 1
            summary["invalidated_players"].append(player.id)
        else:
            summary["errors"] += 1
    return summary
