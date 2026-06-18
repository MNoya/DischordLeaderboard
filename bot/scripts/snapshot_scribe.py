"""Refresh the bundled MTG Scribe fallback snapshot from a clean (residential) IP.

The bot fetches MTG Scribe directly, but SiteGround's anti-bot intermittently challenges datacenter
IPs, so a bundled snapshot backs ``mtgscribe.fetch_events`` when the live call is blocked. Run this
from a machine that isn't challenged (a laptop) to refresh it, e.g. after a set rotation:

    .venv/bin/python -m bot.scripts.snapshot_scribe
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from bot.services import mtgscribe

LOOKBACK_DAYS = 90


def main() -> None:
    raw = mtgscribe.fetch_raw_events(date.today() - timedelta(days=LOOKBACK_DAYS))
    snapshot = [_trim(event) for event in raw]
    mtgscribe.FALLBACK_PATH.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(snapshot)} events to {mtgscribe.FALLBACK_PATH}")


def _trim(event: dict) -> dict:
    """Keep only the fields ``mtgscribe._parse_event`` reads, so the snapshot stays small and stable."""
    return {
        "title": event.get("title", ""),
        "tags": [{"slug": tag.get("slug", "")} for tag in event.get("tags", [])],
        "utc_start_date": event["utc_start_date"],
        "utc_end_date": event["utc_end_date"],
        "start_date": event["start_date"],
        "end_date": event["end_date"],
    }


if __name__ == "__main__":
    main()
