"""Recompute pre-computed scores from existing data — no 17lands fetch.

Use this when the scoring formula, QueueGroup config, or archetype-bucketing
rules change and you want new scores without re-hitting 17lands.

    DATABASE_URL=postgresql://... python -m bot.scripts.recompute_scores \\
        [--set-code SOS] [--scope set|archetype|both]

Default scope is `both`: recomputes player_set_scores from PlayerStats AND
player_archetype_scores from DraftEvent (including MULTICOLOR rows under the
multi-membership rule). Use `--scope archetype` to refresh only the per-color
buckets (e.g. after changing the archetype-keys rule without touching scoring).
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
from bot.models import MagicSet, PlayerStats  # noqa: E402
from bot.services.refresh import (  # noqa: E402
    recompute_player_archetype_scores,
    recompute_player_set_score,
)


logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("recompute")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set-code", help="restrict to one set; default = all sets")
    parser.add_argument(
        "--scope",
        choices=("set", "archetype", "both"),
        default="both",
        help="which scores to recompute (default: both)",
    )
    args = parser.parse_args()

    do_set = args.scope in ("set", "both")
    do_arch = args.scope in ("archetype", "both")

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
                if do_set:
                    recompute_player_set_score(session, player_id, magic_set.id)
                if do_arch:
                    recompute_player_archetype_scores(session, player_id, magic_set.id)
                total += 1
            log.info(
                "set %s: %d players recomputed (scope=%s)",
                magic_set.code, len(player_ids), args.scope,
            )
        session.commit()

    log.info("done. %d (player, set) iterations completed", total)


if __name__ == "__main__":
    main()
