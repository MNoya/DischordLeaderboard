"""Discord-specific helpers shared across signup, linking, and refresh.

Keeping these in one place so the avatar capture logic doesn't drift between
the three entry points that touch it.
"""
from __future__ import annotations

import logging
import unicodedata
from typing import TYPE_CHECKING, Iterable

from bot.config import settings


if TYPE_CHECKING:
    import discord
    from sqlalchemy.orm import Session
    from discord.ext import commands

    from bot.models import Player

logger = logging.getLogger(__name__)

def extract_avatar_hash(user: "discord.abc.User | discord.User | discord.Member | None") -> str | None:
    """Return the Discord avatar hash for a user, or None if they use the default avatar.

    `user.avatar` is an `Optional[Asset]`; the asset's `.key` is the hash that
    composes into the CDN URL. We persist the hash, not the URL, so changes to
    the CDN host (e.g. a Discord-side migration) don't require a backfill.
    """
    if user is None:
        return None
    avatar = getattr(user, "avatar", None)
    if avatar is None:
        return None
    return getattr(avatar, "key", None)


async def refresh_player_profiles(
    bot: "commands.Bot",
    session: "Session",
    players: "Iterable[Player]",
) -> dict:
    """Re-fetch each linked player and sync their avatar, display name, and username if changed.

    Players without a `discord_id` are skipped; players we can't resolve
    (deleted account, banned) keep their last-known values.
    """
    summary = {"checked": 0, "updated": 0, "skipped": 0, "errors": 0}
    for player in players:
        if not player.discord_id:
            summary["skipped"] += 1
            continue
        summary["checked"] += 1
        try:
            user = await bot.fetch_user(int(player.discord_id))
        except Exception:  # noqa: BLE001 - Discord can throw a wide variety
            logger.warning(f"profile refresh: could not fetch user {player.discord_id}", exc_info=True)
            summary["errors"] += 1
            continue
        changed = False
        new_hash = extract_avatar_hash(user)
        if player.avatar_hash != new_hash:
            player.avatar_hash = new_hash
            changed = True
        new_display_name = await resolve_display_name(bot, user)
        if player.display_name != new_display_name:
            player.display_name = new_display_name
            changed = True
        new_username = str(user)
        if player.discord_username != new_username:
            player.discord_username = new_username
            changed = True
        if changed:
            summary["updated"] += 1
    session.commit()
    return summary


def display_width(s: str) -> int:
    """Monospace column width, counting wide CJK glyphs as 2 cells where len() counts 1."""
    return sum(2 if unicodedata.east_asian_width(ch) == "W" else 1 for ch in s)


def player_url(slug: str, set_code: str | None = None) -> str:
    """Public site URL for a player's page, set-scoped when set_code is given."""
    base = settings.public_site_url.rstrip("/")
    return f"{base}/{set_code}/player/{slug}" if set_code else f"{base}/player/{slug}"


async def resolve_display_name(bot: "commands.Bot", user: "discord.User") -> str:
    """Prefer the LLU guild nickname, falling back to the user's global display name.

    `bot.fetch_user` only knows the global account, so `User.display_name` is the
    global name. The server-specific nickname lives on the guild `Member`, which we
    resolve from the configured guild and fall back off of when the player has left.
    """
    guild_id = settings.discord_guild_id
    if guild_id:
        guild = bot.get_guild(guild_id)
        if guild is not None:
            member = guild.get_member(user.id)
            if member is None:
                try:
                    member = await guild.fetch_member(user.id)
                except Exception:  # noqa: BLE001 - not in guild, or Discord hiccup
                    member = None
            if member is not None:
                return member.display_name
    return user.display_name
