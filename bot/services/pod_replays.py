"""Capture 17lands game-history records for pod participants. See spec/pod-draft-replays.md."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Sequence
from uuid import uuid4

from sqlalchemy import or_, select

from bot.database import SessionLocal
from bot.models import PodDraftEvent, PodDraftMatch, PodDraftReplay
from bot.services.seventeenlands import SeventeenLandsClient


log = logging.getLogger(__name__)

_REPLAY_BASE_URL = "https://www.17lands.com"
_POD_EVENT_NAMES = frozenset({"DirectGameTournamentLimited", "DirectGameLimited"})
_MIN_TURNS = 3
_EVENT_WINDOW_HOURS = 6


async def fetch_and_persist_replays_for_player(
    client: SeventeenLandsClient,
    event_id: str,
    player_id: str,
    player_seat_name: str,
    token: str,
) -> int:
    if not token:
        return 0
    try:
        games = await asyncio.to_thread(client.fetch_user_games, token)
    except Exception:
        log.warning(f"17lands fetch failed for player {player_id} in event {event_id}", exc_info=True)
        return 0
    if not games:
        return 0
    try:
        return await asyncio.to_thread(
            _persist_replays_sync, event_id, player_id, player_seat_name, games,
        )
    except Exception:
        log.warning(f"persist_replays failed for player {player_id} in event {event_id}", exc_info=True)
        return 0


def attribute_games_to_rounds(
    games: Sequence[dict],
    player_matches: Sequence[PodDraftMatch],
    player_seat_name: str,
) -> dict[str, int]:
    """Assign each 17lands game to the round whose report window it falls in: after the player's
    previous reported result, up to this one plus a minute of grace. Best-effort, window-only — a
    player can't be paired into their next match until the previous result is reported (Swiss and
    bracket alike), so the window is decisive. Reported scores aren't consulted: 17lands drops games
    and players misreport 2-0 as 2-1, and missing replays cost more than a result reported late
    enough to file a game under the prior round. Skipped matches (score 0-0) form no window."""
    usable = _filter_and_sort_games(games)
    matches_in_round_order = sorted(player_matches, key=lambda m: m.round)

    out: dict[str, int] = {}
    prev_reported_at: datetime | None = None
    for m in matches_in_round_order:
        if m.reported_at is None or not m.winner_name or not m.score or m.score == "0-0":
            continue
        lower = prev_reported_at
        upper_with_grace = m.reported_at + timedelta(minutes=1)
        prev_reported_at = upper_with_grace
        eligible = [
            g for g in usable
            if (lower is None or _parse_game_time(g.get("game_time")) > lower)
            and _parse_game_time(g.get("game_time")) <= upper_with_grace
        ]
        if not eligible:
            log.info(f"[REPLAYS] attribute.empty_window round={m.round} player={player_seat_name!r}")
            continue
        for g in eligible:
            gid = _extract_game_id(g)
            if gid:
                out[gid] = m.round
    return out


def _persist_replays_sync(
    event_id: str,
    player_id: str,
    player_seat_name: str,
    games: Sequence[dict],
) -> int:
    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is None:
            log.warning(f"persist_replays: event {event_id} not found")
            return 0

        player_matches = session.execute(
            select(PodDraftMatch).where(
                PodDraftMatch.event_id == event_id,
                or_(
                    PodDraftMatch.player_a_name == player_seat_name,
                    PodDraftMatch.player_b_name == player_seat_name,
                ),
            )
        ).scalars().all()

        in_window = [g for g in games if _is_in_event_window(g, event.event_time)]
        attribution = attribute_games_to_rounds(in_window, player_matches, player_seat_name)

        count = 0
        for g in in_window:
            if g.get("event_name") not in _POD_EVENT_NAMES:
                continue
            gid = _extract_game_id(g)
            if not gid:
                continue
            gt = _parse_game_time(g.get("game_time"))
            if gt is None:
                continue
            raw_link = g.get("link") or ""
            full_link = (
                f"{_REPLAY_BASE_URL}{raw_link}" if raw_link.startswith("/") else raw_link
            )
            turns = g.get("turns") if isinstance(g.get("turns"), int) else None
            on_play = g.get("on_play") if isinstance(g.get("on_play"), bool) else None
            inferred = attribution.get(gid)

            existing = session.execute(
                select(PodDraftReplay).where(
                    PodDraftReplay.event_id == event_id,
                    PodDraftReplay.player_id == player_id,
                    PodDraftReplay.game_id == gid,
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(PodDraftReplay(
                    id=str(uuid4()),
                    event_id=event_id, player_id=player_id, game_id=gid,
                    link=full_link, game_time=gt,
                    won=bool(g.get("won")), turns=turns, on_play=on_play,
                    inferred_round=inferred,
                ))
                count += 1
            else:
                if existing.inferred_round != inferred and inferred is not None:
                    existing.inferred_round = inferred
                    count += 1
        session.commit()
        return count


def _filter_and_sort_games(games: Sequence[dict]) -> list[dict]:
    out: list[tuple[datetime, dict]] = []
    for g in games:
        if g.get("event_name") not in _POD_EVENT_NAMES:
            continue
        turns = g.get("turns")
        if not isinstance(turns, int) or turns < _MIN_TURNS:
            continue
        gt = _parse_game_time(g.get("game_time"))
        if gt is None:
            continue
        out.append((gt, g))
    out.sort(key=lambda x: x[0])
    return [g for _, g in out]


def _is_in_event_window(game: dict, event_time: datetime | None) -> bool:
    if event_time is None:
        return True
    gt = _parse_game_time(game.get("game_time"))
    if gt is None:
        return False
    delta = abs((gt - event_time).total_seconds()) / 3600.0
    return delta <= _EVENT_WINDOW_HOURS


def _extract_game_id(game: dict) -> str | None:
    link = game.get("link") or ""
    parts = link.split("/")
    return parts[-2] if len(parts) >= 2 and parts[-2] else None


def _parse_game_time(raw: str | None) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
