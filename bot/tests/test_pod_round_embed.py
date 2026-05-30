import re

from bot.services.pod_tournament import (
    LAST_CHANCE,
    LOSERS,
    MIDDLE,
    NBSP,
    PAIR_UP,
    TROPHY,
    WINNERS,
    mark_trophy_match,
    round_embed,
    round_groups,
)


# --- grouping data model (presentation-free; stable across formatting changes) ---

def test_round2_eight_players_split_into_winners_and_losers():
    states = [
        _ms("Aria", "Caedmon", "1-0", "1-0"),
        _ms("Esk", "Gwyn", "1-0", "1-0"),
        _ms("Bryn", "Doryn", "0-1", "0-1"),
        _ms("Fenn", "Hale", "0-1", "0-1"),
    ]
    groups = round_groups(2, states)
    assert _kinds(groups) == [WINNERS, LOSERS]
    assert _pairs(groups[0][1]) == {frozenset(("Aria", "Caedmon")), frozenset(("Esk", "Gwyn"))}
    assert _pairs(groups[1][1]) == {frozenset(("Bryn", "Doryn")), frozenset(("Fenn", "Hale"))}


def test_round2_six_players_insert_pair_up_between_brackets():
    states = [
        _ms("Aria", "Caedmon", "1-0", "1-0"),
        _ms("Bryn", "Esk", "0-1", "1-0"),
        _ms("Doryn", "Fenn", "0-1", "0-1"),
    ]
    groups = round_groups(2, states)
    assert _kinds(groups) == [WINNERS, PAIR_UP, LOSERS]
    assert _pairs(groups[1][1]) == {frozenset(("Bryn", "Esk"))}


def test_round2_ten_players_two_brackets_plus_pair_up():
    states = [
        _ms("Aria", "Caedmon", "1-0", "1-0"),
        _ms("Esk", "Gwyn", "1-0", "1-0"),
        _ms("Iris", "Bryn", "1-0", "0-1"),
        _ms("Doryn", "Fenn", "0-1", "0-1"),
        _ms("Hale", "Juno", "0-1", "0-1"),
    ]
    groups = round_groups(2, states)
    assert _kinds(groups) == [WINNERS, PAIR_UP, LOSERS]
    assert [len(ms) for _, ms in groups] == [2, 1, 2]


def test_final_round_splits_trophy_middle_last_chance():
    states = [
        _ms("Aria", "Esk", "2-0", "2-0"),
        _ms("Bryn", "Caedmon", "1-1", "1-1"),
        _ms("Doryn", "Fenn", "1-1", "1-1"),
        _ms("Gwyn", "Hale", "0-2", "0-2"),
    ]
    mark_trophy_match(states, 3)
    groups = round_groups(3, states)
    assert _kinds(groups) == [TROPHY, MIDDLE, LAST_CHANCE]
    assert [len(ms) for _, ms in groups] == [1, 2, 1]
    assert _pairs(groups[0][1]) == {frozenset(("Aria", "Esk"))}


# --- rendering (one smoke test; the single place exact format is pinned) ---

def test_round2_render_smoke():
    states = [
        _ms("Aria", "Caedmon", "1-0", "1-0"),
        _ms("Bryn", "Esk", "0-1", "1-0"),
        _ms("Doryn", "Fenn", "0-1", "0-1"),
    ]
    assert _norm(round_embed(2, states).description) == (
        "⬆️ **1-0 Match**\n"
        "⚔️ Aria vs Caedmon\n"
        "\n"
        "🌉 **Pair Up Match**\n"
        "⚔️ Esk (1-0) vs Bryn (0-1)\n"
        "\n"
        "⬇️ **0-1 Match**\n"
        "⚔️ Doryn vs Fenn"
    )


def test_round1_seated_titles_by_seats_with_annotation():
    states = [_seated("Aria", "Bryn", 1, 5), _seated("Caedmon", "Doryn", 2, 6)]
    embed = round_embed(1, states)
    assert "by Seats" in embed.title
    assert "⚔️ Aria vs Bryn (1v5)" in _norm(embed.description)


def test_round1_without_seats_titles_random_and_drops_annotation():
    embed = round_embed(1, [_ms("Aria", "Bryn")])
    assert "(Random)" in embed.title
    assert "(1v" not in embed.description


def test_reported_and_skipped_lines_render():
    states = [
        _ms("Aria", "Caedmon", "1-0", "1-0", winner_name="Aria", score="2-1"),
        _ms("Esk", "Gwyn", "1-0", "1-0", winner_name="(skipped)"),
    ]
    desc = _norm(round_embed(2, states).description)
    assert "▫️ Aria wins 2-1 vs Caedmon" in desc
    assert "🚫 Not played: Esk vs Gwyn" in desc


def _ms(a: str, b: str, a_record: str = "0-0", b_record: str = "0-0", **extra) -> dict:
    state = {
        "match_id": f"{a}-{b}",
        "a_name": a, "b_name": b,
        "a_display": a, "b_display": b,
        "a_record": a_record, "b_record": b_record,
        "winner_name": None, "score": None,
    }
    state.update(extra)
    return state


def _seated(a: str, b: str, a_seat: int, b_seat: int) -> dict:
    return _ms(a, b, a_seat=a_seat, b_seat=b_seat)


def _kinds(groups) -> list[str]:
    return [kind for kind, _ in groups]


def _pairs(matches) -> set[frozenset[str]]:
    return {frozenset((m["a_name"], m["b_name"])) for m in matches}


def _norm(desc: str) -> str:
    """Collapse NBSP / space runs so render assertions don't pin exact whitespace."""
    return re.sub(f"[ {NBSP}]+", " ", desc)
