import pytest

from bot.media_sets import EVERGREEN, display_name, resolve_set


@pytest.mark.parametrize(
    "playlists, title, expected_code",
    [
        (["Secrets of Strixhaven"], "Whatever", "SOS"),
        (["Bloomburrow Set Review"], "Whatever", "BLB"),
        (["Outlaws Of Thunder Junction Draft Videos"], "Whatever", "OTJ"),
        (["Powered cube"], "Whatever", "CUBE"),
        (["Duskmorne Videos"], "Whatever", "DSK"),
        (["Spiderman/Through The Omenpaths 1"], "Whatever", "SPM"),
        (["Kamigawa: Neon Dynasty"], "Whatever", "NEO"),
    ],
)
def test_resolve_from_playlist_strips_role_suffix_and_matches_aliases(playlists, title, expected_code):
    result = resolve_set(playlists, title)

    assert result.code == expected_code


@pytest.mark.parametrize(
    "title, expected_code",
    [
        ("How to Draft Kithkin in Lorwyn! #mtg #draft", "ECL"),
        ("What's the Pick in Streets of New Capenna Draft?", "SNC"),
        ("My Top 5 Uncommons in Avatar Draft!", "TLA"),
        ("The New Best Color in Final Fantasy", "FIN"),
    ],
)
def test_resolve_from_title_when_no_playlist_match(title, expected_code):
    result = resolve_set([], title)

    assert result.code == expected_code


def test_resolve_defaults_to_evergreen_for_set_agnostic_content():
    result = resolve_set(["Limited Level Ups Evergreen Episodes"], "The Most Important Rules of Limited Gameplay")

    assert result == EVERGREEN


def test_resolve_prefers_title_over_cross_listed_playlists():
    result = resolve_set(
        ["Lorwyn Eclipsed", "TMNT Set Review", "Teenage Mutant Ninja Turtles"],
        "Teenage Mutant Ninja Turtles Set Primer",
    )

    assert result.code == "TMT"


def test_resolve_uses_playlist_when_title_names_no_set():
    result = resolve_set(["Modern Horizons 3 Set Review"], "Best Commons and Uncommons, Ranked")

    assert result.code == "MH3"


def test_display_name_falls_back_to_evergreen_for_missing_code():
    assert display_name("SOS") == "Secrets of Strixhaven"
    assert display_name(None) == "Evergreen"
    assert display_name("ZZZ") == "ZZZ"
