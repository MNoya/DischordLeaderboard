from datetime import date

import pytest
import requests
import responses

from bot.services.seventeenlands import (
    DEFAULT_BASE_URL,
    SUPPORTED_FORMATS,
    MinIntervalLimiter,
    SeventeenLandsClient,
    aggregate_for_set,
    extract_events_for_set,
    extract_token,
)


VALID_TOKEN = "10c0f8918a2b4fa7b230448caee0b2ca"


# ---------------------------------------------------------------------------
# extract_token
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        VALID_TOKEN,
        f"  {VALID_TOKEN}  ",
        VALID_TOKEN.upper(),
        f"https://www.17lands.com/user_history/{VALID_TOKEN}",
        f"https://www.17lands.com/user/data/{VALID_TOKEN}?start_date=2026-01-20",
        f"http://17lands.com/user_history/{VALID_TOKEN}/",
    ],
)
def test_extract_token_accepts_valid_inputs(raw):
    assert extract_token(raw) == VALID_TOKEN


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not-a-token",
        "https://www.17lands.com/user_history/short",
        "g" * 32,  # right length, wrong charset
    ],
)
def test_extract_token_rejects_invalid_inputs(raw):
    with pytest.raises(ValueError):
        extract_token(raw)


def test_extract_token_handles_none():
    with pytest.raises(ValueError):
        extract_token(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# MinIntervalLimiter
# ---------------------------------------------------------------------------


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_first_wait_does_not_sleep():
    clk = FakeClock()
    limiter = MinIntervalLimiter(min_interval_s=1.0, sleep=clk.sleep, clock=clk.time)

    limiter.wait()

    assert clk.sleeps == []


def test_second_wait_within_interval_sleeps_remainder():
    clk = FakeClock()
    limiter = MinIntervalLimiter(min_interval_s=1.0, sleep=clk.sleep, clock=clk.time)

    limiter.wait()
    clk.now += 0.3  # only 0.3s passed
    limiter.wait()

    assert clk.sleeps == [pytest.approx(0.7)]


def test_second_wait_after_interval_does_not_sleep():
    clk = FakeClock()
    limiter = MinIntervalLimiter(min_interval_s=1.0, sleep=clk.sleep, clock=clk.time)

    limiter.wait()
    clk.now += 5.0
    limiter.wait()

    assert clk.sleeps == []


def test_zero_interval_never_sleeps():
    clk = FakeClock()
    limiter = MinIntervalLimiter(min_interval_s=0, sleep=clk.sleep, clock=clk.time)

    for _ in range(5):
        limiter.wait()

    assert clk.sleeps == []


# ---------------------------------------------------------------------------
# SeventeenLandsClient
# ---------------------------------------------------------------------------


def _client() -> SeventeenLandsClient:
    return SeventeenLandsClient(limiter=MinIntervalLimiter(min_interval_s=0))


@responses.activate
def test_fetch_drafts_returns_drafts_list():
    drafts = [{"format": "PremierDraft", "wins": 7, "losses": 2}]
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/user/data/{VALID_TOKEN}",
        json={"drafts": drafts},
        status=200,
    )

    result = _client().fetch_drafts(VALID_TOKEN)

    assert result == drafts


@responses.activate
def test_fetch_drafts_passes_start_date():
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/user/data/{VALID_TOKEN}",
        json={"drafts": []},
        status=200,
        match=[responses.matchers.query_param_matcher({"start_date": "2026-01-20"})],
    )

    result = _client().fetch_drafts(VALID_TOKEN, start_date=date(2026, 1, 20))

    assert result == []


@responses.activate
def test_fetch_drafts_passes_end_date():
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/user/data/{VALID_TOKEN}",
        json={"drafts": []},
        status=200,
        match=[responses.matchers.query_param_matcher({
            "start_date": "2026-01-20",
            "end_date": "2026-04-20",
        })],
    )

    result = _client().fetch_drafts(
        VALID_TOKEN,
        start_date=date(2026, 1, 20),
        end_date=date(2026, 4, 20),
    )

    assert result == []


@responses.activate
def test_fetch_drafts_raises_on_http_error():
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/user/data/{VALID_TOKEN}",
        status=500,
    )

    with pytest.raises(requests.HTTPError):
        _client().fetch_drafts(VALID_TOKEN)


@responses.activate
def test_fetch_drafts_raises_on_missing_drafts_key():
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/user/data/{VALID_TOKEN}",
        json={"oops": "bad shape"},
        status=200,
    )

    with pytest.raises(ValueError):
        _client().fetch_drafts(VALID_TOKEN)


@responses.activate
def test_fetch_drafts_handles_null_drafts():
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/user/data/{VALID_TOKEN}",
        json={"drafts": None},
        status=200,
    )

    assert _client().fetch_drafts(VALID_TOKEN) == []


@responses.activate
def test_verify_token_true_for_200_with_drafts_key():
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/user/data/{VALID_TOKEN}",
        json={"drafts": []},
        status=200,
    )

    assert _client().verify_token(VALID_TOKEN) is True


@responses.activate
def test_verify_token_false_for_404():
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/user/data/{VALID_TOKEN}",
        status=404,
    )

    assert _client().verify_token(VALID_TOKEN) is False


@responses.activate
def test_verify_token_false_for_malformed_json():
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/user/data/{VALID_TOKEN}",
        body="not json",
        status=200,
        content_type="text/html",
    )

    assert _client().verify_token(VALID_TOKEN) is False


@responses.activate
def test_verify_token_false_on_network_error():
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}/user/data/{VALID_TOKEN}",
        body=requests.ConnectionError("boom"),
    )

    assert _client().verify_token(VALID_TOKEN) is False


def test_client_invokes_limiter_once_per_call():
    calls = {"n": 0}

    class CountingLimiter:
        def wait(self):
            calls["n"] += 1

    client = SeventeenLandsClient(limiter=CountingLimiter())  # type: ignore[arg-type]
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            f"{DEFAULT_BASE_URL}/user/data/{VALID_TOKEN}",
            json={"drafts": []},
            status=200,
        )
        rsps.add(
            responses.GET,
            f"{DEFAULT_BASE_URL}/user/data/{VALID_TOKEN}",
            json={"drafts": []},
            status=200,
        )
        client.fetch_drafts(VALID_TOKEN)
        client.verify_token(VALID_TOKEN)

    assert calls["n"] == 2


# ---------------------------------------------------------------------------
# aggregate_for_set
# ---------------------------------------------------------------------------


def test_aggregate_empty_drafts_returns_zeroed_buckets():
    result = aggregate_for_set([], "ECL")
    assert set(result.keys()) == set(SUPPORTED_FORMATS)
    for stats in result.values():
        assert stats == {"wins": 0, "losses": 0, "games_played": 0, "trophies": 0}


def test_aggregate_filters_unsupported_formats():
    drafts = [
        {"format": "MidWeekSealed", "expansion": "ECL", "wins": 7, "losses": 0, "event_wins": 7},
    ]
    result = aggregate_for_set(drafts, "ECL")
    for stats in result.values():
        assert stats["wins"] == 0
        assert stats["games_played"] == 0


def test_aggregate_filters_other_sets():
    drafts = [
        {"format": "PremierDraft", "expansion": "BLB", "wins": 7, "losses": 0, "event_wins": 7},
        {"format": "PremierDraft", "expansion": "ECL", "wins": 5, "losses": 3, "event_wins": 0},
    ]
    result = aggregate_for_set(drafts, "ECL")
    assert result["PremierDraft"] == {
        "wins": 5,
        "losses": 3,
        "games_played": 8,
        "trophies": 0,
    }


def test_aggregate_substring_match_includes_alchemy_variants():
    """Y26ECL should bucket under ECL — mirrors legacy 'in' behavior."""
    drafts = [
        {"format": "PremierDraft", "expansion": "Y26ECL", "wins": 7, "losses": 1, "event_wins": 7},
        {"format": "PremierDraft", "expansion": "ECL", "wins": 4, "losses": 3, "event_wins": 0},
    ]
    result = aggregate_for_set(drafts, "ECL")
    assert result["PremierDraft"]["wins"] == 11
    assert result["PremierDraft"]["losses"] == 4
    assert result["PremierDraft"]["games_played"] == 15
    assert result["PremierDraft"]["trophies"] == 1


def test_aggregate_counts_trophies_via_event_wins():
    """A trad 4-0 (event_wins truthy but != 7) still counts as a trophy."""
    drafts = [
        {"format": "TradDraft", "expansion": "ECL", "wins": 4, "losses": 0, "event_wins": 4},
        {"format": "TradDraft", "expansion": "ECL", "wins": 2, "losses": 1, "event_wins": 0},
    ]
    result = aggregate_for_set(drafts, "ECL")
    assert result["TradDraft"]["trophies"] == 1
    assert result["TradDraft"]["wins"] == 6


def test_aggregate_handles_missing_fields():
    drafts = [
        {"format": "PremierDraft", "expansion": "ECL"},  # no wins/losses/event_wins
        {"format": "PremierDraft", "expansion": "ECL", "wins": None, "losses": None, "event_wins": None},
    ]
    result = aggregate_for_set(drafts, "ECL")
    assert result["PremierDraft"] == {
        "wins": 0,
        "losses": 0,
        "games_played": 0,
        "trophies": 0,
    }


def test_aggregate_sums_across_all_supported_formats():
    drafts = [
        {"format": "PremierDraft", "expansion": "ECL", "wins": 7, "losses": 2, "event_wins": 7},
        {"format": "TradDraft",    "expansion": "ECL", "wins": 4, "losses": 0, "event_wins": 4},
        {"format": "Sealed",       "expansion": "ECL", "wins": 3, "losses": 3, "event_wins": 0},
        {"format": "TradSealed",   "expansion": "ECL", "wins": 4, "losses": 1, "event_wins": 4},
    ]
    result = aggregate_for_set(drafts, "ECL")
    assert result["PremierDraft"]["trophies"] == 1
    assert result["TradDraft"]["trophies"] == 1
    assert result["Sealed"]["trophies"] == 0
    assert result["TradSealed"]["trophies"] == 1
    assert sum(s["games_played"] for s in result.values()) == 24


# ---------------------------------------------------------------------------
# extract_events_for_set
# ---------------------------------------------------------------------------


def _draft(**overrides):
    base = {
        "id": "abc123",
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


def test_extract_events_returns_one_per_draft():
    drafts = [_draft(id="a"), _draft(id="b"), _draft(id="c")]
    events = extract_events_for_set(drafts, "SOS")
    assert [e["seventeenlands_event_id"] for e in events] == ["a", "b", "c"]


def test_extract_events_preserves_color_case_for_splash():
    """Lowercase letters in colors are splash markers — case must survive."""
    drafts = [
        _draft(id="main", colors="WB"),
        _draft(id="splash", colors="WBg"),
        _draft(id="five", colors="WUBRG"),
        _draft(id="busy", colors="RGwub"),
        _draft(id="mono", colors="W"),
    ]
    events = extract_events_for_set(drafts, "SOS")
    by_id = {e["seventeenlands_event_id"]: e["colors"] for e in events}
    assert by_id == {"main": "WB", "splash": "WBg", "five": "WUBRG",
                     "busy": "RGwub", "mono": "W"}


def test_extract_events_handles_null_colors_and_ranks():
    drafts = [_draft(colors=None, start_rank=None, end_rank=None)]
    [event] = extract_events_for_set(drafts, "SOS")
    assert event["colors"] is None
    assert event["start_rank"] is None
    assert event["end_rank"] is None


def test_extract_events_trophy_flag_from_event_wins():
    drafts = [
        _draft(id="t", event_wins=7),
        _draft(id="nt", event_wins=0),
        _draft(id="trad", event_wins=4),
    ]
    events = extract_events_for_set(drafts, "SOS")
    assert {e["seventeenlands_event_id"]: e["is_trophy"] for e in events} == {
        "t": True, "nt": False, "trad": True,
    }


def test_extract_events_skips_unsupported_formats():
    drafts = [
        _draft(id="ok", format="PremierDraft"),
        _draft(id="bad", format="MidWeekSealed"),
    ]
    events = extract_events_for_set(drafts, "SOS")
    assert [e["seventeenlands_event_id"] for e in events] == ["ok"]


def test_extract_events_filters_by_set_substring():
    """Y26ECL matches set ECL — same rule as aggregate_for_set."""
    drafts = [
        _draft(id="alc", expansion="Y26ECL"),
        _draft(id="std", expansion="ECL"),
        _draft(id="other", expansion="SOS"),
    ]
    events = extract_events_for_set(drafts, "ECL")
    assert sorted(e["seventeenlands_event_id"] for e in events) == ["alc", "std"]


def test_extract_events_skips_events_without_id():
    drafts = [_draft(id=None), _draft(id="")]
    assert extract_events_for_set(drafts, "SOS") == []


def test_extract_events_parses_timestamps():
    drafts = [_draft(
        first_event_server_time="2026-04-28 23:16:43",
        last_event_server_time="2026-04-28 23:39:04",
    )]
    [event] = extract_events_for_set(drafts, "SOS")
    # 17lands serves UTC-naive strings; we tag them as UTC-aware on parse
    assert event["started_at"].isoformat() == "2026-04-28T23:16:43+00:00"
    assert event["finished_at"].isoformat() == "2026-04-28T23:39:04+00:00"


def test_extract_events_handles_minute_precision_timestamps():
    """Some 17lands timestamps come at minute precision (no seconds)."""
    drafts = [_draft(
        first_event_server_time="2026-04-28 23:16",
        last_event_server_time="2026-04-28 23:39",
    )]
    [event] = extract_events_for_set(drafts, "SOS")
    assert event["started_at"].isoformat() == "2026-04-28T23:16:00+00:00"
    assert event["finished_at"].isoformat() == "2026-04-28T23:39:00+00:00"


def test_extract_events_handles_missing_timestamps():
    drafts = [_draft(
        first_event_server_time=None,
        last_event_server_time=None,
    )]
    [event] = extract_events_for_set(drafts, "SOS")
    assert event["started_at"] is None
    assert event["finished_at"] is None
