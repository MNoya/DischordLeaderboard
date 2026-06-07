"""The "Pod Draft registered!" thread embed: built once at registration, then re-rendered in
place whenever Format, Pairings, or Seats change through the lobby Settings panel."""
from __future__ import annotations

import logging

import discord

from bot.services.lobby_embed import SettingsButton
from bot.services.pod_format import format_display
from bot.services.pod_pairing_select import pairing_label
from bot.services.pod_seating_select import seating_mode_label
from bot.sets import set_name_for
from bot.tasks.pod_draft_reminder import REMINDER_LEAD_MIN

log = logging.getLogger("bot.pod_registration_embed")

REGISTERED_TITLE = "🤖 Pod Draft registered!"
CHAMPIONSHIP_TITLE = "👑 Set Championship registered!"
HISTORY_SCAN_LIMIT = 25


class RegisteredSettingsView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(SettingsButton())


def championship_flavor(set_code: str) -> str:
    return (
        f"**{set_name_for(set_code)}** Season!\n"
        "Eight seats to the highest-ranked players who claim them.\n"
    )


def build_registered_embed(
    set_code: str, pairing_mode: str | None, seating_mode: str | None = None,
    *, championship: bool = False,
) -> discord.Embed:
    settings_line = (
        f"Format: **{format_display(set_code)}** · Pairings: **{pairing_label(pairing_mode)}** "
        f"· Seats: **{seating_mode_label(seating_mode)}**\n"
        f"Draftmancer link will be posted {REMINDER_LEAD_MIN} minutes before the event starts."
    )
    if championship:
        return discord.Embed(
            title=CHAMPIONSHIP_TITLE,
            description=f"{championship_flavor(set_code)}\n{settings_line}",
            color=discord.Color.gold(),
        )
    return discord.Embed(
        title=REGISTERED_TITLE,
        description=settings_line,
        color=discord.Color.green(),
    )


async def update_registered_embed(
    channel: discord.abc.Messageable | None,
    *,
    client_user: discord.ClientUser | None,
    set_code: str,
    pairing_mode: str | None,
    seating_mode: str | None = None,
    championship: bool = False,
) -> None:
    """Walk the thread for the bot's registration embed and re-render it with the current settings."""
    if channel is None or client_user is None:
        return
    titles = {REGISTERED_TITLE, CHAMPIONSHIP_TITLE}
    try:
        async for msg in channel.history(limit=HISTORY_SCAN_LIMIT, oldest_first=True):
            if msg.author.id == client_user.id and msg.embeds and msg.embeds[0].title in titles:
                await msg.edit(embed=build_registered_embed(
                    set_code, pairing_mode, seating_mode, championship=championship))
                return
    except discord.HTTPException:
        log.warning("could not update Pod Draft registered embed", exc_info=True)
