"""One-shot import of historical SOS pod-draft results into pod_draft_events + pod_draft_participants.

Idempotent: skips events that already exist by (name, event_date).
For names without a matching Player, creates a lightweight Player (no 17lands token) with a
`historical-{slug}` discord_id.

Run with:
    DATABASE_URL=... python -m bot.scripts.import_pod_draft_history
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone

from sqlalchemy import select

from bot.database import SessionLocal
from bot.models import MagicSet, Player, PodDraftEvent, PodDraftParticipant
from bot.services.pod_drafts import player_for_name
from bot.slug import disambiguate_slug, slugify


logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("import_pod_draft_history")


HISTORICAL_DISCORD_IDS: dict[str, dict] = {
    "Doctormagi#47646": {"discord_id": "134089951590481921"},
    "maimslap#64991":   {"discord_id": "270233342539071489"},
    "eltonium#54419":   {"discord_id": "89227157603110912", "display_name": "elton", "slug": "elton"},
    "Aristeo#15552":    {"discord_id": "803309103983362069"},
}


EVENTS = [
    {
        "name": "Pod Draft #1",
        "event_date": date(2026, 4, 29),
        "set_code": "SOS",
        "participants": [
            ("springbok7", "springbok7#14100", "3-0", 1),
            ("Doctormagi", "Doctormagi#47646", "2-1", 2),
            ("Oophies", "Oophies#11360", "2-1", 3),
            ("eltonium", "eltonium#54419", "1-2", 4),
            ("Aristeo", "Aristeo#15552", "2-1", 5),
            ("RepTuneRepeat", "RepTuneRepeat#3878", "1-2", 6),
            ("jonnietang", "jonnietang#11502", "1-2", 7),
            ("Bacchus", "Bacchus#23673", "0-3", 8),
        ],
    },
    {
        "name": "Pod Draft #2",
        "event_date": date(2026, 5, 6),
        "set_code": "SOS",
        "participants": [
            ("queueknee", "dankesean#67393", "3-0", 1),
            ("Bacchus", "Bacchus#23673", "2-1", 2),
            ("Aristeo", "Aristeo#15552", "2-1", 3),
            ("Chonce", "DongSlinger420#4573", "2-1", 4),
            ("Doctormagi", "Doctormagi#47646", "1-2", 5),
            ("whalematron", None, "1-2", 6),
            ("NiamhIsTired", None, "1-2", 7),
            ("Oophies", "Oophies#11360", "0-3", 8),
        ],
    },
    {
        "name": "Pod Draft #3",
        "event_date": date(2026, 5, 13),
        "set_code": "SOS",
        "participants": [
            ("Elfandor", None, "3-0", 1),
            ("flutterdev", "fullerene60#49190", "2-1", 2),
            ("whalematron", None, "2-1", 3),
            ("Waveofshadow", None, "2-1", 4),
            ("Noya", None, "1-2", 5),
            ("Bacchus", "Bacchus#23673", "1-2", 6),
            ("NiamhIsTired", None, "1-2", 7),
            ("C.Elegans", "maimslap#64991", "0-3", 8),
        ],
    },
]


def _resolve_or_create_player(session, taken_slugs, display_name, arena_name):
    """Find an existing Player by arena_name / mapped discord_id / normalized display_name, else
    create a lightweight one."""
    if arena_name:
        player = player_for_name(session, arena_name)
        if player is not None:
            if not player.arena_name:
                player.arena_name = arena_name
            return player

    entry = HISTORICAL_DISCORD_IDS.get(arena_name) if arena_name else None
    if entry is not None:
        existing = session.execute(
            select(Player).where(Player.discord_id == entry["discord_id"])
        ).scalar_one_or_none()
        if existing is not None:
            if arena_name and not existing.arena_name:
                existing.arena_name = arena_name
            return existing
        new_display = entry.get("display_name", display_name)
        new_slug = entry.get("slug") or disambiguate_slug(slugify(new_display), taken_slugs)
        taken_slugs.add(new_slug)
        player = Player(
            slug=new_slug,
            discord_id=entry["discord_id"],
            display_name=new_display,
            arena_name=arena_name,
            active=True,
        )
        session.add(player)
        session.flush()
        log.info(
            f"created identified player: {new_display} (slug={new_slug}, arena_name={arena_name}, "
            f"discord_id={entry['discord_id']})"
        )
        return player

    player = player_for_name(session, display_name)
    if player is not None:
        if arena_name and not player.arena_name:
            player.arena_name = arena_name
        return player

    slug = disambiguate_slug(slugify(display_name), taken_slugs)
    taken_slugs.add(slug)
    player = Player(
        slug=slug,
        discord_id=f"historical-{slug}",
        display_name=display_name,
        arena_name=arena_name,
        active=True,
    )
    session.add(player)
    session.flush()
    log.info(f"created lightweight player: {display_name} (slug={slug}, arena_name={arena_name})")
    return player


def main() -> None:
    with SessionLocal() as session:
        taken_slugs = set(session.execute(select(Player.slug)).scalars().all())
        added_events = 0
        skipped_events = 0
        for ev in EVENTS:
            existing = session.execute(
                select(PodDraftEvent).where(
                    PodDraftEvent.name == ev["name"],
                    PodDraftEvent.event_date == ev["event_date"],
                )
            ).scalar_one_or_none()
            if existing is not None:
                log.info(f"skipping {ev['name']} ({ev['event_date']}) — already exists")
                skipped_events += 1
                continue
            set_id = session.execute(
                select(MagicSet.id).where(MagicSet.code == ev["set_code"])
            ).scalar_one_or_none()
            if set_id is None:
                log.error(f"no MagicSet row for code={ev['set_code']}; skipping {ev['name']}")
                continue
            event_time = datetime.combine(ev["event_date"], time(hour=20), tzinfo=timezone.utc)
            event = PodDraftEvent(
                name=ev["name"],
                event_date=ev["event_date"],
                event_time=event_time,
                set_id=set_id,
                set_code=ev["set_code"],
                format_label=None,
                draftmancer_session=f"LLU-SOS-historical-{ev['event_date'].isoformat()}",
                discord_thread_id="0",
                sesh_message_id="0",
                socket_status="complete",
                current_round=3,
            )
            session.add(event)
            session.flush()

            for display_name, arena_name, record, placement in ev["participants"]:
                player = _resolve_or_create_player(session, taken_slugs, display_name, arena_name)
                participant = PodDraftParticipant(
                    event_id=event.id,
                    player_id=player.id,
                    display_name=display_name,
                    draftmancer_name=arena_name or display_name,
                    placement=placement,
                    record=record,
                    eliminated_round=None if placement == 1 else 3,
                )
                session.add(participant)
            log.info(f"imported {ev['name']}: {len(ev['participants'])} participants")
            added_events += 1
        session.commit()
    log.info(f"done. added={added_events} skipped={skipped_events}")


if __name__ == "__main__":
    main()
