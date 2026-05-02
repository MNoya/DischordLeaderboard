from datetime import date

from bot.commands.leaderboard import process_leaderboard
from bot.models import MagicSet, Player, PlayerSetScore


def _seed_set(session, code="SOS"):
    s = MagicSet(code=code, name=code, start_date=date(2026, 4, 21))
    session.add(s)
    session.flush()
    return s


def _seed_player(session, name, discord_id, token_suffix, active=True):
    token = (token_suffix * 32)[:32]
    p = Player(
        discord_id=discord_id,
        discord_username=name.lower(),
        display_name=name,
        seventeenlands_token=token,
        seventeenlands_url=f"https://www.17lands.com/user_history/{token}",
        active=active,
    )
    session.add(p)
    session.flush()
    return p


def _score(session, p, s, score, trophies=0):
    session.add(PlayerSetScore(player_id=p.id, set_id=s.id, score=score, trophies=trophies))


def test_leaderboard_returns_none_when_no_current_set(session):
    _seed_set(session, code="ECL")
    assert process_leaderboard(session, viewer_discord_id=None) is None


def test_leaderboard_orders_by_score_desc(session):
    s = _seed_set(session)
    a = _seed_player(session, "Alice", "1", "a")
    b = _seed_player(session, "Bob", "2", "b")
    c = _seed_player(session, "Carol", "3", "c")
    _score(session, a, s, score=42.5, trophies=5)
    _score(session, b, s, score=88.1, trophies=10)
    _score(session, c, s, score=12.0, trophies=2)
    session.commit()

    data = process_leaderboard(session, viewer_discord_id=None, top_n=3)
    assert [(e.rank, e.display_name, e.score, e.trophies) for e in data.top] == [
        (1, "Bob", 88.1, 10),
        (2, "Alice", 42.5, 5),
        (3, "Carol", 12.0, 2),
    ]


def test_leaderboard_excludes_inactive_players(session):
    s = _seed_set(session)
    a = _seed_player(session, "Alice", "1", "a", active=True)
    b = _seed_player(session, "Bob", "2", "b", active=False)
    _score(session, a, s, score=10.0, trophies=2)
    _score(session, b, s, score=99.0, trophies=10)
    session.commit()

    data = process_leaderboard(session, viewer_discord_id=None, top_n=3)
    assert [e.display_name for e in data.top] == ["Alice"]


def test_leaderboard_excludes_players_with_no_score_row(session):
    """A player without a PlayerSetScore for the current set isn't shown."""
    s = _seed_set(session)
    a = _seed_player(session, "Alice", "1", "a")
    _seed_player(session, "Newcomer", "2", "b")  # no score yet
    _score(session, a, s, score=15.0, trophies=3)
    session.commit()

    data = process_leaderboard(session, viewer_discord_id=None, top_n=3)
    assert [e.display_name for e in data.top] == ["Alice"]


def test_leaderboard_includes_viewer_outside_top(session):
    s = _seed_set(session)
    for i in range(5):
        p = _seed_player(session, f"P{i}", str(i), chr(ord("a") + i))
        _score(session, p, s, score=100.0 - i, trophies=10 - i)
    viewer = _seed_player(session, "Me", "viewer", "z")
    _score(session, viewer, s, score=2.5, trophies=1)
    session.commit()

    data = process_leaderboard(session, viewer_discord_id="viewer", top_n=3)
    assert len(data.top) == 3
    assert data.viewer is not None
    assert data.viewer.display_name == "Me"
    assert data.viewer.rank == 6
    assert data.viewer.score == 2.5


def test_leaderboard_viewer_none_when_not_registered(session):
    s = _seed_set(session)
    p = _seed_player(session, "Alice", "1", "a")
    _score(session, p, s, score=10.0, trophies=2)
    session.commit()

    data = process_leaderboard(session, viewer_discord_id="not_a_user", top_n=3)
    assert data.viewer is None
