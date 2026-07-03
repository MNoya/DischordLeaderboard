from types import SimpleNamespace

from bot.services.pod_tournament import (
    ANNOUNCEMENT_TOP_N,
    ParticipantDeckData,
    deck_complete,
    incomplete_top_decks,
    normalize_player_name,
    build_deck_ping,
    deck_missing_parts,
    format_reported_result,
)


def test_deck_complete_requires_colors_and_screenshot():
    assert deck_complete(_deck("WU", "http://img/x.png"))
    assert not deck_complete(_deck("WU", None))
    assert not deck_complete(_deck(None, "http://img/x.png"))
    assert not deck_complete(None)


def test_championship_clear_when_top_finishers_all_complete():
    standings = _standings("Aria", "Bryn", "Caedmon", "Doryn", "Esk")
    deck_data = _complete_decks("Aria", "Bryn", "Caedmon", "Doryn")
    assert incomplete_top_decks(standings, deck_data) == []


def test_championship_waits_on_missing_top_finisher():
    standings = _standings("Aria", "Bryn", "Caedmon", "Doryn")
    deck_data = _complete_decks("Aria", "Bryn", "Caedmon")
    deck_data[normalize_player_name("Doryn")] = _deck("WU", None)
    assert incomplete_top_decks(standings, deck_data) == ["Doryn"]


def test_championship_ignores_players_outside_top_n():
    extra = "Faron"
    standings = _standings("Aria", "Bryn", "Caedmon", "Doryn", extra)
    deck_data = _complete_decks("Aria", "Bryn", "Caedmon", "Doryn")
    assert incomplete_top_decks(standings, deck_data) == []


def test_championship_requires_all_when_pod_smaller_than_top_n():
    standings = _standings("Aria", "Bryn", "Caedmon")
    assert len(standings) < ANNOUNCEMENT_TOP_N
    deck_data = _complete_decks("Aria", "Bryn")
    assert incomplete_top_decks(standings, deck_data) == ["Caedmon"]


def test_deck_missing_parts_reports_each_gap():
    assert deck_missing_parts(_deck("WU", "http://img/x.png")) == []
    assert deck_missing_parts(_deck("WU", None)) == ["screenshot"]
    assert deck_missing_parts(_deck(None, "http://img/x.png")) == ["colors"]
    assert deck_missing_parts(_deck(None, None)) == ["screenshot", "colors"]
    assert deck_missing_parts(None) == ["screenshot", "colors"]


def test_deck_ping_is_action_forward_split_by_audience():
    text = build_deck_ping((["1"], ["1", "2"]), (["3"], ["3"]), "https://limitedlevelups.com/pods/pod-7")

    assert text == (
        "Championship post is waiting on a few decks 🏆\n"
        "Please post your deck screenshot <@1>\n"
        "Use this button to register your deck colors <@1> <@2>\n"
        "\n"
        "Your deck shows on your seat at [limitedlevelups.com/pods/pod-7]"
        "(<https://limitedlevelups.com/pods/pod-7>) 🎨\n"
        "Please post your deck screenshot <@3>\n"
        "Use this button to register your deck colors <@3>"
    )


def test_deck_ping_pod_link_suppresses_embed_and_hides_scheme():
    text = build_deck_ping(([], []), (["3"], []), "https://limitedlevelups.com/pods/pod-7")
    assert "[limitedlevelups.com/pods/pod-7](<https://limitedlevelups.com/pods/pod-7>)" in text


def test_deck_ping_drops_championship_block_once_post_is_clear():
    text = build_deck_ping(([], []), (["3"], ["3"]), "https://limitedlevelups.com/pods/pod-7")
    assert "waiting" not in text
    assert text.startswith("Your deck shows on your seat")


def test_deck_ping_is_empty_when_nobody_owes_anything():
    assert build_deck_ping(([], []), ([], []), "https://limitedlevelups.com/pods/pod-7") == ""


def test_reported_result_uses_display_names_either_side():
    match = {
        "a_name": "marlo#1", "b_name": "bob#2",
        "a_display": "Marlo", "b_display": "Bob", "score": "2-1",
    }

    assert format_reported_result({**match, "winner_name": "marlo#1"}) == "Marlo wins 2-1 vs Bob"
    assert format_reported_result({**match, "winner_name": "bob#2"}) == "Bob wins 2-1 vs Marlo"


def _standings(*names: str) -> list:
    return [SimpleNamespace(player_name=n) for n in names]


def _deck(colors: str | None, screenshot: str | None) -> ParticipantDeckData:
    return ParticipantDeckData(colors=colors, screenshot_url=screenshot, screenshot_caption=None)


def _complete_decks(*names: str) -> dict:
    return {normalize_player_name(n): _deck("WU", "http://img/x.png") for n in names}
