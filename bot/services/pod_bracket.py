"""Record-based 'pod bracket' pairer — the fast-advance alternative to pod_swiss.

pod_swiss pairs a whole round at once, only after every match in the prior round is reported. The
bracket advances per match: the moment two players reach the same record they're paired into the
next round. For 8 players this is the classic draft bracket — winners play winners, losers play
losers, and the 2-0 Trophy Match starts as soon as both 2-0 players exist, without waiting for the
rest of the round.

Standings and tiebreakers still come from pod_swiss.compute_standings; this module only decides
pairings. Pure functions — the orchestration layer handles every side effect.
"""
from __future__ import annotations

from dataclasses import dataclass

from bot.services.pod_swiss import MatchOutcome, Player


BRACKET_POD_SIZE = 8


def supports(roster_size: int) -> bool:
    """The bracket is designed and tested for 8 players; other sizes should fall back to Swiss."""
    return roster_size == BRACKET_POD_SIZE


def incremental_pairings(
    players: list[Player],
    completed: list[MatchOutcome],
    existing_next: list[tuple[str, str]],
    target_round: int,
    *,
    source_round_complete: bool,
) -> list[tuple[str, str]]:
    """Return the *new* pairings to add to target_round given the completed earlier-round matches.

    A player is ready for target_round once they've finished exactly target_round-1 matches and
    aren't already paired into target_round. Ready players are grouped by record and paired
    earliest-finisher-first, skipping rematches. Leftover players wait for a non-rematch partner to
    become ready. When source_round_complete and only a rematch pairing remains, it's forced so the
    bracket never stalls. `completed` must be in chronological (report) order.
    """
    expected_prior = target_round - 1
    ids = {p.id for p in players}
    wins: dict[str, int] = {pid: 0 for pid in ids}
    losses: dict[str, int] = {pid: 0 for pid in ids}
    last_index: dict[str, int] = {}
    for idx, m in enumerate(completed):
        if m.player_a_id not in ids or m.player_b_id not in ids:
            continue
        wins[m.winner_id] += 1
        losses[m.loser_id] += 1
        last_index[m.player_a_id] = idx
        last_index[m.player_b_id] = idx

    already = {pid for pair in existing_next for pid in pair}
    ready = [
        p.id for p in players
        if wins[p.id] + losses[p.id] == expected_prior and p.id not in already
    ]
    ready.sort(key=lambda pid: last_index.get(pid, -1))

    groups: dict[tuple[int, int], list[str]] = {}
    for pid in ready:
        groups.setdefault((wins[pid], losses[pid]), []).append(pid)

    played = {frozenset((m.player_a_id, m.player_b_id)) for m in completed}
    new_pairings: list[tuple[str, str]] = []
    for record in sorted(groups, key=lambda r: (-r[0], r[1])):
        new_pairings.extend(_pair_group(groups[record], played, force=source_round_complete))
    return new_pairings


@dataclass(frozen=True)
class Slot:
    """One side of a projected match: a known 'player', or the 'winner'/'loser' of an undecided
    source matchup. `label` is the name or matchup; `record` is the prospective W-L."""
    kind: str
    label: str
    record: tuple[int, int]


def render_placeholder(a: Slot, b: Slot) -> str:
    """Full label for a projected match, in 'X vs Y' shape: known players by name, undecided sides by
    their pending record."""
    token = next((s for s in (a, b) if s.kind != "player"), None)
    if token is None:
        return f"{a.label} vs {b.label}"
    rec = f"{token.record[0]}-{token.record[1]}"
    player = next((s for s in (a, b) if s.kind == "player"), None)
    return f"{player.label} vs {rec}" if player else f"{rec} vs {rec}"


def projected_placeholders(
    players: list[Player],
    completed: list[MatchOutcome],
    source_matches: list[tuple[str, str, bool]],
    target_round: int,
    created_pairs: list[tuple[str, str]],
) -> list[tuple[Slot, Slot]]:
    """Projected (not-yet-reportable) matches that round out target_round's slate, as (Slot, Slot).

    Unreported `source_matches` (player_a_id, player_b_id, reported) supply undecided opponents;
    `created_pairs` are excluded. Waiting players pair with a pending winner/loser slot; leftover
    pending sources pair with each other.
    """
    ids = {p.id for p in players}
    name = {p.id: p.name for p in players}
    wins = {pid: 0 for pid in ids}
    losses = {pid: 0 for pid in ids}
    last_index: dict[str, int] = {}
    for idx, m in enumerate(completed):
        if m.player_a_id not in ids or m.player_b_id not in ids:
            continue
        wins[m.winner_id] += 1
        losses[m.loser_id] += 1
        last_index[m.player_a_id] = idx
        last_index[m.player_b_id] = idx

    already = {pid for pair in created_pairs for pid in pair}
    expected_prior = target_round - 1
    waiting = sorted(
        (pid for pid in ids if wins[pid] + losses[pid] == expected_prior and pid not in already),
        key=lambda pid: last_index.get(pid, -1),
    )

    pool: dict[tuple[int, int], dict[str, list[Slot]]] = {}

    def bucket(rec: tuple[int, int]) -> dict[str, list[Slot]]:
        return pool.setdefault(rec, {"players": [], "tokens": []})

    for pid in waiting:
        rec = (wins[pid], losses[pid])
        bucket(rec)["players"].append(Slot("player", name[pid], rec))

    for a_id, _b_id, reported in source_matches:
        if reported:
            continue
        w, l = wins.get(a_id, 0), losses.get(a_id, 0)
        bucket((w + 1, l))["tokens"].append(Slot("winner", "", (w + 1, l)))
        bucket((w, l + 1))["tokens"].append(Slot("loser", "", (w, l + 1)))

    pairs: list[tuple[Slot, Slot]] = []
    for rec in sorted(pool, key=lambda r: (-r[0], r[1])):
        ps, ts = pool[rec]["players"], pool[rec]["tokens"]
        while ps and ts:
            pairs.append((ps.pop(0), ts.pop(0)))
        while len(ts) >= 2:
            pairs.append((ts.pop(0), ts.pop(0)))
        while len(ps) >= 2:
            pairs.append((ps.pop(0), ps.pop(0)))
    return pairs


def _pair_group(
    pool: list[str], played: set[frozenset[str]], *, force: bool,
) -> list[tuple[str, str]]:
    """Greedily pair an earliest-first ordered same-record pool, skipping rematches. Players with no
    non-rematch partner wait; when `force`, leftover waiters are paired anyway so the bracket can't
    stall on a final forced rematch."""
    remaining = list(pool)
    pairs: list[tuple[str, str]] = []
    waiting: list[str] = []
    while remaining:
        a = remaining.pop(0)
        partner_idx = next(
            (i for i, b in enumerate(remaining) if frozenset((a, b)) not in played),
            None,
        )
        if partner_idx is None:
            waiting.append(a)
            continue
        pairs.append((a, remaining.pop(partner_idx)))
    if force:
        for i in range(0, len(waiting) - 1, 2):
            pairs.append((waiting[i], waiting[i + 1]))
    return pairs
