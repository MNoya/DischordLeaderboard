"""Seed local-dev player rows from ``legacy/user_ids.py``.

Idempotent: re-running leaves existing rows untouched. Intended for local
testing only — production players sign themselves up via ``/join``. Pair this
with ``refresh_stats --cache`` to fully repopulate a freshly-wiped local DB
without hitting the 17lands API.

    DATABASE_URL=postgresql://... python -m bot.scripts.seed_local_players
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from bot.database import SessionLocal
from bot.models import Player
from bot.slug import disambiguate_slug, slugify

try:
    from legacy.user_ids import PLAYERS
except ImportError as e:
    raise SystemExit(
        "legacy/user_ids.py is required (gitignored); see legacy/ for the format"
    ) from e


logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("seed_local_players")


def main() -> None:
    added = 0
    skipped = 0
    with SessionLocal() as session:
        taken_slugs = set(session.execute(select(Player.slug)).scalars().all())
        for display_name, token in PLAYERS:
            existing = session.execute(
                select(Player).where(Player.seventeenlands_token == token)
            ).scalar_one_or_none()
            if existing is not None:
                skipped += 1
                continue
            slug = disambiguate_slug(slugify(display_name), taken_slugs)
            taken_slugs.add(slug)
            session.add(Player(
                slug=slug,
                display_name=display_name,
                seventeenlands_token=token,
                seventeenlands_url=f"https://www.17lands.com/user_history/{token}",
                active=True,
            ))
            added += 1
        session.commit()
    log.info("done. added=%d skipped=%d", added, skipped)


if __name__ == "__main__":
    main()
