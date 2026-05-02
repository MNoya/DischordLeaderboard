from sqlalchemy import select

from bot.commands.signout import process_signout
from bot.models import Player


def _seed_player(session, discord_id="111", active=True):
    p = Player(
        discord_id=discord_id,
        discord_username="alice",
        display_name="Alice",
        seventeenlands_token=("a" * 32),
        seventeenlands_url="https://www.17lands.com/user_history/" + ("a" * 32),
        active=active,
    )
    session.add(p)
    session.flush()
    return p


def test_signout_marks_active_player_inactive(session):
    p = _seed_player(session, discord_id="111")

    result = process_signout(session, "111")

    assert result.kind == "signed_out"
    assert result.player_id == p.id
    refreshed = session.execute(select(Player).where(Player.id == p.id)).scalar_one()
    assert refreshed.active is False


def test_signout_already_inactive(session):
    _seed_player(session, discord_id="222", active=False)

    result = process_signout(session, "222")

    assert result.kind == "already_inactive"


def test_signout_not_registered(session):
    result = process_signout(session, "nonexistent")
    assert result.kind == "not_registered"
    assert result.player_id is None
