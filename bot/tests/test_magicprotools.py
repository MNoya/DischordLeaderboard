"""Tests for the MagicProTools format converter. API submit is not exercised (no live HTTP)."""
from __future__ import annotations

from bot.services.magicprotools import convert_to_magicprotools_format


def _sample_log() -> dict:
    return {
        "sessionID": "LLU-TEST",
        "time": 1736035200000,  # 2025-01-05 00:00 UTC
        "setRestriction": ["SOS"],
        "carddata": {
            "c1": {"name": "Lightning Bolt", "set": "SOS"},
            "c2": {"name": "Counterspell", "set": "SOS"},
            "c3": {"name": "Doom Blade", "set": "SOS"},
        },
        "users": {
            "u1": {
                "userName": "Noya",
                "picks": [
                    {"packNum": 0, "pickNum": 0, "pick": [0], "booster": ["c1", "c2", "c3"]},
                    {"packNum": 0, "pickNum": 1, "pick": [1], "booster": ["c2", "c3"]},
                    {"packNum": 1, "pickNum": 0, "pick": [2], "booster": ["c1", "c2", "c3"]},
                ],
            },
            "u2": {"userName": "Oophies", "picks": []},
        },
    }


def test_converter_marks_self_seat() -> None:
    out = convert_to_magicprotools_format(_sample_log(), "u1")
    lines = out.splitlines()
    # Self seat in player list is prefixed `--> `
    assert "--> Noya" in lines
    assert "    Oophies" in lines


def test_converter_marks_picked_card_per_pack() -> None:
    out = convert_to_magicprotools_format(_sample_log(), "u1")
    # First pack first pick: Lightning Bolt is at index 0 of [Bolt, Counter, Doom]
    assert "Pack 1 pick 1:" in out
    assert "--> Lightning Bolt" in out
    # Second pick: Doom Blade is at index 1 of [Counter, Doom]
    assert "Pack 1 pick 2:" in out
    assert "--> Doom Blade" in out


def test_converter_uses_set_header_when_set_restriction_matches() -> None:
    out = convert_to_magicprotools_format(_sample_log(), "u1")
    assert "------ SOS ------" in out


def test_converter_falls_back_to_cube_header_when_carddata_diverges() -> None:
    log = _sample_log()
    # Force carddata sets to diverge from setRestriction so the heuristic fails
    for card in log["carddata"].values():
        card["set"] = "OTHER"
    out = convert_to_magicprotools_format(log, "u1")
    assert "------ Cube ------" in out


def test_converter_handles_double_faced_cards() -> None:
    log = _sample_log()
    log["carddata"]["c1"]["back"] = {"name": "Lightning Bolt Reborn"}
    out = convert_to_magicprotools_format(log, "u1")
    assert "Lightning Bolt // Lightning Bolt Reborn" in out


def test_converter_event_header_includes_session_id() -> None:
    out = convert_to_magicprotools_format(_sample_log(), "u1")
    assert "Event #: LLU-TEST_1736035200000" in out
