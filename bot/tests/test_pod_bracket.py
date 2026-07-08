from bot.services import pod_bracket
from bot.services.pod_tournament import format_result_change
from bot.tests.pod_helpers import match, pairset, players


# --- supports -------------------------------------------------------------

def test_supports_only_eight():
    assert pod_bracket.supports(8) is True
    assert pod_bracket.supports(6) is False
    assert pod_bracket.supports(4) is False


# --- incremental_pairings -------------------------------------------------

def test_round2_pairs_winners_and_losers_from_first_two_results():
    roster = players(8)
    completed = [match(1, "p0", "p1", "p0"), match(1, "p2", "p3", "p2")]
    new = pod_bracket.incremental_pairings(roster, completed, [], 2, source_round_complete=False)
    assert pairset(new) == {frozenset({"p0", "p2"}), frozenset({"p1", "p3"})}


def test_round2_no_pairing_from_a_single_result():
    roster = players(8)
    completed = [match(1, "p0", "p1", "p0")]
    new = pod_bracket.incremental_pairings(roster, completed, [], 2, source_round_complete=False)
    assert new == []  # one winner + one loser, neither has a same-record partner yet


def test_round2_excludes_already_paired_players():
    roster = players(8)
    completed = [
        match(1, "p0", "p1", "p0"), match(1, "p2", "p3", "p2"),
        match(1, "p4", "p5", "p4"), match(1, "p6", "p7", "p6"),
    ]
    existing = [("p0", "p2"), ("p1", "p3")]  # already created
    new = pod_bracket.incremental_pairings(roster, completed, existing, 2, source_round_complete=False)
    assert pairset(new) == {frozenset({"p4", "p6"}), frozenset({"p5", "p7"})}


def test_round2_full_slate_when_all_reported():
    roster = players(8)
    completed = [
        match(1, "p0", "p1", "p0"), match(1, "p2", "p3", "p2"),
        match(1, "p4", "p5", "p4"), match(1, "p6", "p7", "p6"),
    ]
    new = pod_bracket.incremental_pairings(roster, completed, [], 2, source_round_complete=True)
    assert len(new) == 4
    winners, losers = {"p0", "p2", "p4", "p6"}, {"p1", "p3", "p5", "p7"}
    assert all(set(p) <= winners or set(p) <= losers for p in new)


def test_round3_trophy_opens_before_loser_bracket_finishes():
    roster = players(8)
    completed = [
        match(1, "p0", "p4", "p0"), match(1, "p1", "p5", "p1"),
        match(1, "p2", "p6", "p2"), match(1, "p3", "p7", "p3"),
        match(2, "p0", "p1", "p0"), match(2, "p2", "p3", "p2"),  # winner bracket only
    ]
    new = pod_bracket.incremental_pairings(roster, completed, [], 3, source_round_complete=False)
    # p0 and p2 are both 2-0 → the trophy match forms while p4-p7 haven't played R2 yet
    assert frozenset({"p0", "p2"}) in pairset(new)


def test_rematch_is_held_then_forced_when_source_complete():
    roster = players(4)
    completed = [
        match(1, "p0", "p1", "p0"), match(1, "p2", "p3", "p2"),
        match(2, "p2", "p0", "p2"), match(2, "p1", "p3", "p1"),
    ]
    # entering R3: 2-0 p2 (alone), 1-1 {p0, p1} who already met in R1, 0-2 p3 (alone)
    held = pod_bracket.incremental_pairings(roster, completed, [], 3, source_round_complete=False)
    assert held == []  # the only same-record pair is a rematch → wait
    forced = pod_bracket.incremental_pairings(roster, completed, [], 3, source_round_complete=True)
    assert pairset(forced) == {frozenset({"p0", "p1"})}  # forced so the bracket can't stall


def test_round3_holds_one_one_group_until_no_avoidable_rematch():
    # p0 and p1 met in R1; both go W-L / L-W and land at 1-1. The other two 1-1 players (p5, p6)
    # finish R2 first, so a greedy pairer would lock p5-p6 and strand p0-p1 into their R1 rematch.
    # The group must wait, then pair rematch-free.
    roster = players(8)
    r1 = [  # winners p0 p2 p4 p6, losers p1 p3 p5 p7
        match(1, "p0", "p1", "p0"), match(1, "p2", "p3", "p2"),
        match(1, "p4", "p5", "p4"), match(1, "p6", "p7", "p6"),
    ]
    r2_in_report_order = [  # winners' bracket p0/p2 & p4/p6, losers' bracket p1/p3 & p5/p7
        match(2, "p5", "p7", "p5"),  # p5 → 1-1, ready first
        match(2, "p4", "p6", "p4"),  # p6 → 1-1
        match(2, "p2", "p0", "p2"),  # p0 → 1-1 (its R1 win now offset by an R2 loss)
        match(2, "p1", "p3", "p1"),  # p1 → 1-1, ready last (completes R2)
    ]

    completed = list(r1)
    accumulated: list = []
    for i, result in enumerate(r2_in_report_order):
        completed.append(result)
        source_complete = i == len(r2_in_report_order) - 1
        new = pod_bracket.incremental_pairings(
            roster, completed, accumulated, 3, source_round_complete=source_complete,
        )
        accumulated += new

    one_one = {"p0", "p1", "p5", "p6"}
    one_one_pairs = [p for p in accumulated if set(p) <= one_one]

    assert frozenset({"p0", "p1"}) not in pairset(accumulated)  # never the R1 rematch
    assert len(one_one_pairs) == 2
    assert {pid for pair in one_one_pairs for pid in pair} == one_one


# --- padding_slots --------------------------------------------------------

def test_padding_all_unknown_before_any_result():
    roster = players(8)
    slots = pod_bracket.padding_slots(roster, [], [], [], 2)
    assert slots == [((1, 0), None, None), ((1, 0), None, None),
                     ((0, 1), None, None), ((0, 1), None, None)]


def test_padding_names_a_waiting_player():
    roster = players(8)
    completed = [match(1, "p0", "p1", "p0"), match(1, "p2", "p3", "p2"), match(1, "p4", "p5", "p4")]
    # two real R2 matches already exist (a winner pair + a loser pair)
    slots = pod_bracket.padding_slots(
        roster, completed, real_records=[(1, 0), (0, 1)],
        paired_names=["p0", "p2", "p1", "p3"], round_num=2,
    )
    assert slots == [((1, 0), "p4", None), ((0, 1), "p5", None)]


def test_padding_unknown_when_no_one_waiting():
    roster = players(8)
    completed = [match(1, "p0", "p1", "p0"), match(1, "p2", "p3", "p2")]
    slots = pod_bracket.padding_slots(
        roster, completed, real_records=[(1, 0), (0, 1)],
        paired_names=["p0", "p2", "p1", "p3"], round_num=2,
    )
    assert slots == [((1, 0), None, None), ((0, 1), None, None)]


def test_padding_pairs_two_waiting_players_in_one_slot():
    roster = players(8)
    completed = [
        match(1, "p0", "p4", "p0"), match(1, "p1", "p5", "p1"),
        match(1, "p2", "p6", "p2"), match(1, "p3", "p7", "p3"),
        match(2, "p0", "p1", "p0"), match(2, "p2", "p3", "p2"),
    ]
    # R3 has the 1-1 match created; the two 2-0 players (p0, p2) still wait for the trophy slot
    slots = pod_bracket.padding_slots(
        roster, completed, real_records=[(1, 1)],
        paired_names=["p1", "p3"], round_num=3,
    )
    assert slots[0] == ((2, 0), "p0", "p2")  # trophy slot names both finalists


def test_padding_empty_for_unsupported_round():
    roster = players(8)
    assert pod_bracket.padding_slots(roster, [], [], [], 1) == []
    assert pod_bracket.padding_slots(roster, [], [], [], 4) == []


# --- shared wording -------------------------------------------------------

def test_format_result_change_reported_leads_with_winner_and_score():
    phrase = format_result_change("Arcyl", "Bramblewick", "Bramblewick", "2-1")

    assert phrase.startswith("Bramblewick")
    assert "2-1" in phrase
    assert "Arcyl" in phrase


def test_format_result_change_cleared_names_both_without_score():
    phrase = format_result_change("Arcyl", "Bramblewick", None, None)

    assert "Arcyl" in phrase
    assert "Bramblewick" in phrase
    assert not any(ch.isdigit() for ch in phrase)


def test_format_result_change_drops_arena_ids_from_both_players():
    phrase = format_result_change("Arcyl#48087", "Bramblewick#13488", "Arcyl#48087", "2-0")

    assert phrase == "Arcyl wins 2-0 vs Bramblewick"
