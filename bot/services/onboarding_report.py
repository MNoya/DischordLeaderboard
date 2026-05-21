"""Per-period onboarding summary for the bi-daily refresh report.

`recent_joiners` reads `Player.joined_at`; `recent_join_failures` walks
`logs/events.jsonl` and aggregates the audit events emitted by /join and the
auto-link listener.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.audit import EVENTS_FILE
from bot.models import Player

JOIN_RESULT_TYPES = {"signup_result", "auto_link_signup_result"}
JOIN_ENVELOPE_TYPES = {"signup_invoked", "auto_link_detected"}
JOIN_TERMINAL_TYPES = {"signup_dms_disabled", "signup_timeout"}
FAIL_KINDS = {"invalid_format", "rejected_by_17lands", "token_in_use"}


def recent_joiners(session: Session, since: datetime) -> list[Player]:
    return list(
        session.execute(
            select(Player)
            .where(Player.joined_at >= since)
            .order_by(Player.joined_at)
        ).scalars().all()
    )


def recent_join_failures(since: datetime, log_path: Path = EVENTS_FILE) -> list[dict]:
    """Aggregate one entry per user who tried to join but didn't make it.

    Walks the audit JSONL once, collecting username envelopes (signup_invoked /
    auto_link_detected) plus terminal failure events. Returns the most-recent
    failure per user_id, with the best-known username attached.
    """
    if not log_path.exists():
        return []

    usernames: dict[str, str] = {}
    failures: dict[str, dict] = {}

    for rec in _iter_jsonl(log_path):
        ts = _parse_ts(rec.get("ts"))
        if ts is None or ts < since:
            continue
        t = rec.get("type")
        uid = rec.get("user_id")
        if not uid:
            continue
        if t in JOIN_ENVELOPE_TYPES:
            name = rec.get("username")
            if name:
                usernames[uid] = name
            continue
        reason: str | None = None
        if t in JOIN_RESULT_TYPES and rec.get("kind") in FAIL_KINDS:
            reason = rec.get("kind")
        elif t == "signup_dms_disabled":
            reason = "dms_disabled"
        elif t == "signup_timeout":
            reason = "timed_out"
        if reason is None:
            continue
        name = rec.get("username") or usernames.get(uid)
        if name:
            usernames[uid] = name
        failures[uid] = {"user_id": uid, "username": usernames.get(uid), "reason": reason, "ts": ts}

    # If a user later succeeded, drop the prior failure
    succeeded = _users_who_succeeded(since, log_path)
    for uid in succeeded:
        failures.pop(uid, None)

    return sorted(failures.values(), key=lambda r: r["ts"])


def format_report_section(
    joiners: Iterable[Player],
    failures: Iterable[dict],
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    joiners = list(joiners)
    failures = list(failures)
    if not joiners and not failures:
        return ""

    lines: list[str] = []
    if joiners:
        lines.append(f"🆕 New joiners: {len(joiners)}")
        for p in joiners:
            lines.append(f"  • {p.display_name} ({_fmt_ago(p.joined_at, now)})")
    if failures:
        lines.append(f"⚠️ Failed to join: {len(failures)}")
        for f in failures:
            name = f.get("username") or f"user:{f['user_id']}"
            lines.append(f"  • {name} — {f['reason']} ({_fmt_ago(f['ts'], now)})")
    return "\n".join(lines)


def _users_who_succeeded(since: datetime, log_path: Path) -> set[str]:
    out: set[str] = set()
    for rec in _iter_jsonl(log_path):
        ts = _parse_ts(rec.get("ts"))
        if ts is None or ts < since:
            continue
        if rec.get("type") in JOIN_RESULT_TYPES and rec.get("kind") == "created":
            uid = rec.get("user_id")
            if uid:
                out.add(uid)
    return out


def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _parse_ts(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _fmt_ago(ts: datetime, now: datetime) -> str:
    delta = now - ts
    secs = int(delta.total_seconds())
    if secs < 0:
        return "just now"
    if secs < 60:
        return f"{secs}s ago"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"
