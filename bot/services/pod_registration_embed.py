"""The "Pod Draft registered!" thread embed: built once at registration, then re-rendered in
place whenever Format or Pairings change through the lobby Settings panel."""
from __future__ import annotations

import logging

import discord

from bot.services.pod_format import format_display
from bot.services.pod_pairing_select import pairing_label
from bot.tasks.pod_draft_reminder import REMINDER_LEAD_MIN

log = logging.getLogger("bot.pod_registration_embed")

REGISTERED_TITLE = "🤖 Pod Draft registered!"
HISTORY_SCAN_LIMIT = 25


def build_registered_embed(set_code: str, pairing_mode: str | None) -> discord.Embed:
    return discord.Embed(
        title=REGISTERED_TITLE,
        description=(
            f"Format: **{format_display(set_code)}** · Pairings: **{pairing_label(pairing_mode)}**\n"
            f"Draftmancer link will be posted {REMINDER_LEAD_MIN} minutes before the event starts."
        ),
        color=discord.Color.green(),
    )


async def update_registered_embed(
    channel: discord.abc.Messageable | None,
    *,
    client_user: discord.ClientUser | None,
    set_code: str,
    pairing_mode: str | None,
) -> None:
    """Walk the thread for the bot's registration embed and re-render it with the current settings."""
    if channel is None or client_user is None:
        return
    try:
        async for msg in channel.history(limit=HISTORY_SCAN_LIMIT, oldest_first=True):
            if msg.author.id == client_user.id and msg.embeds and msg.embeds[0].title == REGISTERED_TITLE:
                await msg.edit(embed=build_registered_embed(set_code, pairing_mode))
                return
    except discord.HTTPException:
        log.warning("could not update Pod Draft registered embed", exc_info=True)
