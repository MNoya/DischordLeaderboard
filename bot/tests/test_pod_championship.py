from types import SimpleNamespace

from bot.services.pod_tournament import (
    ANNOUNCEMENT_TOP_N,
    ParticipantDeckData,
    deck_complete,
    incomplete_top_decks,
    normalize_player_name,
    build_deck_reminder_text,
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


def test_deck_reminder_text_carries_mentions():
    text = build_deck_reminder_text("<@1> <@2>")
    assert "<@1>" in text and "<@2>" in text


def _standings(*names: str) -> list:
    return [SimpleNamespace(player_name=n) for n in names]


def _deck(colors: str | None, screenshot: str | None) -> ParticipantDeckData:
    return ParticipantDeckData(colors=colors, screenshot_url=screenshot, screenshot_caption=None, draft_log_url=None)


def _complete_decks(*names: str) -> dict:
    return {normalize_player_name(n): _deck("WU", "http://img/x.png") for n in names}
