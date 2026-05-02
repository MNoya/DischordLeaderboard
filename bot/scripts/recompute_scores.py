"""Recompute PlayerSetScore from existing PlayerStats — no 17lands fetch.

Use this when the scoring formula or QueueGroup config changes and you want
new scores without re-hitting 17lands. Affects every (player, set) that has
PlayerStats rows.

    DATABASE_URL=postgresql://... python -m bot.scripts.recompute_scores [--set-code SOS]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import select

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bot.database import SessionLocal  # noqa: E402
from bot.models import MagicSet, Player, PlayerStats  # noqa: E402
from bot.services.refresh import recompute_player_set_score  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("recompute")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set-code", help="restrict to one set; default = all sets")
    args = parser.parse_args()

    with SessionLocal() as session:
        sets_q = select(MagicSet)
        if args.set_code:
            sets_q = sets_q.where(MagicSet.code == args.set_code)
        sets = session.execute(sets_q).scalars().all()
        if not sets:
            raise SystemExit("no matching sets found")

        total = 0
        for magic_set in sets:
            player_ids = session.execute(
                select(PlayerStats.player_id)
                .where(PlayerStats.set_id == magic_set.id)
                .distinct()
            ).scalars().all()
            for player_id in player_ids:
                recompute_player_set_score(session, player_id, magic_set.id)
                total += 1
            log.info("set %s: %d players recomputed", magic_set.code, len(player_ids))
        session.commit()

    log.info("done. %d (player, set) scores recomputed", total)


if __name__ == "__main__":
    main()
