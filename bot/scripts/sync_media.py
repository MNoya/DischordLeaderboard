"""Run a media sync against DATABASE_URL — the same code path as the bot's daily tick / !sync-media.

The podcast feed always syncs; videos + Shorts only when YOUTUBE_API_KEY is set. That key lives in
``frontend/.env`` (not the bot's env), so export it explicitly or the table repopulates podcast-only:

    DATABASE_URL=postgresql://postgres:devpw@localhost:5433/dischord \\
    YOUTUBE_API_KEY=$(grep -h YOUTUBE_API_KEY frontend/.env | cut -d= -f2- | tr -d '"') \\
    .venv/bin/python -m bot.scripts.sync_media

Safe to run repeatedly — the feeds stay the source of truth and the table is rebuilt each run.
"""
from __future__ import annotations

import logging

from bot.config import settings
from bot.database import SessionLocal
from bot.services.media_sync import sync_media

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not settings.youtube_api_key:
        log.warning("YOUTUBE_API_KEY unset — podcast-only sync (no videos or Shorts). Export it to pull YouTube.")
    with SessionLocal() as session:
        result = sync_media(session)
    log.info(f"sync complete: {result}")


if __name__ == "__main__":
    main()
