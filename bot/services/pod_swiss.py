"""Swiss-tournament pairer + standings for pod drafts. Pure functions only; the manager handles side effects.

Inputs: roster of Player records + chronological list of MatchOutcome records.
Outputs: pairings as `[(player_a_id, player_b_id), ...]` and Standings sorted by wins → OMW% → GW% → OGW% → name.
Tiebreakers follow MTR §1.6: per-opponent terms in OMW%/OGW% are floored at 1/3.
"""
from __future__ import annotations

import random
from dataclasses import dataclass


_MIN_PCT = 1.0 / 3.0  # MTR floor for OMW% / OGW% per-opponent terms
_GAMES_TO_WIN_MATCH = 2  # Bo3


@dataclass(frozen=True)
class Player:
    id: str    # stable per-tournament identifier (we use draftmancer_name)
    name: str  # display name
    seat: int | None = None  # draft-table seat index (0-based); drives round-1 pairing


@dataclass(frozen=True)
class MatchOutcome:
    round_num: int
    player_a_id: str
    player_b_id: str
    winner_id: str
    score: str  # "2-0" or "2-1"

    @property
    def loser_id(self) -> str:
        return self.player_b_id if self.winner_id == self.player_a_id else self.player_a_id

    def games_for(self, player_id: str) -> tuple[int, int]:
        """Returns (games_won, games_lost) for player_id; score is always 'winner_games-loser_games'."""
        parts = self.score.split("-", 1)
        winner_games, loser_games = int(parts[0]), int(parts[1])
        if player_id == self.winner_id:
            return winner_games, loser_games
        return loser_games, winner_games


@dataclass(frozen=True)
class Standing:
    rank: int
    player_id: str
    player_name: str
    wins: int
    losses: int
    omw_pct: float
    gw_pct: float
    ogw_pct: float


def pair_round(
    players: list[Player],
    prior_matches: list[MatchOutcome],
    round_num: int,
    *,
    rng: random.Random | None = None,
) -> list[tuple[str, str]]:
    """Return pairings for round_num as a list of (player_a_id, player_b_id).

    Round 1 pairs by seat distance — seat N faces seat N+half, so each player meets whoever sat
    furthest from them at the table. When seats are unknown it falls back to a random shuffle.
    Later rounds sort by tiebreaker cascade and greedy-pair from the top, never re-pairing two
    players who have already met. Raises ValueError if no rematch-free pairing exists.
    """
    if len(players) < 2:
        return []
    if round_num == 1:
        if all(p.seat is not None for p in players):
            ordered = sorted(players, key=lambda p: p.seat)
            half = len(ordered) // 2
            return [(ordered[i].id, ordered[i + half].id) for i in range(half)]
        roster = list(players)
        (rng or random).shuffle(roster)
        return [(roster[i].id, roster[i + 1].id) for i in range(0, len(roster), 2)]

    standings = compute_standings(players, prior_matches)
    sorted_ids = [s.player_id for s in standings]
    played: set[frozenset[str]] = {frozenset((m.player_a_id, m.player_b_id)) for m in prior_matches}

    result = _pair_recursive(sorted_ids, played)
    if result is None:
        raise ValueError(f"no valid pairing for round {round_num}")
    return result


def _pair_recursive(
    queue: list[str], played: set[frozenset[str]],
) -> list[tuple[str, str]] | None:
    if not queue:
        return []
    if len(queue) % 2 != 0:
        return None
    a = queue[0]
    for i in range(1, len(queue)):
        b = queue[i]
        if frozenset((a, b)) in played:
            continue
        remaining = queue[1:i] + queue[i + 1:]
        sub = _pair_recursive(remaining, played)
        if sub is not None:
            return [(a, b)] + sub
    return None


def compute_standings(
    players: list[Player],
    matches: list[MatchOutcome],
) -> list[Standing]:
    """Returns standings sorted by wins → OMW% → GW% → OGW% → name."""
    by_id = {p.id: p for p in players}
    wins = {p.id: 0 for p in players}
    losses = {p.id: 0 for p in players}
    games_won = {p.id: 0 for p in players}
    games_lost = {p.id: 0 for p in players}
    opponents: dict[str, list[str]] = {p.id: [] for p in players}

    for m in matches:
        a, b = m.player_a_id, m.player_b_id
        if a not in by_id or b not in by_id:
            continue
        if m.winner_id == a:
            wins[a] += 1
            losses[b] += 1
        else:
            wins[b] += 1
            losses[a] += 1
        a_won, a_lost = m.games_for(a)
        b_won, b_lost = m.games_for(b)
        games_won[a] += a_won
        games_lost[a] += a_lost
        games_won[b] += b_won
        games_lost[b] += b_lost
        opponents[a].append(b)
        opponents[b].append(a)

    mw_pct: dict[str, float] = {}
    for pid in by_id:
        total = wins[pid] + losses[pid]
        mw_pct[pid] = max(_MIN_PCT, wins[pid] / total) if total > 0 else 0.0
    gw_pct: dict[str, float] = {}
    for pid in by_id:
        total_games = games_won[pid] + games_lost[pid]
        gw_pct[pid] = max(_MIN_PCT, games_won[pid] / total_games) if total_games > 0 else 0.0
    omw: dict[str, float] = {}
    ogw: dict[str, float] = {}
    for pid in by_id:
        opps = opponents[pid]
        omw[pid] = sum(mw_pct[o] for o in opps) / len(opps) if opps else 0.0
        ogw[pid] = sum(gw_pct[o] for o in opps) / len(opps) if opps else 0.0

    ranked = sorted(
        players,
        key=lambda p: (-wins[p.id], -omw[p.id], -gw_pct[p.id], -ogw[p.id], p.name.lower()),
    )
    return [
        Standing(
            rank=i + 1,
            player_id=p.id,
            player_name=p.name,
            wins=wins[p.id],
            losses=losses[p.id],
            omw_pct=omw[p.id],
            gw_pct=gw_pct[p.id],
            ogw_pct=ogw[p.id],
        )
        for i, p in enumerate(ranked)
    ]
