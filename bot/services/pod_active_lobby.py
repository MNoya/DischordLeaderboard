"""Bridge from a just-linked Arena handle back to a live lobby the player belongs to, so any Link Arena
success can hand back the personalized Draftmancer link with no second click. Kept as a leaf module (no
lobby-post or DM imports) so `ping_roles` can reach it without an import cycle.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.database import SessionLocal
from bot.models import PodSignal, PodSignalMember
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_drafts import player_arena_handle
from bot.services.pod_signals import RSVP_MAYBE, RSVP_YES


def active_lobby_link_for(discord_id: str) -> tuple[str, str] | None:
    """The (session_id, arena_name) a just-linked player should receive for the live lobby that lists
    them as Yes or Maybe, or None when no active lobby does. Returns None for an unlinked player."""
    if not ACTIVE_POD_MANAGERS:
        return None
    with SessionLocal() as session:
        arena_name = player_arena_handle(session, discord_id)
        if arena_name is None:
            return None
        for event_id, manager in ACTIVE_POD_MANAGERS.items():
            if _is_rsvp_member(session, event_id, discord_id):
                return manager.session_id, arena_name
    return None


def _is_rsvp_member(session: Session, event_id: str, discord_id: str) -> bool:
    signal = session.execute(
        select(PodSignal).where(PodSignal.event_id == event_id)
    ).scalar_one_or_none()
    if signal is None:
        return False
    hit = session.execute(
        select(PodSignalMember.id).where(
            PodSignalMember.signal_id == signal.id,
            PodSignalMember.discord_user_id == discord_id,
            PodSignalMember.rsvp.in_((RSVP_YES, RSVP_MAYBE)),
        ).limit(1)
    ).scalar_one_or_none()
    return hit is not None
