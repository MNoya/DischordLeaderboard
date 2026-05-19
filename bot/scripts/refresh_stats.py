"""Full-history refresh of PlayerStats from 17lands for all active players.

    DATABASE_URL=postgresql://... python -m bot.scripts.refresh_stats [--cache]
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from bot.database import SessionLocal
from bot.services.refresh import refresh_active_players_all_sets
from bot.services.seventeenlands import SeventeenLandsClient


REPO_ROOT = Path(__file__).resolve().parents[2]

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("refresh")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache",
        nargs="?",
        const=str(REPO_ROOT / "cache" / "17lands"),
        default=None,
        help="cache 17lands responses to this dir (default: cache/17lands/ if flag is bare)",
    )
    args = parser.parse_args()

    client = SeventeenLandsClient(cache_dir=args.cache)
    if args.cache:
        log.info(f"17lands cache: {args.cache}")
    with SessionLocal() as session:
        log.info("refreshing all registered sets")
        summary = refresh_active_players_all_sets(session, client)

    log.info(f"done. updated={summary['updated']} invalidated={summary['invalidated']} errors={summary['errors']}")


if __name__ == "__main__":
    main()
