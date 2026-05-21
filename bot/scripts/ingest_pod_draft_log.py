"""Ingest a raw Draftmancer DraftLog .txt into a pod_draft_events row.

Packs the log into compact-gz form (same shape build_compact emits), stores it on
pod_draft_events.draft_log_gz, reconciles pod_draft_participants.draftmancer_name to match the
canonical Draftmancer userName, applies seat indexes + mainboards, and (when MPT_API_KEY is set)
submits each non-bot seat to MagicProTools, stashing the URL on pod_draft_participants.draft_log_url.

    DATABASE_URL=... [MPT_API_KEY=...] python -m bot.scripts.ingest_pod_draft_log \\
        <event_id> <path/to/DraftLog.txt> [--no-mpt]

Idempotent — re-running overwrites draft_log_gz, re-applies mainboards, and re-aligns names from
the same log. Pass --no-mpt to skip the MagicProTools submission step.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import sys
from pathlib import Path

from sqlalchemy import select

from bot.config import settings
from bot.database import SessionLocal
from bot.models import Player, PodDraftEvent, PodDraftParticipant
from bot.scripts.draftmancer_log import build_compact
from bot.services.magicprotools import submit_to_api
from bot.services.pod_draft_manager import _apply_mainboards, _apply_seat_indexes


def _arena_name_needs_fix(current: str | None, log_name: str) -> bool:
    """True if Player.arena_name is NULL, or if its #NNNN suffix is a strict prefix of the
    log's #NNNNN suffix AND the basename matches (truncated suffix repair). Leaves arena_name
    alone when the basename differs — that's a Draftmancer rename, not an Arena ID typo."""
    if current is None or not current.strip():
        return True
    cur_base, cur_suf = _split_name(current)
    log_base, log_suf = _split_name(log_name)
    if cur_base.casefold() != log_base.casefold():
        return False
    if cur_suf is None or log_suf is None:
        return False
    return cur_suf != log_suf and log_suf.startswith(cur_suf)


def _split_name(s: str) -> tuple[str, str | None]:
    if "#" in s:
        base, _, suf = s.rpartition("#")
        return base, suf
    return s, None


def _match_participant(
    log_name: str,
    participants: list[PodDraftParticipant],
    used: set[str],
) -> PodDraftParticipant | None:
    """Resolve a log userName to a participant row.

    Tries: exact draftmancer_name, then suffix-prefix (DB suffix is a prefix of log suffix —
    catches truncated #NNNN -> #NNNNN), then display_name basename + suffix prefix, then
    display_name basename alone, then draftmancer_name basename alone."""
    log_base, log_suf = _split_name(log_name)

    for p in participants:
        if p.id in used:
            continue
        if p.draftmancer_name and p.draftmancer_name == log_name:
            return p

    if log_suf is not None:
        for p in participants:
            if p.id in used:
                continue
            if not p.draftmancer_name or "#" not in p.draftmancer_name:
                continue
            _, db_suf = _split_name(p.draftmancer_name)
            if db_suf and log_suf.startswith(db_suf):
                return p

    if log_suf is not None:
        for p in participants:
            if p.id in used:
                continue
            db_base, db_suf = _split_name(p.display_name)
            if db_base.casefold() == log_base.casefold() and (db_suf is None or log_suf.startswith(db_suf)):
                return p

    for p in participants:
        if p.id in used:
            continue
        if p.display_name.casefold() == log_base.casefold():
            return p
        if p.draftmancer_name and _split_name(p.draftmancer_name)[0].casefold() == log_base.casefold():
            return p

    return None


async def _submit_mpt(event_id: str, log: dict) -> None:
    if settings.mpt_api_key is None:
        print("MPT_API_KEY not set; skipping MagicProTools submission")
        return
    seats = [
        (uid, ud) for uid, ud in log["users"].items()
        if isinstance(ud, dict)
        and ud.get("userName") and not ud.get("isBot")
    ]
    print(f"\nsubmitting {len(seats)} seat(s) to MagicProTools...")
    submitted = 0
    failed = 0
    for user_id, user_data in seats:
        user_name = user_data["userName"]
        url = await submit_to_api(user_id, log)
        if not url:
            print(f"  {user_name}: MPT submit failed")
            failed += 1
            continue
        with SessionLocal() as session:
            rows = session.execute(
                select(PodDraftParticipant).where(
                    PodDraftParticipant.event_id == event_id,
                    PodDraftParticipant.draftmancer_name == user_name,
                )
            ).scalars().all()
            if not rows:
                print(f"  {user_name}: no participant row, URL discarded")
                continue
            for row in rows:
                row.draft_log_url = url
            session.commit()
        print(f"  {user_name}: {url}")
        submitted += 1
    print(f"MPT done: submitted={submitted} failed={failed}")


async def main(event_id: str, log_path: Path, submit_mpt: bool) -> int:
    with log_path.open() as f:
        log = json.load(f)

    user_names = [u["userName"] for u in log["users"].values()]
    print(f"log: {len(user_names)} seats, sid={log.get('sessionID')}")

    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is None:
            print(f"event {event_id} not found", file=sys.stderr)
            return 1

        participants = session.execute(
            select(PodDraftParticipant).where(PodDraftParticipant.event_id == event_id)
        ).scalars().all()

        if len(participants) != len(user_names):
            print(f"WARN: event has {len(participants)} participants, log has {len(user_names)}", file=sys.stderr)

        used: set[str] = set()
        renamed = 0
        unchanged = 0
        arena_fixed = 0
        unmatched: list[str] = []
        for name in user_names:
            p = _match_participant(name, participants, used)
            if p is None:
                unmatched.append(name)
                continue
            used.add(p.id)
            if p.draftmancer_name == name:
                unchanged += 1
            else:
                print(f"  rename: {p.display_name!r}  {p.draftmancer_name!r} -> {name!r}")
                p.draftmancer_name = name
                renamed += 1
            if p.player_id is not None:
                player = session.get(Player, p.player_id)
                if player is not None and _arena_name_needs_fix(player.arena_name, name):
                    print(f"  player.arena_name: {player.display_name!r}  {player.arena_name!r} -> {name!r}")
                    player.arena_name = name
                    arena_fixed += 1

        if unmatched:
            print(f"\nUNMATCHED log users (no participant): {unmatched}", file=sys.stderr)
            print("aborting — fix manually before re-running", file=sys.stderr)
            session.rollback()
            return 2

        compact = build_compact(log)
        event.draft_log_gz = gzip.compress(
            json.dumps(compact, separators=(",", ":")).encode(), compresslevel=9
        )
        print(f"stored draft_log_gz: {len(event.draft_log_gz):,} bytes")
        _apply_seat_indexes(session, event_id, compact.get("seats") or [])
        _apply_mainboards(session, event_id, log)
        session.commit()

    print(f"done: renamed={renamed} unchanged={unchanged} arena_fixed={arena_fixed}")

    if submit_mpt:
        await _submit_mpt(event_id, log)

    return 0


if __name__ == "__main__":
    raw_args = sys.argv[1:]
    submit_mpt = "--no-mpt" not in raw_args
    pos = [a for a in raw_args if a != "--no-mpt"]
    if len(pos) != 2:
        print(
            "usage: python -m bot.scripts.ingest_pod_draft_log <event_id> <path/to/DraftLog.txt> [--no-mpt]",
            file=sys.stderr,
        )
        sys.exit(64)
    sys.exit(asyncio.run(main(pos[0], Path(pos[1]), submit_mpt)))
