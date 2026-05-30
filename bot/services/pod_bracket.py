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


ROUND_RECORD_BUCKETS: dict[int, tuple[tuple[tuple[int, int], int], ...]] = {
    2: (((1, 0), 2), ((0, 1), 2)),
    3: (((2, 0), 1), ((1, 1), 2), ((0, 2), 1)),
}


def padding_slots(
    players: list[Player],
    completed: list[MatchOutcome],
    real_records: list[tuple[int, int]],
    paired_names: list[str],
    round_num: int,
) -> list[tuple[tuple[int, int], str | None, str | None]]:
    """Waiting-match slots that fill a bracket round to its full fixed slate, so a round always
    renders the same number of dropdowns. For the 8-player bracket each round's same-record buckets
    are fixed (R2: two 1-0, two 0-1; R3: one 2-0, two 1-1, one 0-2).

    `real_records` is the start-of-round (wins, losses) of each real match already created;
    `paired_names` are the players already in one. A player who has finished the prior round but
    isn't paired yet is named into a slot (earliest-ready first) so a partly-known match reads
    'Alice vs 1-0'; slots with no known side stay anonymous. Returns one (record, name_a, name_b) per
    missing match, best record first; name_* is None when that side is still unknown."""
    buckets = ROUND_RECORD_BUCKETS.get(round_num)
    if not buckets:
        return []
    ids = {p.id for p in players}
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

    have: dict[tuple[int, int], int] = {}
    for rec in real_records:
        have[rec] = have.get(rec, 0) + 1
    paired = set(paired_names)
    expected_prior = round_num - 1
    waiting = sorted(
        (pid for pid in ids if wins[pid] + losses[pid] == expected_prior and pid not in paired),
        key=lambda pid: last_index.get(pid, -1),
    )
    queues: dict[tuple[int, int], list[str]] = {}
    for pid in waiting:
        queues.setdefault((wins[pid], losses[pid]), []).append(pid)

    out: list[tuple[tuple[int, int], str | None, str | None]] = []
    for rec, expected in buckets:
        queue = queues.get(rec, [])
        for _ in range(max(expected - have.get(rec, 0), 0)):
            a = queue.pop(0) if queue else None
            b = queue.pop(0) if queue else None
            out.append((rec, a, b))
    return out


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
