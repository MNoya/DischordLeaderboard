"""Seed Magic sets into the leaderboard DB.

Idempotent: re-running leaves existing rows untouched. Safe to run against
any environment (local Postgres or Supabase) — pick the target via DATABASE_URL.

    DATABASE_URL=postgresql://... python -m bot.scripts.seed_sets

Set metadata lives in ``bot/sets.py`` — edit there, not here.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.database import SessionLocal
from bot.models import MagicSet
from bot.sets import ALL_SETS, SetSeed


logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("seed_sets")


def upsert_set(session: Session, seed: SetSeed) -> None:
    existing = session.execute(
        select(MagicSet).where(MagicSet.code == seed.code)
    ).scalar_one_or_none()
    if existing is not None:
        if (
            existing.end_date != seed.end_date
            or existing.start_date != seed.start_date
            or existing.name != seed.name
        ):
            existing.end_date = seed.end_date
            existing.start_date = seed.start_date
            existing.name = seed.name
            log.info("updating set %s (metadata refreshed)", seed.code)
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
