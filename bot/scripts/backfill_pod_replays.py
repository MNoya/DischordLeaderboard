"""Backfill 17lands replays for every participant of a pod draft event.

Use this when the bot didn't capture replays at match-report time (e.g. mid-event crash).
Run promptly — 17lands user_game_history only exposes the last 100 matches, so games age out
as players keep playing.

    DATABASE_URL=... python -m bot.scripts.backfill_pod_replays <event_id>
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from bot.database import SessionLocal
from bot.models import PodDraftParticipant, Player
from bot.services.pod_replays import fetch_and_persist_replays_for_player
from bot.services.seventeenlands import SeventeenLandsClient


async def main(event_id: str) -> int:
    with SessionLocal() as session:
        rows = session.execute(
            select(
                PodDraftParticipant.player_id,
                PodDraftParticipant.draftmancer_name,
                PodDraftParticipant.display_name,
                Player.seventeenlands_token,
            )
            .join(Player, Player.id == PodDraftParticipant.player_id)
            .where(PodDraftParticipant.event_id == event_id)
        ).all()

    if not rows:
        print(f"no participants for event {event_id}", file=sys.stderr)
        return 1

    client = SeventeenLandsClient()
    total = 0
    for player_id, seat_name, display, token in rows:
        seat = seat_name or display
        if not token:
            print(f"  {seat}: no 17lands token, skipping")
            continue
        n = await fetch_and_persist_replays_for_player(client, event_id, player_id, seat, token)
        print(f"  {seat}: {n} replay rows touched")
        total += n

    print(f"\ndone: {total} rows touched across {len(rows)} participants")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m bot.scripts.backfill_pod_replays <event_id>", file=sys.stderr)
        sys.exit(64)
    sys.exit(asyncio.run(main(sys.argv[1])))
