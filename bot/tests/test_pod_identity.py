"""Tests for pod-draft player identity matching and arena-name format validation."""
from __future__ import annotations

import re

from bot.models import Player
from bot.services.pod_drafts import (
    normalize_player_name,
    _player_for_name,
    classify_lobby_names,
)

_ARENA_INPUT_RE = re.compile(r"^.+#\d+$")


def _seed_player(
    session,
    *,
    discord_id,
    username,
    display_name,
    arena_name=None,
    arena_aliases=None,
    active=True,
):
    if arena_aliases is None:
        arena_aliases = [normalize_player_name(arena_name)] if arena_name else []
    p = Player(
        slug=f"{username}-{discord_id}",
        discord_id=discord_id,
        discord_username=username,
        display_name=display_name,
        arena_name=arena_name,
        arena_aliases=arena_aliases,
        active=active,
    )
    session.add(p)
    session.flush()
    return p


# --- normalize_player_name ---

def test_normalize_strips_arena_suffix():
    assert normalize_player_name("Noya#12345") == "noya"


def test_normalize_lowercases_bare_name():
    assert normalize_player_name("MartinTheGreat") == "martinthegreat"


def test_normalize_hash_with_no_digits_is_not_stripped():
    # `#` alone doesn't match `#\d+$`, so the hash stays
    assert normalize_player_name("Name#") == "name#"


def test_normalize_strips_only_trailing_suffix():
    assert normalize_player_name("Na#12me#99") == "na#12me"


def test_normalize_empty_string():
    assert normalize_player_name("") == ""


# --- _player_for_name priority ---

def test_exact_arena_name_wins_over_display_name(session):
    _seed_player(session, discord_id="1", username="alice", display_name="Alice", arena_name="MagicAlice#9999")
    _seed_player(session, discord_id="2", username="magicalice", display_name="MagicAlice")

    # "MagicAlice#9999" matches player 1's arena_name exactly (lower), not player 2's display_name
    found = _player_for_name(session, "MagicAlice#9999")
    assert found is not None
    assert found.discord_id == "1"


def test_arena_name_match_is_case_insensitive(session):
    _seed_player(session, discord_id="3", username="bob", display_name="Bob", arena_name="Bob#5678")

    assert _player_for_name(session, "bob#5678") is not None
    assert _player_for_name(session, "BOB#5678") is not None


def test_falls_back_to_normalized_display_name(session):
    _seed_player(session, discord_id="4", username="charlie", display_name="Charlie")

    found = _player_for_name(session, "Charlie#0001")
    assert found is not None
    assert found.discord_id == "4"


def test_falls_back_to_normalized_discord_username(session):
    # display_name doesn't match but discord_username does after normalization
    _seed_player(session, discord_id="5", username="nightowl", display_name="NightOwl2025")

    found = _player_for_name(session, "nightowl#777")
    assert found is not None
    assert found.discord_id == "5"


def test_returns_none_when_no_match(session):
    _seed_player(session, discord_id="6", username="dave", display_name="Dave")
    assert _player_for_name(session, "ghost#1234") is None


def test_ignores_inactive_players(session):
    _seed_player(session, discord_id="7", username="retired", display_name="Retired", active=False)
    assert _player_for_name(session, "retired") is None


def test_display_name_wins_over_discord_username_when_both_match(session):
    # Two players: one whose display_name normalizes to "ace", one whose username is "ace"
    _seed_player(session, discord_id="8", username="notace", display_name="Ace")
    _seed_player(session, discord_id="9", username="ace", display_name="Somebody Else")

    found = _player_for_name(session, "Ace#1111")
    # display_name leg fires before discord_username leg; p_display should win
    assert found is not None
    assert found.discord_id == "8"


# --- classify_lobby_names ---

def test_classify_returns_display_name_for_recognized_names(session):
    _seed_player(session, discord_id="10", username="known", display_name="Known")

    result = dict(classify_lobby_names(session, ["Known", "Unknown#9999"]))
    assert result["Known"] == "Known"
    assert result["Unknown#9999"] is None


def test_classify_resolves_name_with_arena_suffix_via_display_name(session):
    _seed_player(session, discord_id="11", username="noya", display_name="Noya")

    result = dict(classify_lobby_names(session, ["Noya#12345"]))
    assert result["Noya#12345"] == "Noya"


def test_classify_resolves_via_stored_arena_name(session):
    _seed_player(
        session, discord_id="12", username="martin", display_name="Noya",
        arena_name="MartinTheGreat#5432",
    )

    result = dict(classify_lobby_names(session, ["MartinTheGreat#5432", "Noya#0001"]))
    assert result["MartinTheGreat#5432"] == "Noya"
    assert result["Noya#0001"] == "Noya"


def test_classify_empty_list(session):
    assert classify_lobby_names(session, []) == []


def test_classify_preserves_order(session):
    _seed_player(session, discord_id="13", username="one", display_name="One")
    _seed_player(session, discord_id="14", username="three", display_name="Three")

    names = ["One", "Two#0", "Three", "Four#0"]
    result = classify_lobby_names(session, names)
    assert [n for n, _ in result] == names
    assert [dn for _, dn in result] == ["One", None, "Three", None]


# --- /link-arena input format (regex) ---

def test_valid_arena_handle_accepted():
    assert _ARENA_INPUT_RE.match("Noya#12345")
    assert _ARENA_INPUT_RE.match("Mr Fancy#1")
    assert _ARENA_INPUT_RE.match("a#0")


def test_bare_name_without_hash_rejected():
    assert not _ARENA_INPUT_RE.match("NoHashAtAll")


def test_hash_without_digits_rejected():
    assert not _ARENA_INPUT_RE.match("Name#")


def test_hash_with_non_digit_suffix_rejected():
    assert not _ARENA_INPUT_RE.match("Name#abc")


def test_empty_string_rejected():
    assert not _ARENA_INPUT_RE.match("")


# --- multi-account alias matching ---

def test_alias_exact_match_resolves_to_owner(session):
    _seed_player(
        session, discord_id="10", username="flutterdev", display_name="flutterdev",
        arena_name="fullerene60#49190",
        arena_aliases=["fullerene60", "edvor"],
    )
    assert _player_for_name(session, "fullerene60#49190").discord_id == "10"
    assert _player_for_name(session, "edvor#11111").discord_id == "10"


def test_alias_match_independent_of_primary_arena_name(session):
    _seed_player(
        session, discord_id="11", username="dev2", display_name="Dev Two",
        arena_name="primaryhandle#10000",
        arena_aliases=["primaryhandle", "secondhandle"],
    )
    assert _player_for_name(session, "secondhandle#22222").discord_id == "11"


def test_longest_alias_prefix_wins(session):
    _seed_player(
        session, discord_id="12", username="a", display_name="A",
        arena_aliases=["drag"],
    )
    _seed_player(
        session, discord_id="13", username="b", display_name="B",
        arena_aliases=["dragonslayer"],
    )
    assert _player_for_name(session, "dragonslayer99#1234").discord_id == "13"
    assert _player_for_name(session, "dragfoo#9999").discord_id == "12"


def test_alias_no_match_falls_back_to_display_name(session):
    _seed_player(
        session, discord_id="14", username="zoinks", display_name="zoinks",
        arena_name=None,
    )
    assert _player_for_name(session, "zoinks#42").discord_id == "14"


# --- token-in-display-name matching (tier 4) ---

def test_token_match_in_display_name(session):
    _seed_player(session, discord_id="20", username="zorn", display_name="Zorn (Kael)")
    assert _player_for_name(session, "Kael#12345").discord_id == "20"


def test_token_match_does_not_fire_for_short_norm(session):
    _seed_player(session, discord_id="21", username="xy", display_name="XY (ab)")
    assert _player_for_name(session, "ab#1") is None


def test_exact_display_name_beats_token_match(session):
    exact = _seed_player(session, discord_id="22", username="u22", display_name="Kael")
    _seed_player(session, discord_id="23", username="u23", display_name="Zorn (Kael)")
    assert _player_for_name(session, "Kael#12345").discord_id == exact.discord_id
