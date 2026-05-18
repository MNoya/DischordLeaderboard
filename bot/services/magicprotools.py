"""MagicProTools draft-log integration.

Ported from Amelas/DraftBot (helpers/magicprotools_helper.py). Trimmed to the two pieces this
project needs: the MTGO-format text conversion (pure function) and the API submit. The Amelas
DigitalOcean Spaces fallback path is deliberately not ported — the spec defers it.

Returns `None` on any failure so callers can degrade gracefully (omit a player's link button
from the announcement instead of breaking the whole post).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from bot.config import settings


log = logging.getLogger(__name__)

_MPT_ENDPOINT = "https://magicprotools.com/api/draft/add"
_MPT_REFERER = "https://draftmancer.com"
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10.0)


def convert_to_magicprotools_format(draft_log: dict[str, Any], user_id: str) -> str:
    """Render a Draftmancer draftLog payload as MTGO-format text for a specific seat.

    `user_id` is the Draftmancer user ID whose perspective to render. `--> ` marks both that seat
    in the player list and that seat's picked card in each pack listing.
    """
    output: list[str] = []

    session_id = draft_log["sessionID"]
    timestamp_ms = draft_log["time"]
    output.append(f"Event #: {session_id}_{timestamp_ms}")
    formatted_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )
    output.append(f"Time: {formatted_time}")
    output.append("Players:")

    for player_id, user_data in draft_log["users"].items():
        prefix = "--> " if player_id == user_id else "    "
        output.append(f"{prefix}{user_data['userName']}")
    output.append("")

    set_restriction = draft_log.get("setRestriction") or []
    carddata = draft_log["carddata"]
    if (
        len(set_restriction) == 1
        and sum(1 for c in carddata.values() if c.get("set") == set_restriction[0])
        >= 0.5 * len(carddata)
    ):
        booster_header = f"------ {set_restriction[0].upper()} ------"
    else:
        booster_header = "------ Cube ------"

    picks = draft_log["users"][user_id]["picks"]
    picks_by_pack: dict[int, list[dict]] = {}
    for pick in picks:
        picks_by_pack.setdefault(pick["packNum"], []).append(pick)
    for pack_num in picks_by_pack:
        picks_by_pack[pack_num].sort(key=lambda p: p["pickNum"])

    for pack_num in sorted(picks_by_pack):
        output.append(booster_header)
        output.append("")
        for pick in picks_by_pack[pack_num]:
            output.append(f"Pack {pick['packNum'] + 1} pick {pick['pickNum'] + 1}:")
            picked_indices = set(pick["pick"])
            for idx, card_id in enumerate(pick["booster"]):
                card = carddata[card_id]
                card_name = card["name"]
                if "back" in card:
                    card_name = f"{card_name} // {card['back']['name']}"
                marker = "--> " if idx in picked_indices else "    "
                output.append(f"{marker}{card_name}")
            output.append("")

    return "\n".join(output)


async def submit_to_api(user_id: str, draft_log: dict[str, Any]) -> str | None:
    """POST a seat's draft to MagicProTools. Returns the viewer URL on success, None on any failure.

    Failure modes that return None (without raising):
      - No API key configured
      - HTTP error / timeout / non-200 response
      - API responded with an `error` field
    """
    if settings.mpt_api_key is None:
        log.warning("magicprotools submit skipped: MPT_API_KEY not configured")
        return None

    user_name = draft_log.get("users", {}).get(user_id, {}).get("userName", user_id)
    session_id = draft_log.get("sessionID", "unknown")

    try:
        body = convert_to_magicprotools_format(draft_log, user_id)
    except (KeyError, TypeError):
        log.warning(f"magicprotools convert failed for {session_id} / {user_name}", exc_info=True)
        return None

    payload = {
        "draft": body,
        "apiKey": settings.mpt_api_key.get_secret_value(),
        "platform": "mtgadraft",
    }
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": _MPT_REFERER,
    }

    try:
        async with aiohttp.ClientSession(timeout=_REQUEST_TIMEOUT) as session:
            async with session.post(_MPT_ENDPOINT, headers=headers, data=payload) as response:
                if response.status != 200:
                    log.warning(f"magicprotools non-200 for {session_id} / {user_name}: status={response.status}")
                    return None
                body_json = await response.json()
                if body_json.get("error"):
                    log.warning(f"magicprotools error for {session_id} / {user_name}: {body_json['error']}")
                    return None
                url = body_json.get("url")
                if not url:
                    log.warning(f"magicprotools response missing url for {session_id} / {user_name}")
                    return None
                return url
    except (aiohttp.ClientError, TimeoutError):
        log.warning(f"magicprotools HTTP error for {session_id} / {user_name}", exc_info=True)
        return None
