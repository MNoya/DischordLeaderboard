from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from bot.services.onboarding_report import format_report_section, recent_join_failures


NOW = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)


def _write_events(path, events):
    with path.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev, default=str) + "\n")


def test_aggregates_username_from_invoked_envelope(tmp_path):
    log = tmp_path / "events.jsonl"
    _write_events(log, [
        {"ts": (NOW - timedelta(hours=1)).isoformat(), "type": "signup_invoked", "user_id": "111", "username": "alice#0001"},
        {"ts": (NOW - timedelta(minutes=30)).isoformat(), "type": "signup_result", "user_id": "111", "kind": "invalid_format"},
    ])

    failures = recent_join_failures(NOW - timedelta(hours=12), log_path=log)
    assert len(failures) == 1
    assert failures[0]["username"] == "alice#0001"
    assert failures[0]["reason"] == "invalid_format"


def test_drops_failures_when_user_eventually_succeeded(tmp_path):
    log = tmp_path / "events.jsonl"
    _write_events(log, [
        {"ts": (NOW - timedelta(hours=2)).isoformat(), "type": "signup_invoked", "user_id": "111", "username": "alice"},
        {"ts": (NOW - timedelta(hours=1, minutes=30)).isoformat(), "type": "signup_result", "user_id": "111", "kind": "invalid_format"},
        {"ts": (NOW - timedelta(hours=1)).isoformat(), "type": "signup_result", "user_id": "111", "kind": "created"},
    ])

    assert recent_join_failures(NOW - timedelta(hours=12), log_path=log) == []


def test_ignores_events_outside_window(tmp_path):
    log = tmp_path / "events.jsonl"
    _write_events(log, [
        {"ts": (NOW - timedelta(days=2)).isoformat(), "type": "signup_result", "user_id": "111", "kind": "invalid_format", "username": "old"},
        {"ts": (NOW - timedelta(hours=3)).isoformat(), "type": "signup_result", "user_id": "222", "kind": "invalid_format", "username": "fresh"},
    ])

    failures = recent_join_failures(NOW - timedelta(hours=12), log_path=log)
    assert [f["user_id"] for f in failures] == ["222"]


def test_picks_up_timeouts_and_dms_disabled(tmp_path):
    log = tmp_path / "events.jsonl"
    _write_events(log, [
        {"ts": (NOW - timedelta(hours=1)).isoformat(), "type": "signup_invoked", "user_id": "1", "username": "carol"},
        {"ts": (NOW - timedelta(minutes=50)).isoformat(), "type": "signup_timeout", "user_id": "1", "username": "carol"},
        {"ts": (NOW - timedelta(minutes=30)).isoformat(), "type": "signup_dms_disabled", "user_id": "2", "username": "dave"},
    ])

    reasons = {f["user_id"]: f["reason"] for f in recent_join_failures(NOW - timedelta(hours=12), log_path=log)}
    assert reasons == {"1": "timed_out", "2": "dms_disabled"}


def test_auto_link_signup_failures_count_too(tmp_path):
    log = tmp_path / "events.jsonl"
    _write_events(log, [
        {"ts": (NOW - timedelta(hours=1)).isoformat(), "type": "auto_link_detected", "user_id": "9", "username": "erin"},
        {"ts": (NOW - timedelta(minutes=45)).isoformat(), "type": "auto_link_signup_result", "user_id": "9", "username": "erin", "kind": "token_in_use"},
    ])

    failures = recent_join_failures(NOW - timedelta(hours=12), log_path=log)
    assert len(failures) == 1
    assert failures[0]["reason"] == "token_in_use"
    assert failures[0]["username"] == "erin"


def test_format_report_section_renders_both_lists():
    class FakePlayer:
        def __init__(self, name, joined_at):
            self.display_name = name
            self.joined_at = joined_at

    joiners = [FakePlayer("alice", NOW - timedelta(hours=2))]
    failures = [{"user_id": "9", "username": "bob", "reason": "invalid_format", "ts": NOW - timedelta(minutes=30)}]

    out = format_report_section(joiners, failures, now=NOW)
    assert "🆕 New joiners: 1" in out
    assert "alice (2h ago)" in out
    assert "⚠️ Failed to join: 1" in out
    assert "bob — invalid_format" in out


def test_format_report_section_empty_returns_empty_string():
    assert format_report_section([], [], now=NOW) == ""
