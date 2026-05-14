from sqlalchemy import select

from bot.commands.delete_account import process_delete_account
from bot.models import MagicSet, Player, PlayerStats
from datetime import date


def _seed_player(session, discord_id="111"):
    p = Player(
        slug=f"alice-{discord_id}",
        discord_id=discord_id,
        discord_username="alice",
        display_name="Alice",
        seventeenlands_token=("a" * 32),
        active=True,
    )
    session.add(p)
    session.flush()
    return p


def test_delete_account_not_registered(session):
    result = process_delete_account(session, "nope")
    assert result.kind == "not_registered"
    assert result.deleted_player_id is None


def test_delete_account_removes_player_and_cascades_stats(session):
    p = _seed_player(session, discord_id="111")
    s = MagicSet(code="ECL", name="ECL", start_date=date(2026, 1, 20))
    session.add(s)
    session.flush()
    session.add(PlayerStats(
        player_id=p.id, set_id=s.id, format="PremierDraft", expansion="ECL",
        wins=5, losses=2, games_played=7, trophies=1,
    ))
    session.commit()

    result = process_delete_account(session, "111")

    assert result.kind == "deleted"
    assert result.deleted_player_id == p.id
    assert session.execute(select(Player).where(Player.id == p.id)).scalar_one_or_none() is None
    assert session.execute(select(PlayerStats).where(PlayerStats.player_id == p.id)).scalars().all() == []
