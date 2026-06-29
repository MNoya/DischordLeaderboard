"""Persistence for /trophy self-reported trophies.

Showcase-only records: a player logs a trophy they posted in trophy-hype to their profile.
Idempotent on (player_id, source_message_id) so re-running /trophy on the same post edits
the existing row instead of stacking duplicates.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.models import MagicSet, Player, SelfReportedTrophy
from bot.slug import disambiguate_slug, slugify


def get_or_create_player(
    session: Session,
    *,
    discord_id: str,
    discord_username: str,
    display_name: str,
    avatar_hash: str | None,
) -> Player:
    """The Player for a Discord user, creating a lightweight 17lands-less row when none exists.

    /trophy is a valid first touch: a player can showcase trophies before ever linking 17lands.
    Mirrors the tokenless player pods create via /link-arena.
    """
    player = session.execute(
        select(Player).where(Player.discord_id == discord_id)
    ).scalar_one_or_none()
    if player is None:
        taken_slugs = set(session.execute(select(Player.slug)).scalars().all())
        player = Player(
            slug=disambiguate_slug(slugify(display_name), taken_slugs),
            discord_id=discord_id,
            discord_username=discord_username,
            display_name=display_name,
            avatar_hash=avatar_hash,
            active=True,
            leaderboard_opt_in=False,
        )
        session.add(player)
        session.flush()
    return player


def upsert_trophy(
    session: Session,
    *,
    player_id: str,
    set_code: str,
    record: str,
    colors: str | None,
    platform: str,
    caption: str | None,
    screenshot_url: str | None,
    source_channel_id: str,
    source_message_id: str,
    source_url: str,
    reported_at: datetime | None = None,
) -> SelfReportedTrophy:
    trophy = session.execute(
        select(SelfReportedTrophy).where(
            SelfReportedTrophy.player_id == player_id,
            SelfReportedTrophy.source_message_id == source_message_id,
        )
    ).scalar_one_or_none()
    if trophy is None:
        trophy = SelfReportedTrophy(player_id=player_id, source_message_id=source_message_id)
        session.add(trophy)
    trophy.set_code = set_code
    trophy.set_id = _resolve_set_id(session, set_code)
    trophy.record = record
    trophy.colors = colors
    trophy.platform = platform
    trophy.caption = caption
    trophy.screenshot_url = screenshot_url
    if reported_at is not None:
        trophy.reported_at = reported_at
    trophy.source_channel_id = source_channel_id
    trophy.source_url = source_url
    session.flush()
    return trophy


def _resolve_set_id(session: Session, set_code: str) -> str | None:
    return session.execute(
        select(MagicSet.id).where(MagicSet.code == set_code)
    ).scalar_one_or_none()
