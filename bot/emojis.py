from __future__ import annotations

import logging

import discord
from discord.ext import commands


log = logging.getLogger("bot.emojis")

_EMOJIS: dict[str, discord.Emoji] = {}


def get(name: str) -> str:
    e = _EMOJIS.get(name)
    return str(e) if e else ""


def get_emoji(name: str) -> discord.Emoji | None:
    return _EMOJIS.get(name)


def prefix(name: str) -> str:
    """Custom emoji followed by a space for inlining before text, or '' if not loaded."""
    e = _EMOJIS.get(name)
    return f"{e} " if e else ""


def resolve(token: str) -> str | None:
    """An application-emoji name resolves to its glyph, a unicode glyph passes through, and an
    application name that isn't loaded yet resolves to None."""
    e = _EMOJIS.get(token)
    if e:
        return str(e)
    return None if token.isalnum() else token


def mana_number(n: int) -> str:
    """`5` → `:mana5:` glyph if loaded, else `'5'` fallback. Mana font ships 0–20."""
    e = _EMOJIS.get(f"mana{n}")
    return str(e) if e else str(n)


async def load(bot: commands.Bot) -> None:
    try:
        fetched = await bot.fetch_application_emojis()
    except discord.HTTPException:
        log.warning("could not fetch application emojis", exc_info=True)
        return
    _EMOJIS.clear()
    for e in fetched:
        _EMOJIS[e.name] = e
    log.info(f"loaded {len(_EMOJIS)} application emojis: {', '.join(sorted(_EMOJIS)) or '(none)'}")
