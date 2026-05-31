from __future__ import annotations

from bot.models import Player
from bot.services.leaderboard_visibility import set_opt_in


def _seed(session, discord_id, opt_in=True, token="t" * 32):
    p = Player(
        slug=f"x-{discord_id}",
        discord_id=discord_id,
        discord_username="x",
        display_name="X",
        seventeenlands_token=token,
        active=True,
        leaderboard_opt_in=opt_in,
    )
    session.add(p)
    session.commit()
    return p


def test_set_opt_in_hides_player(session):
    p = _seed(session, "111", opt_in=True)
    result = set_opt_in(session, "111", False)
    assert result is p
    session.refresh(p)
    assert p.leaderboard_opt_in is False


def test_set_opt_in_shows_player(session):
    p = _seed(session, "111", opt_in=False)
    set_opt_in(session, "111", True)
    session.refresh(p)
    assert p.leaderboard_opt_in is True


def test_set_opt_in_unregistered_returns_none(session):
    assert set_opt_in(session, "nope", False) is None
