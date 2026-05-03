"""Seed Magic sets into the leaderboard DB.

Idempotent: re-running leaves existing rows untouched. Safe to run against
any environment (local Postgres or Supabase) — pick the target via DATABASE_URL.

    DATABASE_URL=postgresql://... python -m bot.scripts.seed_sets

Set metadata lives in ``bot/sets.py`` — edit there, not here.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bot.database import SessionLocal  # noqa: E402
from bot.models import MagicSet  # noqa: E402
from bot.sets import ALL_SETS, SetSeed  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("seed_sets")


def upsert_set(session: Session, seed: SetSeed) -> None:
    existing = session.execute(
        select(MagicSet).where(MagicSet.code == seed.code)
    ).scalar_one_or_none()
    if existing is not None:
        # update mutable metadata in case end_date / name shifted between releases
        if existing.end_date != seed.end_date or existing.name != seed.name:
            existing.end_date = seed.end_date
            existing.name = seed.name
            log.info("updating set %s (name/end_date refreshed)", seed.code)
        else:
            log.info("set %s exists, leaving as-is", seed.code)
        return
    session.add(MagicSet(
        code=seed.code,
        name=seed.name,
        start_date=seed.start_date,
        end_date=seed.end_date,
    ))
    log.info("seeding set %s (%s)", seed.code, seed.name)


def main() -> None:
    with SessionLocal() as session:
        for seed in ALL_SETS:
            upsert_set(session, seed)
        session.commit()
    log.info("done.")


if __name__ == "__main__":
    main()
