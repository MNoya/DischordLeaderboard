from datetime import date

import pytest
import requests
from sqlalchemy import select

from bot.models import DraftEvent, MagicSet, Player, PlayerSetScore, PlayerStats
from bot.services.refresh import (
    aggregate_by_set_format_expansion,
    recompute_player_set_score,
    refresh_active_players,
    refresh_active_players_all_sets,
    refresh_one_player_for_all_sets,
    refresh_player,
    upsert_draft_events,
)
from bot.sets import ACTIVE_SET_CODE


class _FakeSet:
    __slots__ = ("id", "code")

    def __init__(self, set_id: str, code: str) -> None:
        self.id = set_id
        self.code = code


def test_aggregate_empty():
    assert aggregate_by_set_format_expansion([], [_FakeSet("s1", "ECL")]) == []


def test_aggregate_buckets_per_set_format_expansion():
    drafts = [
        {"format": "PremierDraft", "expansion": "ECL", "wins": 5, "losses": 3, "event_wins": 0},
        {"format": "PremierDraft", "expansion": "ECL", "wins": 7, "losses": 1, "event_wins": 7},
        {"format": "PremierDraft", "expansion": "Y26ECL", "wins": 4, "losses": 3, "event_wins": 0},
        {"format": "TradDraft", "expansion": "ECL", "wins": 4, "losses": 0, "event_wins": 4},
    ]
    rows = aggregate_by_set_format_expansion(drafts, [_FakeSet("s1", "ECL")])

    by_key = {(r["format"], r["expansion"]): r for r in rows}
    assert set(by_key.keys()) == {("PremierDraft", "ECL"), ("PremierDraft", "Y26ECL"), ("TradDraft", "ECL")}
    assert by_key[("PremierDraft", "ECL")]["set_id"] == "s1"
    assert by_key[("PremierDraft", "ECL")]["set_code"] == "ECL"
    assert by_key[("PremierDraft", "ECL")]["events"] == 2
    assert by_key[("PremierDraft", "ECL")]["wins"] == 12
    assert by_key[("PremierDraft", "ECL")]["games_played"] == 16
    assert by_key[("PremierDraft", "ECL")]["trophies"] == 1
    assert by_key[("PremierDraft", "Y26ECL")]["events"] == 1
    assert by_key[("TradDraft", "ECL")]["trophies"] == 1


def test_aggregate_substring_match():
    rows = aggregate_by_set_format_expansion(
        [{"format": "PremierDraft", "expansion": "Y26ECL", "wins": 7, "losses": 0, "event_wins": 7}],
        [_FakeSet("s1", "ECL")],
    )
    assert len(rows) == 1
    assert rows[0]["expansion"] == "Y26ECL"
    assert rows[0]["set_code"] == "ECL"
    assert rows[0]["trophies"] == 1


def test_aggregate_skips_unsupported_formats_and_tallies_unknown():
    """Unknown formats are dropped and counted in the optional ``unknown_formats`` dict."""
    unknown: dict[str, int] = {}
    rows = aggregate_by_set_format_expansion(
        [{"format": "MidWeekSealed", "expansion": "ECL", "wins": 7, "losses": 0, "event_wins": 7}],
        [_FakeSet("s1", "ECL")],
        unknown_formats=unknown,
    )
    assert rows == []
    assert unknown == {"MidWeekSealed": 1}


def test_aggregate_drops_unknown_expansions(caplog):
    drafts = [
        {"format": "PremierDraft", "expansion": "BLB", "wins": 7, "losses": 0, "event_wins": 7},
        {"format": "PremierDraft", "expansion": "DSK", "wins": 4, "losses": 1},
    ]
    with caplog.at_level("INFO", logger="bot.services.refresh"):
        rows = aggregate_by_set_format_expansion(drafts, [_FakeSet("s1", "ECL")])
    assert rows == []
    assert any("BLB" in r.message for r in caplog.records)
    assert any("DSK" in r.message for r in caplog.records)


def test_aggregate_routes_across_multiple_sets():
    drafts = [
        {"format": "PremierDraft", "expansion": "SOS", "wins": 7, "losses": 0, "event_wins": 7},
        {"format": "PremierDraft", "expansion": "ECL", "wins": 5, "losses": 3},
        {"format": "PremierDraft", "expansion": "Y26ECL", "wins": 4, "losses": 0, "event_wins": 4},
    ]
    sets = [_FakeSet("s-sos", "SOS"), _FakeSet("s-ecl", "ECL")]
    rows = aggregate_by_set_format_expansion(drafts, sets)
    by_set = {r["set_code"]: r for r in rows if r["expansion"] != "Y26ECL"}
    assert by_set["SOS"]["wins"] == 7
    assert by_set["ECL"]["wins"] == 5
    y26 = next(r for r in rows if r["expansion"] == "Y26ECL")
    assert y26["set_code"] == "ECL"
    assert y26["trophies"] == 1


def test_aggregate_trophy_via_event_wins():
    rows = aggregate_by_set_format_expansion(
        [
            {"format": "TradDraft", "expansion": "ECL", "wins": 4, "losses": 0, "event_wins": 4},
            {"format": "TradDraft", "expansion": "ECL", "wins": 2, "losses": 1, "event_wins": 0},
        ],
        [_FakeSet("s1", "ECL")],
    )
    assert len(rows) == 1
    assert rows[0]["trophies"] == 1
    assert rows[0]["wins"] == 6


class FakeClient:
    def __init__(self, drafts=None, raise_=None):
        self.drafts = drafts or []
        self.raise_ = raise_
        self.calls: list[tuple[str, object, object]] = []

    def fetch_drafts(self, token, start_date=None, end_date=None):
        self.calls.append((token, start_date, end_date))
        if self.raise_ is not None:
            raise self.raise_
        return list(self.drafts)


class ExplodingClient:
    def fetch_drafts(self, token, start_date=None, end_date=None):  # pragma: no cover - shouldn't be called
        raise AssertionError("client should not be called for skipped player")


def _make_404():
    resp = requests.Response()
    resp.status_code = 404
    return requests.HTTPError(response=resp)


def _make_500():
    resp = requests.Response()
    resp.status_code = 500
    return requests.HTTPError(response=resp)


def _seed_set(session, code="ECL", start_date=date(2026, 1, 20)):
    s = MagicSet(code=code, name=code, start_date=start_date)
    session.add(s)
    session.flush()
    return s


def _seed_active_set(session):
    return _seed_set(session, code=ACTIVE_SET_CODE, start_date=date(2026, 4, 21))


def _seed_player(session, name="P", token_suffix="a", active=True, token_invalid=False):
    token = (token_suffix * 32)[:32]
    p = Player(
        slug=f"{name.lower()}-{token_suffix}",
        discord_id=f"refresh-{name.lower()}-{token_suffix}",
        display_name=name,
        seventeenlands_token=token,
        active=active,
        token_invalid=token_invalid,
    )
    session.add(p)
    session.flush()
    return p


def test_refresh_player_inserts_rows(session):
    s = _seed_set(session)
    p = _seed_player(session)
    drafts = [
        {"format": "PremierDraft", "expansion": "ECL", "wins": 5, "losses": 3, "event_wins": 0},
        {"format": "TradDraft", "expansion": "ECL", "wins": 4, "losses": 0, "event_wins": 4},
    ]
    client = FakeClient(drafts=drafts)

    result = refresh_player(session, client, p)
    session.flush()

    assert result == {"status": "updated", "rows": 2, "unknown_formats": {}}
    assert client.calls == [(p.seventeenlands_token, None, None)]
    rows = session.execute(select(PlayerStats).where(PlayerStats.player_id == p.id)).scalars().all()
    assert len(rows) == 2
    by_fmt = {r.format: r for r in rows}
    assert by_fmt["PremierDraft"].wins == 5
    assert by_fmt["PremierDraft"].expansion == "ECL"
    assert by_fmt["PremierDraft"].last_fetched_at is not None
    assert by_fmt["TradDraft"].trophies == 1


def test_refresh_player_passes_fetch_start(session):
    s = _seed_set(session)
    p = _seed_player(session)
    client = FakeClient(drafts=[])
    refresh_player(session, client, p, fetch_start=date(2026, 4, 1))
    assert client.calls == [(p.seventeenlands_token, date(2026, 4, 1), None)]


def test_refresh_player_updates_existing_row(session):
    s = _seed_set(session)
    p = _seed_player(session)
    session.add(PlayerStats(
        player_id=p.id, set_id=s.id, format="PremierDraft", expansion="ECL",
        events=1, wins=2, losses=1, games_played=3, trophies=0,
    ))
    session.flush()

    client = FakeClient(drafts=[{"format": "PremierDraft", "expansion": "ECL", "wins": 9, "losses": 4, "event_wins": 7}])
    refresh_player(session, client, p)
    session.flush()

    row = session.execute(select(PlayerStats).where(PlayerStats.player_id == p.id)).scalar_one()
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

    refresh_player(session, client, p)
    session.flush()

    rows = session.execute(
        select(PlayerStats).where(PlayerStats.player_id == p.id, PlayerStats.format == "PremierDraft")
    ).scalars().all()
    by_exp = {r.expansion: r for r in rows}
    assert set(by_exp) == {"ECL", "Y26ECL"}
    assert by_exp["ECL"].wins == 5
    assert by_exp["Y26ECL"].trophies == 1


def test_refresh_player_routes_drafts_across_sets(session):
    sos = _seed_set(session, code="SOS", start_date=date(2026, 4, 21))
    ecl = _seed_set(session, code="ECL", start_date=date(2026, 1, 20))
    p = _seed_player(session)
    client = FakeClient(drafts=[
        {"format": "PremierDraft", "expansion": "SOS", "wins": 7, "losses": 0, "event_wins": 7},
        {"format": "PremierDraft", "expansion": "ECL", "wins": 4, "losses": 3, "event_wins": 0},
    ])

    refresh_player(session, client, p)
    session.flush()

    rows = session.execute(select(PlayerStats).where(PlayerStats.player_id == p.id)).scalars().all()
    by_set = {r.set_id: r for r in rows}
    assert by_set[sos.id].trophies == 1
    assert by_set[ecl.id].wins == 4


def test_refresh_player_404_invalidates_token(session):
    s = _seed_set(session)
    p = _seed_player(session)
    client = FakeClient(raise_=_make_404())

    result = refresh_player(session, client, p)
    session.flush()

    assert result == {"status": "invalidated"}
    assert p.token_invalid is True
    rows = session.execute(select(PlayerStats).where(PlayerStats.player_id == p.id)).scalars().all()
    assert rows == []


def test_refresh_player_malformed_response_does_not_invalidate(session):
    """Signup verifies tokens, so a malformed 200 is a 17lands bug — don't blame the user."""
    s = _seed_set(session)
    p = _seed_player(session)
    client = FakeClient(raise_=ValueError("bad json"))

    result = refresh_player(session, client, p)

    assert result["status"] == "error"
    assert p.token_invalid is False


def test_refresh_player_5xx_does_not_invalidate(session):
    s = _seed_set(session)
    p = _seed_player(session)
    client = FakeClient(raise_=_make_500())

    result = refresh_player(session, client, p)

    assert result["status"] == "error"
    assert p.token_invalid is False


def test_refresh_player_network_error_does_not_invalidate(session):
    s = _seed_set(session)
    p = _seed_player(session)
    client = FakeClient(raise_=requests.ConnectTimeout("timeout"))

    result = refresh_player(session, client, p)

    assert result["status"] == "error"
    assert p.token_invalid is False


def test_refresh_active_players_skips_token_invalid_and_inactive(session):
    _seed_active_set(session)
    active_ok = _seed_player(session, name="ok", token_suffix="a")
    _seed_player(session, name="inactive", token_suffix="b", active=False)
    _seed_player(session, name="invalid", token_suffix="c", token_invalid=True)
    session.flush()

    client = FakeClient(drafts=[{"format": "PremierDraft", "expansion": ACTIVE_SET_CODE, "wins": 7, "losses": 0, "event_wins": 7}])

    summary = refresh_active_players(session, client)

    assert summary["updated"] == 1
    assert summary["invalidated"] == 0
    assert summary["errors"] == 0
    assert [c[0] for c in client.calls] == [active_ok.seventeenlands_token]


def test_refresh_active_players_does_not_call_client_when_all_skipped(session):
    _seed_active_set(session)
    _seed_player(session, name="inactive", token_suffix="a", active=False)
    _seed_player(session, name="invalid", token_suffix="b", token_invalid=True)
    session.flush()

    summary = refresh_active_players(session, ExplodingClient())
    assert summary["updated"] == 0
    assert summary["invalidated"] == 0
    assert summary["errors"] == 0


def test_refresh_active_players_summary_counts(session):
    _seed_active_set(session)
    p_ok = _seed_player(session, name="ok", token_suffix="a")
    p_404 = _seed_player(session, name="bad", token_suffix="b")
    p_5xx = _seed_player(session, name="flaky", token_suffix="c")
    session.flush()

    error_404 = _make_404()
    error_500 = _make_500()

    class RoutingClient:
        def __init__(self):
            self.calls = []

        def fetch_drafts(self, token, start_date=None, end_date=None):
            self.calls.append(token)
            if token == p_404.seventeenlands_token:
                raise error_404
            if token == p_5xx.seventeenlands_token:
                raise error_500
            return [{"format": "PremierDraft", "expansion": ACTIVE_SET_CODE, "wins": 3, "losses": 2}]

    summary = refresh_active_players(session, RoutingClient())

    assert summary["updated"] == 1
    assert summary["invalidated"] == 1
    assert summary["errors"] == 1
    assert summary["invalidated_players"] == [p_404.id]
    session.refresh(p_404)
    session.refresh(p_5xx)
    assert p_404.token_invalid is True
    assert p_5xx.token_invalid is False


def test_refresh_active_players_no_active_set(session):
    _seed_set(session, code="OLD")
    _seed_player(session)
    session.flush()
    summary = refresh_active_players(session, ExplodingClient())
    assert summary["status"] == "no_active_set"
    assert summary["updated"] == 0


def test_refresh_active_players_all_sets_uses_earliest_start(session):
    _seed_set(session, code="A", start_date=date(2025, 6, 9))
    _seed_set(session, code="B", start_date=date(2026, 1, 20))
    p = _seed_player(session)
    session.flush()
    client = FakeClient(drafts=[])
    refresh_active_players_all_sets(session, client)
    assert client.calls and client.calls[0][1] == date(2025, 6, 9)


def test_refresh_one_player_no_sets(session):
    p = _seed_player(session)
    session.commit()
    result = refresh_one_player_for_all_sets(session, FakeClient(), p.id)
    assert result == {"status": "no_sets"}


def test_refresh_one_player_unknown_player_id(session):
    _seed_set(session, code="SOS")
    result = refresh_one_player_for_all_sets(session, FakeClient(), "nonexistent-id")
    assert result == {"status": "no_player"}


def test_refresh_one_player_for_all_sets_writes_rows_per_set(session):
    _seed_set(session, code="SOS", start_date=date(2026, 4, 21))
    _seed_set(session, code="ECL", start_date=date(2026, 1, 20))
    p = _seed_player(session)
    session.commit()
    client = FakeClient(drafts=[
        {"format": "PremierDraft", "expansion": "SOS", "wins": 5, "losses": 2, "event_wins": 7},
        {"format": "PremierDraft", "expansion": "ECL", "wins": 7, "losses": 0, "event_wins": 7},
    ])

    result = refresh_one_player_for_all_sets(session, client, p.id)
    session.commit()

    assert result["status"] == "updated"
    assert result["rows"] == 2
    assert client.calls == [(p.seventeenlands_token, date(2026, 1, 20), None)]
    rows = session.execute(select(PlayerStats).where(PlayerStats.player_id == p.id)).scalars().all()
    assert len(rows) == 2


def _draft(event_id, **overrides):
    base = {
        "id": event_id,
        "format": "PremierDraft",
        "expansion": "SOS",
        "wins": 5,
        "losses": 3,
        "event_wins": 0,
        "colors": "WB",
        "start_rank": "Gold-3",
        "end_rank": "Platinum-4",
        "first_event_server_time": "2026-04-28 23:16:43",
        "last_event_server_time": "2026-04-28 23:39:04",
    }
    base.update(overrides)
    return base


def test_upsert_draft_events_inserts_each_event(session):
    s = _seed_set(session, code="SOS")
    p = _seed_player(session)
    session.flush()

    drafts = [_draft("ev-a"), _draft("ev-b"), _draft("ev-c", colors="WBg", event_wins=7)]
    n = upsert_draft_events(session, p.id, s.id, drafts, "SOS")
    session.flush()

    assert n == 3
    rows = session.execute(select(DraftEvent).where(DraftEvent.player_id == p.id)).scalars().all()
    assert sorted(r.seventeenlands_event_id for r in rows) == ["ev-a", "ev-b", "ev-c"]
    by_id = {r.seventeenlands_event_id: r for r in rows}
    assert by_id["ev-c"].colors == "WBg"
    assert by_id["ev-c"].is_trophy is True


def test_upsert_draft_events_idempotent(session):
    """Re-running with the same drafts must not duplicate rows."""
    s = _seed_set(session, code="SOS")
    p = _seed_player(session)
    session.flush()

    drafts = [_draft("ev-a"), _draft("ev-b")]
    upsert_draft_events(session, p.id, s.id, drafts, "SOS")
    session.flush()
    upsert_draft_events(session, p.id, s.id, drafts, "SOS")
    session.flush()

    count = session.execute(select(DraftEvent).where(DraftEvent.player_id == p.id)).scalars().all()
    assert len(count) == 2


def test_upsert_draft_events_updates_changed_fields(session):
    """Refetched event with new wins/colors should overwrite the old row."""
    s = _seed_set(session, code="SOS")
    p = _seed_player(session)
    session.flush()

    upsert_draft_events(session, p.id, s.id, [_draft("ev-a", wins=2, colors="WB")], "SOS")
    session.flush()
    upsert_draft_events(session, p.id, s.id, [_draft("ev-a", wins=7, colors="WBg", event_wins=7)], "SOS")
    session.flush()

    [row] = session.execute(select(DraftEvent).where(DraftEvent.player_id == p.id)).scalars().all()
    assert row.wins == 7
    assert row.colors == "WBg"
    assert row.is_trophy is True


def test_upsert_draft_events_isolates_per_player(session):
    """Same 17lands event id under different players must not collide."""
    s = _seed_set(session, code="SOS")
    p1 = _seed_player(session, name="P1", token_suffix="a")
    p2 = _seed_player(session, name="P2", token_suffix="b")
    session.flush()

    upsert_draft_events(session, p1.id, s.id, [_draft("shared-id", wins=7)], "SOS")
    upsert_draft_events(session, p2.id, s.id, [_draft("shared-id", wins=2)], "SOS")
    session.flush()

    rows = session.execute(select(DraftEvent)).scalars().all()
    assert len(rows) == 2
    by_player = {r.player_id: r for r in rows}
    assert by_player[p1.id].wins == 7
    assert by_player[p2.id].wins == 2


def test_refresh_player_writes_draft_events(session):
    """refresh_player should populate draft_events alongside player_stats."""
    s = _seed_set(session, code="SOS")
    p = _seed_player(session)
    drafts = [
        _draft("alpha", wins=7, event_wins=7, colors="WB"),
        _draft("beta", wins=4, losses=3, event_wins=0, colors="UR"),
    ]
    client = FakeClient(drafts=drafts)

    refresh_player(session, client, p)
    session.flush()

    events = session.execute(select(DraftEvent).where(DraftEvent.player_id == p.id)).scalars().all()
    assert sorted(e.seventeenlands_event_id for e in events) == ["alpha", "beta"]
    by_id = {e.seventeenlands_event_id: e for e in events}
    assert by_id["alpha"].is_trophy is True
    assert by_id["beta"].colors == "UR"
