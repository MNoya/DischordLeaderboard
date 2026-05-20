"""Update deck metadata for a pod draft participant.

    DATABASE_URL=... python -m bot.scripts.update_pod_participant \\
        --event "SOS Pod Draft #2" \\
        --player Oophies \\
        --colors WB \\
        --screenshot-url "https://..." \\
        --caption "yeah this is probably my best deck that will ever 0-3"

Event is matched case-insensitively by name substring (e.g. "Pod Draft #2").
Player is matched case-insensitively by display_name.
Only the flags you pass are written; omitted flags leave existing values unchanged.
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from bot.database import SessionLocal
from bot.models import PodDraftEvent, PodDraftParticipant


def main(event_query: str, player_name: str, colors: str | None, screenshot_url: str | None, caption: str | None) -> None:
    with SessionLocal() as session:
        events = session.execute(
            select(PodDraftEvent).where(PodDraftEvent.name.ilike(f"%{event_query}%"))
        ).scalars().all()
        if not events:
            raise SystemExit(f"no event matching {event_query!r}")
        if len(events) > 1:
            raise SystemExit(f"ambiguous — matched {len(events)} events: " + ", ".join(e.name for e in events))
        event = events[0]

        participant = session.execute(
            select(PodDraftParticipant).where(
                PodDraftParticipant.event_id == event.id,
                PodDraftParticipant.display_name.ilike(player_name),
            )
        ).scalar_one_or_none()
        if participant is None:
            raise SystemExit(f"no participant {player_name!r} in {event.name!r}")

        print(f"event:      {event.name}")
        print(f"player:     {participant.display_name}")

        if colors is not None:
            print(f"colors:     {participant.deck_colors!r} → {colors!r}")
            participant.deck_colors = colors
        if screenshot_url is not None:
            print(f"screenshot: {participant.deck_screenshot_url!r} → {screenshot_url!r}")
            participant.deck_screenshot_url = screenshot_url
        if caption is not None:
            print(f"caption:    {participant.deck_screenshot_caption!r} → {caption!r}")
            participant.deck_screenshot_caption = caption

        if colors is None and screenshot_url is None and caption is None:
            raise SystemExit("nothing to update — pass at least one of --colors, --screenshot-url, --caption")

        session.commit()
        print("updated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--event", required=True, help="event name substring, e.g. 'Pod Draft #2'")
    parser.add_argument("--player", required=True, help="display_name (case-insensitive)")
    parser.add_argument("--colors", default=None)
    parser.add_argument("--screenshot-url", dest="screenshot_url", default=None)
    parser.add_argument("--caption", default=None)
    args = parser.parse_args()
    main(args.event, args.player, args.colors, args.screenshot_url, args.caption)
