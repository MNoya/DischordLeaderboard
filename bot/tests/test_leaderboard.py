from datetime import date, datetime

from bot.commands.leaderboard import (
    LeaderboardData,
    LeaderboardEntry,
    process_leaderboard,
    render_public_embed,
)
from bot.models import MagicSet, Player, PlayerStats


def _seed_set(session, code="SOS"):
    s = MagicSet(code=code, name=code, start_date=date(2026, 4, 21))
    session.add(s)
    session.flush()
    return s


def _seed_player(session, name, discord_id, token_suffix, active=True):
    token = (token_suffix * 32)[:32]
    p = Player(
        slug=f"{name.lower()}-{discord_id}",
        discord_id=discord_id,
        discord_username=name.lower(),
        display_name=name,
        seventeenlands_token=token,
        active=active,
    )
    session.add(p)
    session.flush()
    return p


def _seed_stats(session, p, s, trophies=0, events=1, fmt="PremierDraft", expansion=None):
    """Single PlayerStats row, defaults to Premier so compute_score weights it at 10pts.

    A row with (trophies=0, events=N) yields score=0 — same effect as the old _score(score=0).
    """
    session.add(PlayerStats(
        player_id=p.id, set_id=s.id, format=fmt, expansion=expansion or s.code,
        events=events, wins=trophies * 7, losses=max(0, events - trophies),
        games_played=events * 5, trophies=trophies,
    ))


def test_leaderboard_returns_none_when_no_current_set(session):
    _seed_set(session, code="ECL")
    assert process_leaderboard(session, viewer_discord_id=None) is None


def test_leaderboard_orders_by_score_desc(session):
    s = _seed_set(session)
    a = _seed_player(session, "Alice", "1", "a")
    b = _seed_player(session, "Bob", "2", "b")
    c = _seed_player(session, "Carol", "3", "c")
    _seed_stats(session, a, s, trophies=2, events=4)
    _seed_stats(session, b, s, trophies=5, events=8)
    _seed_stats(session, c, s, trophies=1, events=3)
    session.commit()

    data = process_leaderboard(session, viewer_discord_id=None, top_n=3)
    assert [(e.rank, e.display_name, e.trophies) for e in data.top] == [
        (1, "Bob", 5),
        (2, "Alice", 2),
        (3, "Carol", 1),
    ]


def test_leaderboard_excludes_inactive_players(session):
    s = _seed_set(session)
    a = _seed_player(session, "Alice", "1", "a", active=True)
    b = _seed_player(session, "Bob", "2", "b", active=False)
    _seed_stats(session, a, s, trophies=2, events=4)
    _seed_stats(session, b, s, trophies=10, events=10)
    session.commit()

    data = process_leaderboard(session, viewer_discord_id=None, top_n=3)
    assert [e.display_name for e in data.top] == ["Alice"]


def test_leaderboard_excludes_players_with_no_stats(session):
    s = _seed_set(session)
    a = _seed_player(session, "Alice", "1", "a")
    _seed_player(session, "Newcomer", "2", "b")  # no stats yet
    _seed_stats(session, a, s, trophies=3, events=5)
    session.commit()

    data = process_leaderboard(session, viewer_discord_id=None, top_n=3)
    assert [e.display_name for e in data.top] == ["Alice"]


def test_leaderboard_includes_viewer_outside_top(session):
    s = _seed_set(session)
    for i in range(5):
        p = _seed_player(session, f"P{i}", str(i), chr(ord("a") + i))
        # Higher trophies + higher events → higher score; preserves ordering
        _seed_stats(session, p, s, trophies=10 - i, events=12 - i)
    viewer = _seed_player(session, "Me", "viewer", "z")
    _seed_stats(session, viewer, s, trophies=1, events=20)  # lowest score
    session.commit()

    data = process_leaderboard(session, viewer_discord_id="viewer", top_n=3)
    assert len(data.top) == 3
    assert data.viewer is not None
    assert data.viewer.display_name == "Me"
    assert data.viewer.rank == 6


def test_leaderboard_viewer_none_when_not_registered(session):
    s = _seed_set(session)
    p = _seed_player(session, "Alice", "1", "a")
    _seed_stats(session, p, s, trophies=2, events=4)
    session.commit()

    data = process_leaderboard(session, viewer_discord_id="not_a_user", top_n=3)
    assert data.viewer is None


# ---------------------------------------------------------------------------
# render_public_embed
# ---------------------------------------------------------------------------


def _data(viewer=None, top=None, last_updated=None, drafter_count=0):
    return LeaderboardData(
        set_code="SOS",
        set_name="Secrets of Strixhaven",
        top=top if top is not None else [
            LeaderboardEntry(1, "alice-id", "alice", "Alice", 50.0, 5),
            LeaderboardEntry(2, "bob-id",   "bob",   "Bob",   30.0, 3),
        ],
        viewer=viewer,
        last_updated=last_updated,
        drafter_count=drafter_count,
    )


def test_public_embed_omits_you_are_line_for_outside_viewer():
    viewer = LeaderboardEntry(7, "me-id", "me", "Me", 1.0, 0)
    embed = render_public_embed(_data(viewer=viewer))
    assert embed.description is None or "You are" not in embed.description


def test_public_embed_omits_signup_prompt_for_unregistered_viewer():
    embed = render_public_embed(_data(viewer=None))
    assert all("Not signed up" not in (f.name or "") for f in embed.fields)


def test_public_embed_handles_empty_top():
    embed = render_public_embed(_data(top=[]))
    assert "No players" in (embed.description or "")


def test_public_embed_footer_has_drafter_count_and_last_updated():
    embed = render_public_embed(_data(
        last_updated=datetime(2026, 5, 3, 12, 0, 0),
        drafter_count=8,
    ))
    assert "8 players sharing their drafts" in embed.footer.text
    assert "/join to add yours" in embed.footer.text
    assert "Last updated" in embed.footer.text
    assert "\n" in embed.footer.text
    assert "netlify" not in embed.footer.text


def test_public_embed_footer_singular_for_one_drafter():
    embed = render_public_embed(_data(
        last_updated=datetime(2026, 5, 3, 12, 0, 0),
        drafter_count=1,
    ))
    assert "1 player sharing their drafts" in embed.footer.text
    import re
    assert re.search(r"\bplayers\b", embed.footer.text) is None


def test_public_embed_footer_omits_count_when_zero():
    embed = render_public_embed(_data(
        last_updated=datetime(2026, 5, 3, 12, 0, 0),
        drafter_count=0,
    ))
    assert "drafter" not in embed.footer.text


def test_public_embed_wraps_each_row_in_inline_code():
    embed = render_public_embed(_data(drafter_count=2))
    assert embed.description is not None
    assert embed.description.count("`") >= 2 * 2


# ---------------------------------------------------------------------------
# 0-point hiding
# ---------------------------------------------------------------------------


def test_leaderboard_hides_zero_point_players(session):
    s = _seed_set(session)
    a = _seed_player(session, "Alice", "1", "a")
    b = _seed_player(session, "Bob", "2", "b")
    c = _seed_player(session, "Carol", "3", "c")
    _seed_stats(session, a, s, trophies=2, events=4)
    _seed_stats(session, b, s, trophies=0, events=5)  # no trophies → score 0
    _seed_stats(session, c, s, trophies=1, events=2)
    session.commit()

    data = process_leaderboard(session, viewer_discord_id=None, top_n=10)
    assert [e.display_name for e in data.top] == ["Alice", "Carol"]


def test_leaderboard_zero_point_viewer_still_sees_their_rank(session):
    s = _seed_set(session)
    top = _seed_player(session, "Top", "1", "a")
    me = _seed_player(session, "Me", "viewer", "z")
    _seed_stats(session, top, s, trophies=2, events=4)
    _seed_stats(session, me, s, trophies=0, events=3)  # 0 trophies → 0 score
    session.commit()

    data = process_leaderboard(session, viewer_discord_id="viewer", top_n=10)
    assert data.top == [e for e in data.top if e.score > 0]
    assert data.viewer is not None
    assert data.viewer.display_name == "Me"
    assert data.viewer.score == 0.0


# ---------------------------------------------------------------------------
# drafter_count
# ---------------------------------------------------------------------------


def test_drafter_count_counts_only_players_with_events_in_current_set(session):
    s = _seed_set(session)
    a = _seed_player(session, "Alice", "1", "a")
    b = _seed_player(session, "Bob", "2", "b")
    c = _seed_player(session, "Carol", "3", "c")
    _seed_stats(session, a, s, trophies=1, events=2)   # counted
    _seed_stats(session, b, s, trophies=0, events=0)   # zero events — not counted
    _seed_stats(session, c, s, trophies=0, events=1)   # counted
    session.commit()

    data = process_leaderboard(session, viewer_discord_id=None, top_n=10)
    assert data.drafter_count == 2


def test_drafter_count_excludes_inactive_players(session):
    s = _seed_set(session)
    a = _seed_player(session, "Alice", "1", "a", active=True)
    b = _seed_player(session, "Bob", "2", "b", active=False)
    _seed_stats(session, a, s, trophies=1, events=2)
    _seed_stats(session, b, s, trophies=2, events=5)
    session.commit()

    data = process_leaderboard(session, viewer_discord_id=None, top_n=10)
    assert data.drafter_count == 1
