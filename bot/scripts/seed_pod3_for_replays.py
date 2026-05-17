"""One-off seed for end-to-end replays validation against the real May 14 Pod #3 data."""
from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine, select, text

from bot.database import SessionLocal
from bot.models import (
    PodDraftEvent,
    PodDraftMatch,
    PodDraftParticipant,
    Player,
)
from bot.services.pod_replays import fetch_and_persist_replays_for_player
from bot.services.seventeenlands import SeventeenLandsClient
from bot.slug import slugify


_EVENT_NAME = "SOS Pod Draft #3"
_EVENT_DATE = date(2026, 5, 14)
_EVENT_TIME = datetime(2026, 5, 14, 0, 8, 20, tzinfo=timezone.utc)


def _ensure_wave_player(session) -> Player:
    wave = session.execute(
        select(Player).where(Player.display_name == "WaveofShadow")
    ).scalar_one_or_none()
    if wave is not None and wave.seventeenlands_token:
        return wave

    prod_url = os.environ.get("SUPABASE_DB_URL")
    if not prod_url:
        raise RuntimeError("SUPABASE_DB_URL is required to pull WaveofShadow token from prod")
    prod_engine = create_engine(prod_url)
    with prod_engine.connect() as conn:
        row = conn.execute(text(
            "SELECT discord_id, seventeenlands_token FROM players WHERE display_name = 'WaveofShadow'"
        )).first()
    if row is None:
        raise RuntimeError("WaveofShadow not found in prod")
    discord_id, token = row

    if wave is None:
        wave = Player(
            id=str(uuid4()),
            slug=slugify("WaveofShadow"),
            discord_id=discord_id,
            display_name="WaveofShadow",
            seventeenlands_token=token,
            active=True,
        )
        session.add(wave)
    else:
        wave.seventeenlands_token = token
    session.flush()
    return wave


def main() -> None:
    with SessionLocal() as session:
        noya = session.execute(select(Player).where(Player.display_name == "Noya")).scalar_one()
        wave = _ensure_wave_player(session)

        existing = session.execute(
            select(PodDraftEvent).where(PodDraftEvent.name == _EVENT_NAME)
        ).scalar_one_or_none()
        if existing is not None:
            session.execute(text("DELETE FROM pod_draft_replays WHERE event_id = :eid"), {"eid": existing.id})
            session.execute(text("DELETE FROM pod_draft_matches WHERE event_id = :eid"), {"eid": existing.id})
            session.execute(text("DELETE FROM pod_draft_participants WHERE event_id = :eid"), {"eid": existing.id})
            session.delete(existing)
            session.flush()

        event = PodDraftEvent(
            id=str(uuid4()),
            event_date=_EVENT_DATE,
            event_time=_EVENT_TIME,
            set_id=None,
            set_code="SOS",
            format_label=None,
            name=_EVENT_NAME,
            draftmancer_session="LLU-SOS-3",
            draftmancer_url="https://draftmancer.com/?session=LLU-SOS-3",
            discord_thread_id="0",
            sesh_message_id="0",
            socket_status="complete",
        )
        session.add(event)
        session.flush()

        for player, seat_name in ((noya, "Noya#08011"), (wave, "Waveofshadow#17843")):
            session.add(PodDraftParticipant(
                id=str(uuid4()),
                event_id=event.id,
                player_id=player.id,
                display_name=seat_name,
                draftmancer_name=seat_name,
            ))

        def _add_match(round_num, a, b, winner, score, ts):
            session.add(PodDraftMatch(
                id=str(uuid4()),
                event_id=event.id,
                round=round_num,
                pairing_index=0,
                player_a_name=a,
                player_b_name=b,
                winner_name=winner,
                score=score,
                reported_at=ts,
            ))

        _add_match(1, "Noya#08011", "NiamhIsTired#12791", "NiamhIsTired#12791", "2-1",
                   datetime(2026, 5, 14, 1, 5, tzinfo=timezone.utc))
        _add_match(2, "Noya#08011", "Bacchus#23673", "Noya#08011", "2-1",
                   datetime(2026, 5, 14, 1, 30, tzinfo=timezone.utc))
        _add_match(3, "Noya#08011", "Waveofshadow#17843", "Waveofshadow#17843", "2-1",
                   datetime(2026, 5, 14, 2, 5, tzinfo=timezone.utc))

        _add_match(1, "Waveofshadow#17843", "Elfandor#43425", "Elfandor#43425", "2-1",
                   datetime(2026, 5, 14, 1, 35, tzinfo=timezone.utc))
        _add_match(2, "Waveofshadow#17843", "maimslap#64991", "Waveofshadow#17843", "2-0",
                   datetime(2026, 5, 14, 1, 40, tzinfo=timezone.utc))
        _add_match(3, "Waveofshadow#17843", "Noya#08011", "Waveofshadow#17843", "2-1",
                   datetime(2026, 5, 14, 2, 5, tzinfo=timezone.utc))

        session.commit()
        event_id = event.id
        noya_id, noya_token = noya.id, noya.seventeenlands_token
        wave_id, wave_token = wave.id, wave.seventeenlands_token

    async def _populate():
        client = SeventeenLandsClient()
        n = await fetch_and_persist_replays_for_player(client, event_id, noya_id, "Noya#08011", noya_token)
        print(f"Noya: {n} replay rows touched")
        n = await fetch_and_persist_replays_for_player(client, event_id, wave_id, "Waveofshadow#17843", wave_token)
        print(f"Wave: {n} replay rows touched")
    asyncio.run(_populate())

    with SessionLocal() as session:
        rows = session.execute(text("""
            SELECT player_display_name, game_time, won, turns, inferred_round, link
            FROM public_pod_draft_replays
            WHERE event_id = :eid
            ORDER BY player_display_name, game_time
        """), {"eid": event_id}).fetchall()
        print()
        print(f"=== Persisted {len(rows)} replay rows ===")
        for r in rows:
            won = "W" if r.won else "L"
            ir = f"R{r.inferred_round}" if r.inferred_round else "—"
            print(f"  {r.player_display_name:<14}  {r.game_time}  {won}  t={r.turns:>2}  {ir}  …{r.link[-12:]}")


if __name__ == "__main__":
    main()
