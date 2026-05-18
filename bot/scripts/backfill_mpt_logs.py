"""Reconstruct a Draftmancer draftLog payload from pod_draft_events.draft_log_gz and submit each
seat to MagicProTools, stashing URLs on pod_draft_participants.

Use this once to backfill the May 18 pod that completed before MPT_API_KEY was set in prod.

    DATABASE_URL=... MPT_API_KEY=... python -m bot.scripts.backfill_mpt_logs <event_id> [--force]

`--force` resubmits and overwrites existing draft_log_url values.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import sys

from sqlalchemy import select

from bot.database import SessionLocal
from bot.models import PodDraftEvent, PodDraftParticipant
from bot.scripts.draftmancer_log import PASS_DIRS
from bot.services.magicprotools import submit_to_api


def reconstruct_log(compact: dict) -> dict:
    """Inverse of build_compact: rebuild the original Draftmancer log shape (with booster contents
    per pick) by simulating the pack passing."""
    cards_list = compact["cards"]
    id_by_idx = [c["id"] for c in cards_list]
    n_seats = len(compact["seats"])
    carddata = {c["id"]: {"name": c["n"], "set": c.get("s")} for c in cards_list}

    users: dict[str, dict] = {}
    for i, name in enumerate(compact["seats"]):
        users[f"seat_{i}"] = {"userName": name, "picks": []}

    packs = compact["packs"]
    picks = compact["picks"]

    for pack_num in range(3):
        booster_at = [list(packs[seat + pack_num * n_seats]) for seat in range(n_seats)]
        direction = PASS_DIRS[pack_num]
        pack_size = len(booster_at[0])
        for pick_num in range(pack_size):
            for seat in range(n_seats):
                pick_idx = picks[seat][pack_num][pick_num]
                booster_card_ids = [id_by_idx[c] for c in booster_at[seat]]
                users[f"seat_{seat}"]["picks"].append({
                    "packNum": pack_num,
                    "pickNum": pick_num,
                    "booster": booster_card_ids,
                    "pick": [pick_idx],
                })
            for seat in range(n_seats):
                pick_idx = picks[seat][pack_num][pick_num]
                booster_at[seat].pop(pick_idx)
            booster_at = [booster_at[(seat - direction) % n_seats] for seat in range(n_seats)]

    return {
        "sessionID": compact.get("sid"),
        "time": compact.get("t"),
        "setRestriction": [compact["set"]] if compact.get("set") else [],
        "carddata": carddata,
        "users": users,
    }


async def main(event_id: str, force: bool = False) -> int:
    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is None or event.draft_log_gz is None:
            print(f"event {event_id} has no draft_log_gz", file=sys.stderr)
            return 1
        compact = json.loads(gzip.decompress(event.draft_log_gz).decode("utf-8"))
        participants = session.execute(
            select(PodDraftParticipant).where(PodDraftParticipant.event_id == event_id)
        ).scalars().all()
        by_name = {p.draftmancer_name: p for p in participants if p.draftmancer_name}

    log_payload = reconstruct_log(compact)
    print(f"reconstructed log: {len(log_payload['users'])} seats, {len(log_payload['carddata'])} cards")

    submitted = 0
    skipped = 0
    failed = 0
    for user_id, user_data in log_payload["users"].items():
        name = user_data["userName"]
        participant = by_name.get(name)
        if participant is None:
            print(f"  {name}: no matching participant row, skipping")
            skipped += 1
            continue
        if participant.draft_log_url and not force:
            print(f"  {name}: already has draft_log_url, skipping")
            skipped += 1
            continue
        url = await submit_to_api(user_id, log_payload)
        if not url:
            print(f"  {name}: MPT submit failed")
            failed += 1
            continue
        with SessionLocal() as session:
            row = session.get(PodDraftParticipant, participant.id)
            row.draft_log_url = url
            session.commit()
        print(f"  {name}: {url}")
        submitted += 1

    print(f"\ndone: submitted={submitted} skipped={skipped} failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    args = sys.argv[1:]
    force = "--force" in args
    args = [a for a in args if a != "--force"]
    if len(args) != 1:
        print("usage: python -m bot.scripts.backfill_mpt_logs <event_id> [--force]", file=sys.stderr)
        sys.exit(64)
    sys.exit(asyncio.run(main(args[0], force=force)))
