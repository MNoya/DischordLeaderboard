"""Append-only structured event log for user interactions with the bot.

One JSON object per line at ``logs/events.jsonl`` (relative to the repo root).
Used to spot UX issues — what commands users invoke, what branches they hit,
where they get stuck. Never store secrets here (tokens, raw DM content).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
EVENTS_FILE = LOG_DIR / "events.jsonl"


def event(type: str, **fields: Any) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": type,
        **fields,
    }
    try:
        with EVENTS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except OSError as e:
        logger.warning(f"failed to write audit event {type!r}: {e}")
