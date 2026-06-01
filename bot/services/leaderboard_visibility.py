from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.models import Player


def set_opt_in(session: Session, discord_id: str, opt_in: bool) -> Player | None:
    """Flip a player's leaderboard ranking visibility. Returns the player, or None if not registered."""
    player = session.execute(
        select(Player).where(Player.discord_id == discord_id)
    ).scalar_one_or_none()
    if player is None:
        return None
    player.leaderboard_opt_in = opt_in
    session.commit()
    return player
