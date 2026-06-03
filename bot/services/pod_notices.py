"""Settings-change notices: each new notice replaces the bot's previous one of the same kind."""
from __future__ import annotations

import logging

import discord

log = logging.getLogger("bot.pod_notices")


async def send_settings_notice(channel, bot_user, content: str, *, marker: str) -> None:
    """Post the notice, then drop the bot's older messages carrying the same marker."""
    try:
        posted = await channel.send(content)
    except discord.HTTPException:
        log.warning("could not post settings-change notice", exc_info=True)
        return
    if bot_user is None or not isinstance(channel, (discord.Thread, discord.TextChannel)):
        return

    def stale(message: discord.Message) -> bool:
        return message.id != posted.id and message.author.id == bot_user.id and marker in message.content

    try:
        await channel.purge(limit=None, check=stale, reason="Stale settings notice")
    except discord.HTTPException as exc:
        log.warning(f"could not purge stale settings notices ({marker}): {exc}")
