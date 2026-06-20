"""Resolve the date-derived active set to a seeded DB row.

``active_set_code`` is pure date math against ``ALL_SETS``; the row it names only exists once
``seed_sets`` has run against the database. Seeding stays manual, so when a freshly rotated set
hasn't been seeded yet this falls back to the latest prior set that does have a row — the board
holds on the previous set instead of going blank — and warns so the owner knows to seed.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.models import MagicSet
from bot.sets import ALL_SETS, active_set_code

log = logging.getLogger(__name__)


def resolve_active_set(session: Session) -> MagicSet | None:
    code = active_set_code()
    magic_set = session.execute(
        select(MagicSet).where(MagicSet.code == code)
    ).scalar_one_or_none()
    if magic_set is not None:
        return magic_set

    fallback = _latest_seeded_prior_set(session, code)
    if fallback is not None:
        log.warning(f"active set {code} not seeded; holding leaderboard on {fallback.code} — run seed_sets")
    else:
        log.warning(f"active set {code} not seeded and no prior set seeded; leaderboard has no set")
    return fallback


def _latest_seeded_prior_set(session: Session, code: str) -> MagicSet | None:
    active_seed: object | None = None
    for seed in ALL_SETS:
        if seed.code == code:
            active_seed = seed
            break
    if active_seed is None:
        return None

    prior_codes = [s.code for s in ALL_SETS if s.start_date < active_seed.start_date]
    if not prior_codes:
        return None
    return session.execute(
        select(MagicSet)
        .where(MagicSet.code.in_(prior_codes))
        .order_by(MagicSet.start_date.desc())
    ).scalars().first()
