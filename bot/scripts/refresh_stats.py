"""Refresh PlayerStats from 17lands for all active players.

    DATABASE_URL=postgresql://... python -m bot.scripts.refresh_stats [--set-code ECL]
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from sqlalchemy import select

from bot.database import SessionLocal
from bot.models import MagicSet
from bot.services.refresh import refresh_active_players
from bot.services.seventeenlands import SeventeenLandsClient
from bot.sets import ACTIVE_SET_CODE


REPO_ROOT = Path(__file__).resolve().parents[2]

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("refresh")


def _resolve_set(session, set_code: str | None) -> MagicSet:
    code = set_code or ACTIVE_SET_CODE
    s = session.execute(
        select(MagicSet).where(MagicSet.code == code)
    ).scalar_one_or_none()
    if s is None:
        raise SystemExit(f"no set with code {code!r} (pass --set-code or update bot/sets.py)")
    return s


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set-code", help="set code to refresh; defaults to ACTIVE_SET_CODE in bot/sets.py")
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
        log.info("17lands cache: %s", args.cache)
    with SessionLocal() as session:
        magic_set = _resolve_set(session, args.set_code)
        log.info("refreshing set %s (%s)", magic_set.code, magic_set.name)
        summary = refresh_active_players(session, client, magic_set)

    log.info(
        "done. updated=%d invalidated=%d errors=%d",
        summary["updated"], summary["invalidated"], summary["errors"],
    )


if __name__ == "__main__":
    main()
