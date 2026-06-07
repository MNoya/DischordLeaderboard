"""Extraction and inference for /pod-backfill — reconstructing a pod event from its Discord thread.

Pure functions over scraped message snapshots and raw 17lands game dicts; no Discord client, no DB.
See spec/pod-backfill-handoff.md for the pipeline this implements.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Mapping, Sequence

from bot.services import pod_swiss
from bot.services.pod_drafts import normalize_player_name, parse_caption_record
from bot.services.pod_replays import extract_game_id, filter_and_sort_games, is_in_event_window, parse_game_time


@dataclass(frozen=True)
class ScrapedMessage:
    """Snapshot of one thread message — the command layer builds these from discord.Message."""
    author_id: str
    author_display: str
    author_is_bot: bool
    content: str
    image_url: str | None
    txt_attachments: tuple[tuple[str, str], ...]
    created_at: datetime


@dataclass(frozen=True)
class DeckPost:
    author_id: str
    author_display: str
    image_url: str
    caption: str | None
    record: str | None
    posted_at: datetime


@dataclass(frozen=True)
class ReplayGame:
    game_id: str
    game_time: datetime
    won: bool
    turns: int | None


@dataclass(frozen=True)
class InferredMatch:
    """A match derived by mirror-joining two players' 17lands games. wins reflect captured games
    only — 17lands drops games, so a 2-1 can surface as 1-1."""
    player_a: str
    player_b: str
    wins_a: int
    wins_b: int
    last_game_time: datetime
    round: int | None = None


@dataclass(frozen=True)
class MatchDraft:
    """One match in the confirmation workspace. source: 'db' | 'replay' | 'manual'."""
    round: int
    player_a: str
    player_b: str
    winner: str | None
    score: str | None
    reported_at: datetime | None
    source: str


def extract_deck_posts(messages: Sequence[ScrapedMessage]) -> dict[str, DeckPost]:
    """Latest deck image per author, mirroring the live capture gating: a record-captioned post
    locks the slot against later record-less images; a new record-captioned post always wins."""
    out: dict[str, DeckPost] = {}
    for m in sorted(messages, key=lambda m: m.created_at):
        if m.author_is_bot or m.image_url is None:
            continue
        caption = m.content.strip() or None
        record = parse_caption_record(caption)
        prev = out.get(m.author_id)
        if prev is not None and prev.record is not None and record is None:
            continue
        out[m.author_id] = DeckPost(
            author_id=m.author_id,
            author_display=m.author_display,
            image_url=m.image_url,
            caption=caption,
            record=record,
            posted_at=m.created_at,
        )
    return out


def extract_draft_log_attachment(messages: Sequence[ScrapedMessage]) -> tuple[str, str] | None:
    """(filename, url) of the latest DraftLog .txt posted in the thread; any .txt as fallback."""
    draft_logs: list[tuple[datetime, str, str]] = []
    other_txt: list[tuple[datetime, str, str]] = []
    for m in messages:
        for filename, url in m.txt_attachments:
            if not filename.lower().endswith(".txt"):
                continue
            bucket = draft_logs if "draftlog" in filename.lower() else other_txt
            bucket.append((m.created_at, filename, url))
    candidates = draft_logs or other_txt
    if not candidates:
        return None
    latest = max(candidates, key=lambda c: c[0])
    return latest[1], latest[2]


def games_from_17lands(raw_games: Sequence[dict], event_time: datetime | None) -> list[ReplayGame]:
    """Filter a user_game_list payload down to plausible pod games (event type, min turns, event-day
    window) and convert to ReplayGame, sorted by time."""
    in_window = [g for g in raw_games if is_in_event_window(g, event_time)]
    out: list[ReplayGame] = []
    for g in filter_and_sort_games(in_window):
        game_id = extract_game_id(g)
        game_time = parse_game_time(g.get("game_time"))
        if game_id is None or game_time is None:
            continue
        out.append(ReplayGame(
            game_id=game_id,
            game_time=game_time,
            won=bool(g.get("won")),
            turns=g.get("turns") if isinstance(g.get("turns"), int) else None,
        ))
    return out


MIRROR_WINDOW = timedelta(minutes=2)


def mirror_join(games_a: Sequence[ReplayGame], games_b: Sequence[ReplayGame]) -> list[tuple[ReplayGame, ReplayGame]]:
    """Pair player A's games with player B's mirror recordings of the same games: equal turn count,
    opposite result, timestamps within MIRROR_WINDOW. Backend port of the frontend findOpponentPov
    join; each game is consumed at most once."""
    used: set[str] = set()
    pairs: list[tuple[ReplayGame, ReplayGame]] = []
    for ga in games_a:
        for gb in games_b:
            if gb.game_id in used:
                continue
            if gb.turns != ga.turns or gb.won == ga.won:
                continue
            if abs(gb.game_time - ga.game_time) <= MIRROR_WINDOW:
                pairs.append((ga, gb))
                used.add(gb.game_id)
                break
    return pairs


def infer_matches(games_by_player: Mapping[str, Sequence[ReplayGame]]) -> list[InferredMatch]:
    """Mirror-join every player pair and collapse each joined set into one InferredMatch. Pod rounds
    are rematch-free, so all joined games between a pair belong to a single match. Rounds are then
    assigned greedily in time order: a match's round is one past the latest round either player has
    already been placed in."""
    names = sorted(games_by_player)
    matches: list[InferredMatch] = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            pairs = mirror_join(games_by_player[a], games_by_player[b])
            if not pairs:
                continue
            wins_a = sum(1 for ga, _ in pairs if ga.won)
            matches.append(InferredMatch(
                player_a=a,
                player_b=b,
                wins_a=wins_a,
                wins_b=len(pairs) - wins_a,
                last_game_time=max(ga.game_time for ga, _ in pairs),
            ))
    return _assign_rounds(matches)


def _assign_rounds(matches: list[InferredMatch]) -> list[InferredMatch]:
    last_round: dict[str, int] = {}
    out: list[InferredMatch] = []
    for m in sorted(matches, key=lambda m: m.last_game_time):
        round_num = max(last_round.get(m.player_a, 0), last_round.get(m.player_b, 0)) + 1
        last_round[m.player_a] = round_num
        last_round[m.player_b] = round_num
        out.append(replace(m, round=round_num))
    return out


REPORT_LAG = timedelta(minutes=3)
ROUND_FALLBACK = timedelta(minutes=55)
PLACEHOLDER_SCORE = "2-1"


def merge_matches(
    db_matches: Sequence[MatchDraft],
    inferred: Sequence[InferredMatch],
) -> list[MatchDraft]:
    """Fold replay-inferred matches into what the DB already holds. Replay evidence wins on score
    when it captured a complete match (a side reached 2 wins) — it corrected misreported bracket
    scores in the manual run. Partial replay coverage keeps the DB score; an inferred match with no
    DB row and no decisive winner stays winner-less for the confirmation step to settle."""
    merged: dict[tuple[int, frozenset[str]], MatchDraft] = {}
    for m in db_matches:
        merged[_match_key(m.round, m.player_a, m.player_b)] = m

    for inf in inferred:
        key = _match_key(inf.round, inf.player_a, inf.player_b)
        decisive = max(inf.wins_a, inf.wins_b) >= 2
        winner = None
        if inf.wins_a != inf.wins_b:
            winner = inf.player_a if inf.wins_a > inf.wins_b else inf.player_b
        score = f"{max(inf.wins_a, inf.wins_b)}-{min(inf.wins_a, inf.wins_b)}"
        reported_at = inf.last_game_time + REPORT_LAG

        existing = merged.get(key)
        if existing is None:
            merged[key] = MatchDraft(
                round=inf.round,
                player_a=inf.player_a,
                player_b=inf.player_b,
                winner=winner if decisive else None,
                score=score if decisive else None,
                reported_at=reported_at,
                source="replay",
            )
        elif decisive and (existing.winner != winner or existing.score != score):
            merged[key] = replace(existing, winner=winner, score=score, reported_at=reported_at, source="replay")
        else:
            merged[key] = replace(existing, reported_at=reported_at)

    return sorted(merged.values(), key=lambda m: (m.round, m.player_a))


def _match_key(round_num: int, a: str, b: str) -> tuple[int, frozenset[str]]:
    return round_num, frozenset((normalize_player_name(a), normalize_player_name(b)))


def fill_reported_ats(matches: Sequence[MatchDraft], event_time: datetime) -> list[MatchDraft]:
    """Give every match a realistic reported_at — replay round-attribution windows derive from these.
    Matches without replay coverage borrow the latest known time in their round; rounds with no
    coverage at all step ROUND_FALLBACK per round from the event start (or the prior round's anchor)."""
    anchors: dict[int, datetime] = {}
    for m in matches:
        if m.reported_at is not None:
            current = anchors.get(m.round)
            if current is None or m.reported_at > current:
                anchors[m.round] = m.reported_at

    prev_anchor = event_time
    out: list[MatchDraft] = []
    for round_num in sorted({m.round for m in matches}):
        anchor = anchors.get(round_num)
        if anchor is None:
            anchor = prev_anchor + ROUND_FALLBACK
        for m in [m for m in matches if m.round == round_num]:
            if m.reported_at is None:
                m = replace(m, reported_at=anchor)
            out.append(m)
        prev_anchor = anchor
    return out


def compute_placements(
    names: Sequence[str],
    matches: Sequence[MatchDraft],
    records: Mapping[str, str | None] | None = None,
) -> list[pod_swiss.Standing]:
    """Standings over the confirmed matches, same tiebreakers the live finalize uses. Matches still
    missing a winner or score are excluded — placements firm up as the admin fills gaps. With no
    completed matches at all (pre-bot reconstructions where pairings are unrecoverable), falls back
    to ordering by the seats' caption records; seats without a record stay unplaced."""
    players = [pod_swiss.Player(id=n, name=n) for n in names]
    outcomes = [
        pod_swiss.MatchOutcome(
            round_num=m.round,
            player_a_id=m.player_a,
            player_b_id=m.player_b,
            winner_id=m.winner,
            score=m.score,
        )
        for m in matches
        if m.winner and m.score
    ]
    if not outcomes and records:
        return _standings_from_records(names, records)
    return pod_swiss.compute_standings(players, outcomes)


def _standings_from_records(names: Sequence[str], records: Mapping[str, str | None]) -> list[pod_swiss.Standing]:
    recorded: list[tuple[str, int, int]] = []
    for name in names:
        record = records.get(name)
        if not record or "-" not in record:
            continue
        wins_raw, losses_raw = record.split("-", 1)
        try:
            recorded.append((name, int(wins_raw), int(losses_raw)))
        except ValueError:
            continue
    recorded.sort(key=lambda entry: (-entry[1], entry[2], entry[0].lower()))
    return [
        pod_swiss.Standing(
            rank=i + 1, player_id=name, player_name=name,
            wins=wins, losses=losses, omw_pct=0.0, gw_pct=0.0, ogw_pct=0.0,
        )
        for i, (name, wins, losses) in enumerate(recorded)
    ]
