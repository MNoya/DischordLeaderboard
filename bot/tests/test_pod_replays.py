"""Tests for the score-pattern + time-window attribution algorithm. No live API/DB hits."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bot.models import PodDraftMatch
from bot.services.pod_replays import attribute_games_to_rounds


_POD = "DirectGameTournamentLimited"


def test_attributes_each_match_when_data_is_clean() -> None:
    base = datetime(2026, 5, 14, 0, 0, tzinfo=timezone.utc)
    matches = [
        _match(1, "Noya", "Niamh", "Niamh", "2-1", reported_at=base + timedelta(minutes=35)),
        _match(2, "Noya", "Bacchus", "Noya", "2-1", reported_at=base + timedelta(minutes=75)),
        _match(3, "Noya", "Wave", "Wave", "2-1", reported_at=base + timedelta(minutes=110)),
    ]
    games = [
        _game(base + timedelta(minutes=10), won=True, turns=9, gid="r1g1"),
        _game(base + timedelta(minutes=20), won=False, turns=10, gid="r1g2"),
        _game(base + timedelta(minutes=30), won=False, turns=12, gid="r1g3"),
        _game(base + timedelta(minutes=45), won=False, turns=9, gid="r2g1"),
        _game(base + timedelta(minutes=55), won=True, turns=8, gid="r2g2"),
        _game(base + timedelta(minutes=70), won=True, turns=13, gid="r2g3"),
        _game(base + timedelta(minutes=85), won=True, turns=13, gid="r3g1"),
        _game(base + timedelta(minutes=90), won=False, turns=4, gid="r3g2"),
        _game(base + timedelta(minutes=100), won=False, turns=7, gid="r3g3"),
    ]
    out = attribute_games_to_rounds(games, matches, "Noya")
    assert out == {
        "r1g1": 1, "r1g2": 1, "r1g3": 1,
        "r2g1": 2, "r2g2": 2, "r2g3": 2,
        "r3g1": 3, "r3g2": 3, "r3g3": 3,
    }


def test_handles_2_0_match_with_two_games() -> None:
    base = datetime(2026, 5, 14, 0, 0, tzinfo=timezone.utc)
    matches = [_match(1, "Noya", "X", "Noya", "2-0", reported_at=base + timedelta(minutes=25))]
    games = [
        _game(base + timedelta(minutes=10), won=True, turns=9, gid="g1"),
        _game(base + timedelta(minutes=20), won=True, turns=8, gid="g2"),
    ]
    out = attribute_games_to_rounds(games, matches, "Noya")
    assert out == {"g1": 1, "g2": 1}


def test_attributes_partial_round_when_a_game_is_missing() -> None:
    """R1 has only 2 of 3 expected games (G3 dropped by 17lands). The window still bounds them to
    R1, so both attribute; R2's clean 2-0 data attributes as usual."""
    base = datetime(2026, 5, 14, 0, 0, tzinfo=timezone.utc)
    matches = [
        _match(1, "Noya", "Niamh", "Noya", "2-1", reported_at=base + timedelta(minutes=35)),
        _match(2, "Noya", "Bacchus", "Noya", "2-0", reported_at=base + timedelta(minutes=70)),
    ]
    games = [
        _game(base + timedelta(minutes=10), won=True, turns=9, gid="r1g1"),
        _game(base + timedelta(minutes=20), won=False, turns=10, gid="r1g2"),
        # R1 G3 missing (would be a W)
        _game(base + timedelta(minutes=50), won=True, turns=11, gid="r2g1"),
        _game(base + timedelta(minutes=60), won=True, turns=8, gid="r2g2"),
    ]
    out = attribute_games_to_rounds(games, matches, "Noya")
    assert out == {"r1g1": 1, "r1g2": 1, "r2g1": 2, "r2g2": 2}


def test_late_report_files_overflow_games_under_the_earlier_round() -> None:
    """R1 was reported only after R2's first game, so its window swallows that game — the accepted
    best-effort trade: a game filed under the prior round beats dropping the window entirely."""
    base = datetime(2026, 5, 14, 0, 0, tzinfo=timezone.utc)
    matches = [
        _match(1, "Noya", "Niamh", "Noya", "2-1", reported_at=base + timedelta(minutes=50)),
        _match(2, "Noya", "Bacchus", "Noya", "2-0", reported_at=base + timedelta(minutes=80)),
    ]
    games = [
        _game(base + timedelta(minutes=10), won=True, turns=9, gid="r1g1"),
        _game(base + timedelta(minutes=20), won=False, turns=10, gid="r1g2"),
        _game(base + timedelta(minutes=30), won=True, turns=12, gid="r1g3"),
        _game(base + timedelta(minutes=45), won=True, turns=8, gid="r2g1"),
        _game(base + timedelta(minutes=70), won=True, turns=11, gid="r2g2"),
    ]
    out = attribute_games_to_rounds(games, matches, "Noya")
    assert out == {"r1g1": 1, "r1g2": 1, "r1g3": 1, "r2g1": 1, "r2g2": 2}


def test_attributes_regardless_of_reported_score() -> None:
    """Two observed wins inside a window reported as a 1-2 loss still attribute — players misreport
    scores, the window is what counts."""
    base = datetime(2026, 5, 14, 0, 0, tzinfo=timezone.utc)
    matches = [_match(1, "Noya", "X", "X", "2-1", reported_at=base + timedelta(minutes=35))]
    games = [
        _game(base + timedelta(minutes=10), won=True, turns=9, gid="g1"),
        _game(base + timedelta(minutes=20), won=True, turns=10, gid="g2"),
    ]
    out = attribute_games_to_rounds(games, matches, "Noya")
    assert out == {"g1": 1, "g2": 1}


def test_skipped_match_forms_no_window() -> None:
    """A 'No Match Played' result (0-0) is invisible to attribution: games around it flow into the
    next real match's window."""
    base = datetime(2026, 5, 14, 0, 0, tzinfo=timezone.utc)
    matches = [
        _match(1, "Noya", "Niamh", "(skipped)", "0-0", reported_at=base + timedelta(minutes=15)),
        _match(2, "Noya", "Bacchus", "Noya", "2-0", reported_at=base + timedelta(minutes=40)),
    ]
    games = [
        _game(base + timedelta(minutes=10), won=True, turns=9, gid="g1"),
        _game(base + timedelta(minutes=30), won=True, turns=8, gid="g2"),
    ]
    out = attribute_games_to_rounds(games, matches, "Noya")
    assert out == {"g1": 2, "g2": 2}


def test_filters_out_misload_restarts() -> None:
    base = datetime(2026, 5, 14, 0, 0, tzinfo=timezone.utc)
    matches = [_match(1, "Noya", "X", "Noya", "2-0", reported_at=base + timedelta(minutes=25))]
    games = [
        _game(base + timedelta(minutes=5), won=False, turns=2, gid="misload"),  # restart, dropped
        _game(base + timedelta(minutes=10), won=True, turns=9, gid="real1"),
        _game(base + timedelta(minutes=20), won=True, turns=8, gid="real2"),
    ]
    out = attribute_games_to_rounds(games, matches, "Noya")
    assert "misload" not in out
    assert out == {"real1": 1, "real2": 1}


def test_skips_non_pod_event_names() -> None:
    base = datetime(2026, 5, 14, 0, 0, tzinfo=timezone.utc)
    matches = [_match(1, "Noya", "X", "Noya", "2-0", reported_at=base + timedelta(minutes=25))]
    games = [
        _game(base + timedelta(minutes=5), won=True, turns=9, gid="premier", event_name="PremierDraft"),
        _game(base + timedelta(minutes=10), won=True, turns=9, gid="real1"),
        _game(base + timedelta(minutes=20), won=True, turns=8, gid="real2"),
    ]
    out = attribute_games_to_rounds(games, matches, "Noya")
    assert out == {"real1": 1, "real2": 1}


def test_player_perspective_when_seat_is_loser() -> None:
    base = datetime(2026, 5, 14, 0, 0, tzinfo=timezone.utc)
    matches = [_match(1, "Noya", "X", "X", "2-1", reported_at=base + timedelta(minutes=35))]
    games = [
        _game(base + timedelta(minutes=10), won=True, turns=9, gid="g1"),
        _game(base + timedelta(minutes=20), won=False, turns=10, gid="g2"),
        _game(base + timedelta(minutes=30), won=False, turns=12, gid="g3"),
    ]
    out = attribute_games_to_rounds(games, matches, "Noya")
    assert out == {"g1": 1, "g2": 1, "g3": 1}


def test_real_pod3_noya_data_attributes_r2_partially() -> None:
    """Empirical Pod #3 data for Noya: 8 games captured by 17lands, but R2's third game is
    missing. R1 (W L L = 1-2 loss to Niamh) and R3 (W L L = 1-2 loss to Wave) attribute cleanly;
    R2's two observed games (L W within a 2-1 win) attribute partially."""
    def t(hhmm: str) -> datetime:
        h, m = hhmm.split(":")
        return datetime(2026, 5, 14, int(h), int(m), tzinfo=timezone.utc)

    matches = [
        _match(1, "Noya", "Niamh", "Niamh", "2-1", reported_at=t("01:05")),  # right after game 2 at 01:03
        _match(2, "Noya", "Bacchus", "Noya", "2-1", reported_at=t("01:30")),  # right after the missing G3
        _match(3, "Noya", "Wave", "Wave", "2-1", reported_at=t("02:05")),    # right after game 7 at 02:01
    ]
    games = [
        _game(t("00:41"), won=True, turns=9, gid="g0"),
        _game(t("00:50"), won=False, turns=10, gid="g1"),
        _game(t("01:03"), won=False, turns=12, gid="g2"),
        _game(t("01:19"), won=False, turns=9, gid="g3"),
        _game(t("01:23"), won=True, turns=8, gid="g4"),
        # R2 G3 missing
        _game(t("01:52"), won=True, turns=13, gid="g5"),
        _game(t("01:54"), won=False, turns=4, gid="g6"),
        _game(t("02:01"), won=False, turns=7, gid="g7"),
    ]
    out = attribute_games_to_rounds(games, matches, "Noya")
    assert out == {"g0": 1, "g1": 1, "g2": 1, "g3": 2, "g4": 2, "g5": 3, "g6": 3, "g7": 3}


def _match(round_num: int, player_a: str, player_b: str, winner: str, score: str,
           reported_at: datetime) -> PodDraftMatch:
    return PodDraftMatch(
        id=f"m{round_num}",
        event_id="evt-1",
        round=round_num,
        pairing_index=0,
        player_a_name=player_a,
        player_b_name=player_b,
        winner_name=winner,
        score=score,
        reported_at=reported_at,
    )


def _game(ts: datetime, won: bool, turns: int, gid: str, event_name: str = _POD) -> dict:
    return {
        "event_name": event_name,
        "game_time": ts.strftime("%Y-%m-%d %H:%M"),
        "link": f"/user/game_replay/20260514/{gid}/0",
        "won": won,
        "turns": turns,
        "on_play": True,
        "account_name": "Noya",
    }
