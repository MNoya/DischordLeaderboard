"""Populate pod_draft_participants.seat_index from each event's stored draft_log_gz.

    DATABASE_URL=... python -m bot.scripts.backfill_pod_seat_indexes [event_id ...]

With no args, runs across every event that has a draft_log_gz. With one or more event_ids, only
those events are processed. Skips events without a stored log. Overwrites existing seat_index
values so re-running after a model change is safe.
"""
from __future__ import annotations

import gzip
import json
import re
import sys

from sqlalchemy import select

from bot.database import SessionLocal
from bot.models import PodDraftEvent, PodDraftParticipant
from bot.services.pod_drafts import normalize_player_name


_BOT_USER_NAME = "DisChordBot"
_AI_BOT_RE = re.compile(r"^Bot #\d+$")


def apply_for_event(session, event_id: str) -> tuple[int, int]:
    event = session.get(PodDraftEvent, event_id)
    if event is None or event.draft_log_gz is None:
        return (0, 0)
    compact = json.loads(gzip.decompress(event.draft_log_gz).decode("utf-8"))
    seats: list[str] = compact.get("seats") or []
    rows = session.execute(
        select(PodDraftParticipant).where(PodDraftParticipant.event_id == event_id)
    ).scalars().all()
    by_dm = {normalize_player_name(r.draftmancer_name): r for r in rows if r.draftmancer_name}
    by_display = {normalize_player_name(r.display_name): r for r in rows if r.display_name}
    matched = 0
    for i, name in enumerate(seats):
        if not name or name == _BOT_USER_NAME or _AI_BOT_RE.match(name):
            continue
        key = normalize_player_name(name)
        row = by_dm.get(key) or by_display.get(key)
        if row is None:
            print(f"  {event_id}: no participant matching {name!r} at seat {i}")
            continue
        row.seat_index = i
        matched += 1
    return (matched, len(seats))


def main(event_ids: list[str]) -> int:
    with SessionLocal() as session:
        if event_ids:
            targets = event_ids
        else:
            targets = [
                e.id for e in session.execute(
                    select(PodDraftEvent).where(PodDraftEvent.draft_log_gz.isnot(None))
                ).scalars().all()
            ]
        if not targets:
            print("no events with a stored draft_log_gz")
            return 0
        total_matched = 0
        total_seats = 0
        for eid in targets:
            matched, seats = apply_for_event(session, eid)
            if seats == 0:
                print(f"  {eid}: no draft_log_gz, skipping")
                continue
            print(f"  {eid}: {matched}/{seats} seats")
            total_matched += matched
            total_seats += seats
        session.commit()
        print(f"\ndone: {total_matched}/{total_seats} seats matched across {len(targets)} events")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
