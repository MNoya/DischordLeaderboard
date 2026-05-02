"""Seed initial sets and players into the leaderboard DB.

Idempotent: re-running leaves existing rows untouched.

Run from the repo root with DATABASE_URL set:

    DATABASE_URL=postgresql://... python -m bot.scripts.seed_initial_players
"""
from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bot.database import SessionLocal  # noqa: E402
from bot.models import MagicSet, Player  # noqa: E402
from legacy.user_ids import PLAYERS  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("seed")


# Edit set names here if the placeholders aren't right — codes and dates are
# the source of truth, names are display-only
SETS = [
    {
        "code": "ECL",
        "name": "ECL",
        "start_date": date(2026, 1, 20),
        "end_date": date(2026, 3, 3),
    },
    {
        "code": "SOS",
        "name": "SOS",
        "start_date": date(2026, 4, 21),
        "end_date": date(2026, 6, 22),
    },
]


def upsert_set(session: Session, code: str, name: str, start_date: date,
               end_date: date | None) -> MagicSet:
    existing = session.execute(select(MagicSet).where(MagicSet.code == code)).scalar_one_or_none()
    if existing is not None:
        log.info("set %s exists, leaving as-is", code)
        return existing
    s = MagicSet(code=code, name=name, start_date=start_date, end_date=end_date)
    session.add(s)
    log.info("seeding set %s", code)
    return s


def upsert_player(session: Session, display_name: str, token: str) -> Player:
    existing = session.execute(
        select(Player).where(Player.seventeenlands_token == token)
    ).scalar_one_or_none()
    if existing is not None:
        log.info("player %r exists, leaving as-is", display_name)
        return existing
    p = Player(
        display_name=display_name,
        seventeenlands_token=token,
        seventeenlands_url=f"https://www.17lands.com/user_history/{token}",
        # discord_id / discord_username left NULL — filled in when the player
        # runs /join from Discord and we match them by 17lands token
        active=True,
    )
    session.add(p)
    log.info("seeding player %r", display_name)
    return p


def main() -> None:
    with SessionLocal() as session:
        for set_data in SETS:
            upsert_set(session, **set_data)
        for display_name, token in PLAYERS:
            upsert_player(session, display_name, token)
        session.commit()
    log.info("done.")


if __name__ == "__main__":
    main()
