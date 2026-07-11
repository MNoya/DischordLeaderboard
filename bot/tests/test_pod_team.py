import pytest

from bot.services import pod_team


def test_assign_teams_alternates_by_seat_parity():
    seat_order = ["Ava", "Bram", "Cara", "Dex", "Eli", "Fern", "Gus", "Hana"]

    teams = pod_team.assign_teams(seat_order)

    assert [teams[n] for n in seat_order] == ["A", "B", "A", "B", "A", "B", "A", "B"]


def test_team_rosters_preserve_seat_order_within_team():
    seat_order = ["Ava", "Bram", "Cara", "Dex", "Eli", "Fern"]
    teams = pod_team.assign_teams(seat_order)

    team_a, team_b = pod_team.team_rosters(seat_order, teams)

    assert team_a == ["Ava", "Cara", "Eli"]
    assert team_b == ["Bram", "Dex", "Fern"]


@pytest.mark.parametrize("size,expected_matches", [(3, 3), (4, 4), (5, 5)])
def test_pair_round_is_full_cross_team_each_round(size, expected_matches):
    team_a = [f"A{i}" for i in range(size)]
    team_b = [f"B{i}" for i in range(size)]

    round_1 = pod_team.pair_round(team_a, team_b, 1)

    assert len(round_1) == expected_matches
    assert all(a in team_a and b in team_b for a, b in round_1)


def test_three_rounds_give_each_player_distinct_opponents():
    team_a = ["A0", "A1", "A2", "A3"]
    team_b = ["B0", "B1", "B2", "B3"]

    opponents = {a: set() for a in team_a}
    for round_num in (1, 2, 3):
        for a, b in pod_team.pair_round(team_a, team_b, round_num):
            opponents[a].add(b)

    assert all(len(opps) == 3 for opps in opponents.values())


def test_pair_round_rejects_unequal_teams():
    with pytest.raises(ValueError):
        pod_team.pair_round(["A0", "A1"], ["B0"], 1)


def test_team_match_wins_tallies_by_winner_team():
    teams = pod_team.assign_teams(["Ava", "Bram", "Cara", "Dex"])
    matches = [("Ava", "2-0"), ("Bram", "2-1"), ("Cara", "2-0")]

    a_wins, b_wins = pod_team.team_match_wins(matches, teams)

    assert (a_wins, b_wins) == (2, 1)


def test_team_winner_picks_higher_score_and_none_on_tie():
    assert pod_team.team_winner(5, 3) == pod_team.TEAM_A
    assert pod_team.team_winner(2, 4) == pod_team.TEAM_B
    assert pod_team.team_winner(3, 3) is None
