"""Manually update event_time / event_date on a pod_draft_events row.

    DATABASE_URL=... python -m bot.scripts.reschedule_pod_event <event_id> <new_iso_time>

new_iso_time is parsed by datetime.fromisoformat — use e.g. "2026-05-20T20:00:00+00:00".
event_date is recomputed from the new time in POD_DRAFT_FALLBACK_TZ. Refuses to touch
completed events. The in-memory APScheduler job is NOT touched — restart the bot
afterwards so the startup sweep re-arms it from the new value.
"""
from __future__ import annotations

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from bot.config import settings
from bot.database import SessionLocal
from bot.models import PodDraftEvent


def main(event_id: str, new_time_iso: str) -> None:
    new_time = datetime.fromisoformat(new_time_iso)
    if new_time.tzinfo is None:
        raise SystemExit("new_iso_time must include a timezone offset, e.g. ...+00:00")
    new_date = new_time.astimezone(ZoneInfo(settings.pod_draft_fallback_tz)).date()

    with SessionLocal() as session:
        event = session.execute(
            select(PodDraftEvent).where(PodDraftEvent.id == event_id)
        ).scalar_one_or_none()
        if event is None:
            raise SystemExit(f"no pod_draft_event with id={event_id}")
        if event.socket_status == "complete":
            raise SystemExit(f"event {event_id} is already complete; refusing to update")

        print(f"event:        {event.name}")
        print(f"thread:       {event.discord_thread_id}")
        print(f"old time:     {event.event_time.isoformat()} (date {event.event_date})")
        print(f"new time:     {new_time.isoformat()} (date {new_date})")

        event.event_time = new_time
        event.event_date = new_date
        session.commit()
        print("updated.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    main(sys.argv[1], sys.argv[2])
