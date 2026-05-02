from datetime import date

import pytest
import requests
from sqlalchemy import select

from bot.models import MagicSet, Player, PlayerSetScore, PlayerStats
from bot.services.refresh import (
    aggregate_by_format_and_expansion,
    recompute_player_set_score,
    refresh_active_players,
    refresh_one_player_for_current_set,
    refresh_player,
)


# ---------------------------------------------------------------------------
# aggregate_by_format_and_expansion
# ---------------------------------------------------------------------------


def test_aggregate_by_fmt_exp_empty():
    assert aggregate_by_format_and_expansion([], "ECL") == []


def test_aggregate_by_fmt_exp_buckets_per_pair():
    drafts = [
        {"format": "PremierDraft", "expansion": "ECL", "wins": 5, "losses": 3, "event_wins": 0},
        {"format": "PremierDraft", "expansion": "ECL", "wins": 7, "losses": 1, "event_wins": 7},
        {"format": "PremierDraft", "expansion": "Y26ECL", "wins": 4, "losses": 3, "event_wins": 0},
        {"format": "TradDraft", "expansion": "ECL", "wins": 4, "losses": 0, "event_wins": 4},
    ]
    rows = aggregate_by_format_and_expansion(drafts, "ECL")

    by_key = {(r["format"], r["expansion"]): r for r in rows}
    assert set(by_key.keys()) == {
        ("PremierDraft", "ECL"),
        ("PremierDraft", "Y26ECL"),
        ("TradDraft", "ECL"),
    }
    assert by_key[("PremierDraft", "ECL")] == {
        "format": "PremierDraft", "expansion": "ECL",
        "events": 2, "wins": 12, "losses": 4, "games_played": 16, "trophies": 1,
    }
    assert by_key[("PremierDraft", "Y26ECL")]["events"] == 1
    assert by_key[("PremierDraft", "Y26ECL")]["wins"] == 4
    assert by_key[("PremierDraft", "Y26ECL")]["games_played"] == 7
    assert by_key[("TradDraft", "ECL")]["trophies"] == 1


def test_aggregate_by_fmt_exp_substring_match():
    drafts = [
        {"format": "PremierDraft", "expansion": "Y26ECL", "wins": 7, "losses": 0, "event_wins": 7},
    ]
    rows = aggregate_by_format_and_expansion(drafts, "ECL")
    assert len(rows) == 1
    assert rows[0]["expansion"] == "Y26ECL"
    assert rows[0]["trophies"] == 1


def test_aggregate_by_fmt_exp_skips_unsupported_formats():
    drafts = [
        {"format": "MidWeekSealed", "expansion": "ECL", "wins": 7, "losses": 0, "event_wins": 7},
    ]
    assert aggregate_by_format_and_expansion(drafts, "ECL") == []


def test_aggregate_by_fmt_exp_skips_other_sets():
    drafts = [
        {"format": "PremierDraft", "expansion": "BLB", "wins": 7, "losses": 0, "event_wins": 7},
        {"format": "PremierDraft", "expansion": "DSK", "wins": 4, "losses": 1},
    ]
    assert aggregate_by_format_and_expansion(drafts, "ECL") == []


def test_aggregate_by_fmt_exp_trophy_via_event_wins():
    drafts = [
        {"format": "TradDraft", "expansion": "ECL", "wins": 4, "losses": 0, "event_wins": 4},
        {"format": "TradDraft", "expansion": "ECL", "wins": 2, "losses": 1, "event_wins": 0},
    ]
    rows = aggregate_by_format_and_expansion(drafts, "ECL")
    assert len(rows) == 1
    assert rows[0]["trophies"] == 1
    assert rows[0]["wins"] == 6


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class FakeClient:
    def __init__(self, drafts=None, raise_=None):
        self.drafts = drafts or []
        self.raise_ = raise_
        self.calls: list[tuple[str, object]] = []

    def fetch_drafts(self, token, start_date=None):
        self.calls.append((token, start_date))
        if self.raise_ is not None:
            raise self.raise_
        return list(self.drafts)


class ExplodingClient:
    def fetch_drafts(self, token, start_date=None):  # pragma: no cover - shouldn't be called
        raise AssertionError("client should not be called for skipped player")


def _make_404():
    resp = requests.Response()
    resp.status_code = 404
    return requests.HTTPError(response=resp)


def _make_500():
    resp = requests.Response()
    resp.status_code = 500
    return requests.HTTPError(response=resp)


def _seed_set(session, code="ECL"):
    s = MagicSet(code=code, name=code, start_date=date(2026, 1, 20))
    session.add(s)
    session.flush()
    return s


def _seed_player(session, name="P", token_suffix="a", active=True, token_invalid=False):
    token = (token_suffix * 32)[:32]
    p = Player(
        display_name=name,
        seventeenlands_token=token,
        seventeenlands_url=f"https://www.17lands.com/user_history/{token}",
        active=active,
        token_invalid=token_invalid,
    )
    session.add(p)
    session.flush()
    return p


# ---------------------------------------------------------------------------
# refresh_player
# ---------------------------------------------------------------------------


def test_refresh_player_inserts_rows(session):
    s = _seed_set(session)
    p = _seed_player(session)
    drafts = [
        {"format": "PremierDraft", "expansion": "ECL", "wins": 5, "losses": 3, "event_wins": 0},
        {"format": "TradDraft", "expansion": "ECL", "wins": 4, "losses": 0, "event_wins": 4},
    ]
    client = FakeClient(drafts=drafts)

    result = refresh_player(session, client, p, s)
    session.flush()

    assert result == {"status": "updated", "rows": 2}
    assert client.calls == [(p.seventeenlands_token, s.start_date)]
    rows = session.execute(
        select(PlayerStats).where(PlayerStats.player_id == p.id)
    ).scalars().all()
    assert len(rows) == 2
    by_fmt = {r.format: r for r in rows}
    assert by_fmt["PremierDraft"].wins == 5
    assert by_fmt["PremierDraft"].expansion == "ECL"
    assert by_fmt["PremierDraft"].last_fetched_at is not None
    assert by_fmt["TradDraft"].trophies == 1


def test_refresh_player_updates_existing_row(session):
    s = _seed_set(session)
    p = _seed_player(session)
    session.add(PlayerStats(
        player_id=p.id, set_id=s.id, format="PremierDraft", expansion="ECL",
        events=1, wins=2, losses=1, games_played=3, trophies=0,
    ))
    session.flush()

    client = FakeClient(drafts=[
        {"format": "PremierDraft", "expansion": "ECL", "wins": 9, "losses": 4, "event_wins": 7},
    ])
    refresh_player(session, client, p, s)
    session.flush()

    row = session.execute(
        select(PlayerStats).where(PlayerStats.player_id == p.id)
    ).scalar_one()
    assert row.wins == 9
    assert row.losses == 4
    assert row.games_played == 13
    assert row.trophies == 1
    assert row.last_fetched_at is not None


def test_refresh_player_multiple_expansions_coexist(session):
    s = _seed_set(session)
    p = _seed_player(session)
    client = FakeClient(drafts=[
        {"format": "PremierDraft", "expansion": "ECL", "wins": 5, "losses": 2, "event_wins": 0},
        {"format": "PremierDraft", "expansion": "Y26ECL", "wins": 7, "losses": 1, "event_wins": 7},
    ])

    refresh_player(session, client, p, s)
    session.flush()

    rows = session.execute(
        select(PlayerStats).where(
            PlayerStats.player_id == p.id, PlayerStats.format == "PremierDraft"
        )
    ).scalars().all()
    by_exp = {r.expansion: r for r in rows}
    assert set(by_exp) == {"ECL", "Y26ECL"}
    assert by_exp["ECL"].wins == 5
    assert by_exp["Y26ECL"].trophies == 1


def test_refresh_player_404_invalidates_token(session):
    s = _seed_set(session)
    p = _seed_player(session)
    client = FakeClient(raise_=_make_404())

    result = refresh_player(session, client, p, s)
    session.flush()

    assert result == {"status": "invalidated"}
    assert p.token_invalid is True
    rows = session.execute(
        select(PlayerStats).where(PlayerStats.player_id == p.id)
    ).scalars().all()
    assert rows == []


def test_refresh_player_malformed_response_does_not_invalidate(session):
    """Signup verifies tokens, so a malformed 200 is a 17lands bug — don't blame the user."""
    s = _seed_set(session)
    p = _seed_player(session)
    client = FakeClient(raise_=ValueError("bad json"))

    result = refresh_player(session, client, p, s)

    assert result["status"] == "error"
    assert p.token_invalid is False


def test_refresh_player_5xx_does_not_invalidate(session):
    s = _seed_set(session)
    p = _seed_player(session)
    client = FakeClient(raise_=_make_500())

    result = refresh_player(session, client, p, s)

    assert result["status"] == "error"
    assert p.token_invalid is False


def test_refresh_player_network_error_does_not_invalidate(session):
    s = _seed_set(session)
    p = _seed_player(session)
    client = FakeClient(raise_=requests.ConnectTimeout("timeout"))

    result = refresh_player(session, client, p, s)

    assert result["status"] == "error"
    assert p.token_invalid is False


# ---------------------------------------------------------------------------
# refresh_active_players
# ---------------------------------------------------------------------------


def test_refresh_active_players_skips_token_invalid_and_inactive(session):
    s = _seed_set(session)
    active_ok = _seed_player(session, name="ok", token_suffix="a")
    _seed_player(session, name="inactive", token_suffix="b", active=False)
    _seed_player(session, name="invalid", token_suffix="c", token_invalid=True)
    session.flush()

    client = FakeClient(drafts=[
        {"format": "PremierDraft", "expansion": "ECL", "wins": 7, "losses": 0, "event_wins": 7},
    ])

    summary = refresh_active_players(session, client, s)

    assert summary["updated"] == 1
    assert summary["invalidated"] == 0
    assert summary["errors"] == 0
    # Only the active+valid player got fetched
    assert [c[0] for c in client.calls] == [active_ok.seventeenlands_token]


def test_refresh_active_players_does_not_call_client_when_all_skipped(session):
    s = _seed_set(session)
    _seed_player(session, name="inactive", token_suffix="a", active=False)
    _seed_player(session, name="invalid", token_suffix="b", token_invalid=True)
    session.flush()

    summary = refresh_active_players(session, ExplodingClient(), s)
    assert summary["updated"] == 0
    assert summary["invalidated"] == 0
    assert summary["errors"] == 0


def test_refresh_active_players_summary_counts(session):
    s = _seed_set(session)
    p_ok = _seed_player(session, name="ok", token_suffix="a")
    p_404 = _seed_player(session, name="bad", token_suffix="b")
    p_5xx = _seed_player(session, name="flaky", token_suffix="c")
    session.flush()

    error_404 = _make_404()
    error_500 = _make_500()

    class RoutingClient:
        def __init__(self):
            self.calls = []

        def fetch_drafts(self, token, start_date=None):
            self.calls.append(token)
            if token == p_404.seventeenlands_token:
                raise error_404
            if token == p_5xx.seventeenlands_token:
                raise error_500
            return [{"format": "PremierDraft", "expansion": "ECL", "wins": 3, "losses": 2}]

    summary = refresh_active_players(session, RoutingClient(), s)

    assert summary["updated"] == 1
    assert summary["invalidated"] == 1
    assert summary["errors"] == 1
    assert summary["invalidated_players"] == [p_404.id]
    session.refresh(p_404)
    session.refresh(p_5xx)
    assert p_404.token_invalid is True
    assert p_5xx.token_invalid is False


# ---------------------------------------------------------------------------
# refresh_one_player_for_current_set
# ---------------------------------------------------------------------------


def test_refresh_one_player_no_current_set(session):
    p = _seed_player(session)
    session.commit()
    result = refresh_one_player_for_current_set(session, FakeClient(), p.id)
    assert result == {"status": "no_current_set"}


def test_refresh_one_player_unknown_player_id(session):
    # Seed SOS to match settings.current_set_code default
    _seed_set(session, code="SOS")
    result = refresh_one_player_for_current_set(session, FakeClient(), "nonexistent-id")
    assert result == {"status": "no_player"}


def test_refresh_one_player_for_current_set_writes_rows(session):
    s = _seed_set(session, code="SOS")
    p = _seed_player(session)
    session.commit()
    client = FakeClient(drafts=[
        {"format": "PremierDraft", "expansion": "SOS", "wins": 5, "losses": 2, "event_wins": 7},
    ])

    result = refresh_one_player_for_current_set(session, client, p.id)
    session.commit()

    assert result["status"] == "updated"
    rows = session.execute(
        select(PlayerStats).where(PlayerStats.player_id == p.id)
    ).scalars().all()
    assert len(rows) == 1
