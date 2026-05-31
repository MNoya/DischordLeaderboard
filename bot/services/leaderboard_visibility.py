from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.models import Player

MSG_JOINED_LEADERBOARD = "🎉 Welcome aboard! Run `/help` to see what you can do."
MSG_NOT_REGISTERED = "You're not on the leaderboard yet. Run `/join` or `/link-17lands` first."
MSG_NOW_HIDDEN = "🕵️ Your rank is now hidden. Your profile and trophies stay visible."
MSG_ALREADY_HIDDEN = "You're already off the rankings. Run `/join` to be ranked again."
MSG_RANKED_AGAIN = "👋 You're ranked again. Your stats are back in the standings."


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
