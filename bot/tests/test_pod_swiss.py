import random

import pytest

from bot.services.pod_swiss import (
    MatchOutcome,
    Player,
    compute_standings,
    pair_round,
)


def _players(n: int) -> list[Player]:
    return [Player(id=f"p{i}", name=f"Player{i}") for i in range(n)]


def _match(round_num: int, a: str, b: str, winner: str, score: str = "2-0") -> MatchOutcome:
    return MatchOutcome(round_num=round_num, player_a_id=a, player_b_id=b, winner_id=winner, score=score)


def test_round_1_pairs_all_players_once():
    roster = _players(6)
    pairings = pair_round(roster, [], 1, rng=random.Random(0))
    assert len(pairings) == 3
    flat = [pid for pair in pairings for pid in pair]
    assert sorted(flat) == [p.id for p in roster]


def test_round_1_is_random_with_rng():
    roster = _players(6)
    a = pair_round(roster, [], 1, rng=random.Random(1))
    b = pair_round(roster, [], 1, rng=random.Random(2))
    assert a != b  # different seeds → different pairings


def test_round_2_pairs_winners_with_winners_when_possible():
    roster = _players(4)
    r1 = [_match(1, "p0", "p1", "p0"), _match(1, "p2", "p3", "p2")]
    pairings = pair_round(roster, r1, 2)
    pair_set = {frozenset(p) for p in pairings}
    # Both winners (p0, p2) should be paired together; both losers (p1, p3) together
    assert frozenset({"p0", "p2"}) in pair_set
    assert frozenset({"p1", "p3"}) in pair_set


def test_no_rematch_constraint():
    roster = _players(4)
    r1 = [_match(1, "p0", "p1", "p0"), _match(1, "p2", "p3", "p2")]
    r2 = [_match(2, "p0", "p2", "p0"), _match(2, "p1", "p3", "p3")]
    pairings = pair_round(roster, r1 + r2, 3)
    pair_set = {frozenset(p) for p in pairings}
    # p0 has played p1 and p2 — must face p3
    assert frozenset({"p0", "p3"}) in pair_set
    assert frozenset({"p1", "p2"}) in pair_set


def test_pair_down_for_6_players():
    """After R1 with 3 winners + 3 losers, one winner must pair with one loser."""
    roster = _players(6)
    r1 = [
        _match(1, "p0", "p1", "p0"),
        _match(1, "p2", "p3", "p2"),
        _match(1, "p4", "p5", "p4"),
    ]
    pairings = pair_round(roster, r1, 2)
    pair_set = {frozenset(p) for p in pairings}
    winners = {"p0", "p2", "p4"}
    losers = {"p1", "p3", "p5"}
    cross = sum(1 for p in pair_set if len(p & winners) == 1 and len(p & losers) == 1)
    same_win = sum(1 for p in pair_set if p.issubset(winners))
    same_loss = sum(1 for p in pair_set if p.issubset(losers))
    # Exactly one cross pairing (pair-down), one winner-vs-winner, one loser-vs-loser
    assert cross == 1
    assert same_win == 1
    assert same_loss == 1


def test_compute_standings_basic_records():
    roster = _players(4)
    matches = [
        _match(1, "p0", "p1", "p0", "2-1"),
        _match(1, "p2", "p3", "p2", "2-0"),
        _match(2, "p0", "p2", "p0", "2-0"),
        _match(2, "p1", "p3", "p1", "2-1"),
    ]
    standings = compute_standings(roster, matches)
    by_id = {s.player_id: s for s in standings}
    assert (by_id["p0"].wins, by_id["p0"].losses) == (2, 0)
    assert (by_id["p1"].wins, by_id["p1"].losses) == (1, 1)
    assert (by_id["p2"].wins, by_id["p2"].losses) == (1, 1)
    assert (by_id["p3"].wins, by_id["p3"].losses) == (0, 2)
    # Top of standings is p0
    assert standings[0].player_id == "p0"


def test_compute_standings_omw_pct_breaks_tie():
    roster = _players(4)
    # p0 and p2 both go 1-0. p0 beats p1 (who is otherwise 0-1). p2 beats p3 (who beats p1 in a different match).
    # Hmm — let me set up a clean OMW% tiebreaker
    matches = [
        _match(1, "p0", "p1", "p0", "2-0"),
        _match(1, "p2", "p3", "p2", "2-0"),
        # Now: p1 and p3 both 0-1. p1's opponent (p0) has 1-0 = 100%. p3's opponent (p2) has 1-0 = 100%. Tied so far.
        # Add another round so OMW% diverges:
        _match(2, "p0", "p3", "p0", "2-0"),  # p0 now 2-0; p3 now 0-2
        _match(2, "p1", "p2", "p2", "2-0"),  # p2 now 2-0; p1 now 0-2
    ]
    standings = compute_standings(roster, matches)
    # p0 and p2 are both 2-0. p0's opponents: p1 (0-2), p3 (0-2). p2's opponents: p3 (0-2), p1 (0-2). Same OMW%.
    # Top 2 should be p0 and p2 in some order
    top_ids = {standings[0].player_id, standings[1].player_id}
    assert top_ids == {"p0", "p2"}


def test_compute_standings_gw_pct_uses_game_counts():
    roster = _players(2)
    matches = [_match(1, "p0", "p1", "p0", "2-1")]
    standings = compute_standings(roster, matches)
    p0 = next(s for s in standings if s.player_id == "p0")
    p1 = next(s for s in standings if s.player_id == "p1")
    # p0: 2 game wins / 3 games = 0.667
    assert p0.gw_pct == pytest.approx(2 / 3, rel=1e-3)
    # p1: 1 game win / 3 games = 0.333 (but min floor is 1/3 anyway)
    assert p1.gw_pct == pytest.approx(1 / 3, rel=1e-3)


def test_match_games_for_winner_and_loser():
    m = _match(1, "p0", "p1", "p0", "2-1")
    assert m.games_for("p0") == (2, 1)
    assert m.games_for("p1") == (1, 2)
    m2 = _match(1, "p2", "p3", "p3", "2-0")
    assert m2.games_for("p2") == (0, 2)
    assert m2.games_for("p3") == (2, 0)


def test_pair_round_raises_when_no_valid_pairing():
    # 4 players, all have played each other → no valid pairing for round 4
    roster = _players(4)
    matches = [
        _match(1, "p0", "p1", "p0"), _match(1, "p2", "p3", "p2"),
        _match(2, "p0", "p2", "p0"), _match(2, "p1", "p3", "p3"),
        _match(3, "p0", "p3", "p0"), _match(3, "p1", "p2", "p1"),
    ]
    with pytest.raises(ValueError):
        pair_round(roster, matches, 4)


def test_8_player_round_1_yields_4_pairings():
    roster = _players(8)
    pairings = pair_round(roster, [], 1, rng=random.Random(0))
    assert len(pairings) == 4
    flat = sorted(pid for pair in pairings for pid in pair)
    assert flat == [p.id for p in roster]


def test_8_player_round_2_pairs_within_brackets():
    roster = _players(8)
    r1 = [
        _match(1, "p0", "p1", "p0"),
        _match(1, "p2", "p3", "p2"),
        _match(1, "p4", "p5", "p4"),
        _match(1, "p6", "p7", "p6"),
    ]
    pairings = pair_round(roster, r1, 2)
    pair_set = {frozenset(p) for p in pairings}
    winners = {"p0", "p2", "p4", "p6"}
    losers = {"p1", "p3", "p5", "p7"}
    # All pairings should be winner-vs-winner or loser-vs-loser
    assert all(p.issubset(winners) or p.issubset(losers) for p in pair_set)
