"""CLI wrapper for bot.services.pod_log_ingest — ingest a raw Draftmancer DraftLog .txt.

    DATABASE_URL=... [MPT_API_KEY=...] python -m bot.scripts.ingest_pod_draft_log \\
        <event_id> <path/to/DraftLog.txt> [--no-mpt]

Idempotent — re-running overwrites draft_log_gz, re-applies mainboards, and re-aligns names from
the same log. Pass --no-mpt to skip the MagicProTools submission step.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from bot.services.pod_log_ingest import ingest_draft_log_sync, log_user_names, submit_log_to_mpt


async def main(event_id: str, log_path: Path, submit_mpt: bool) -> int:
    with log_path.open() as f:
        draft_log = json.load(f)

    user_names = log_user_names(draft_log)
    print(f"log: {len(user_names)} seats, sid={draft_log.get('sessionID')}")

    summary = ingest_draft_log_sync(event_id, draft_log)
    if summary is None:
        print(f"event {event_id} not found", file=sys.stderr)
        return 1
    if not summary.applied:
        print(f"\nUNMATCHED log users (no participant): {list(summary.unmatched)}", file=sys.stderr)
        print("aborting — fix manually before re-running", file=sys.stderr)
        return 2

    for line in summary.renames:
        print(f"  rename: {line}")
    for line in summary.arena_fixes:
        print(f"  player.arena_name: {line}")
    print(f"stored draft_log_gz: {summary.stored_bytes:,} bytes")
    print(f"done: renamed={summary.renamed} unchanged={summary.unchanged} arena_fixed={summary.arena_fixed}")

    if submit_mpt:
        mpt = await submit_log_to_mpt(event_id, draft_log)
        if mpt is None:
            print("MPT_API_KEY not set; skipping MagicProTools submission")
        else:
            for user_name, url in mpt.results:
                print(f"  {user_name}: {url or 'MPT submit failed'}")
            print(f"MPT done: submitted={mpt.submitted} failed={mpt.failed}")

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
