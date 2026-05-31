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
        for entry in PLAYERS:
            display_name = entry[0]
            token = entry[1]
            real_discord_id = entry[2] if len(entry) >= 3 else None
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
                discord_id=real_discord_id or str(800_000_000_000_000_000 + added),
                display_name=display_name,
                seventeenlands_token=token,
                active=True,
            ))
            added += 1
        session.commit()
    log.info(f"done. added={added} skipped={skipped}")


if __name__ == "__main__":
    main()
