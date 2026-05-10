from datetime import date, datetime

from bot.commands.leaderboard import (
    LeaderboardData,
    LeaderboardEntry,
    process_leaderboard,
    render_public_embed,
)
from bot.models import MagicSet, Player, PlayerSetScore, PlayerStats


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


# ---------------------------------------------------------------------------
# render_public_embed / render_personal_text
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


def _player_field_value(embed):
    for f in embed.fields:
        if f.name == "Player":
            return f.value
    return ""


def test_public_embed_omits_you_are_line_for_outside_viewer():
    """If viewer is below top, 'You are #N' must not leak into the public message."""
    viewer = LeaderboardEntry(7, "me-id", "me", "Me", 1.0, 0)
    embed = render_public_embed(_data(viewer=viewer))
    assert embed.description is None or "You are" not in embed.description


def test_public_embed_omits_signup_prompt_for_unregistered_viewer():
    """Public version shouldn't pitch /join — that only makes sense to the invoker."""
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
    # footer is two lines: '<N> players sharing their stats · /join to add yours'
    # then 'Last updated'. URL stays on embed.url, not in footer text.
    assert "8 players sharing their stats" in embed.footer.text
    assert "/join to add yours" in embed.footer.text
    assert "Last updated" in embed.footer.text
    assert "\n" in embed.footer.text
    assert "netlify" not in embed.footer.text


def test_public_embed_footer_singular_for_one_drafter():
    embed = render_public_embed(_data(
        last_updated=datetime(2026, 5, 3, 12, 0, 0),
        drafter_count=1,
    ))
    assert "1 player sharing their stats" in embed.footer.text
    # plural must not appear when there's just one drafter
    import re
    assert re.search(r"\bplayers\b", embed.footer.text) is None


def test_public_embed_footer_omits_count_when_zero():
    embed = render_public_embed(_data(
        last_updated=datetime(2026, 5, 3, 12, 0, 0),
        drafter_count=0,
    ))
    assert "drafter" not in embed.footer.text


def test_public_embed_wraps_each_row_in_inline_code():
    """Inline code per row gives monospace alignment without the code-block brick."""
    embed = render_public_embed(_data(drafter_count=2))
    # Description should contain backtick-wrapped rows, one per top entry
    assert embed.description is not None
    assert embed.description.count("`") >= 2 * 2  # at least 2 rows × 2 backticks each




# ---------------------------------------------------------------------------
# 0-point hiding
# ---------------------------------------------------------------------------


def test_leaderboard_hides_zero_point_players(session):
    s = _seed_set(session)
    a = _seed_player(session, "Alice", "1", "a")
    b = _seed_player(session, "Bob", "2", "b")
    c = _seed_player(session, "Carol", "3", "c")
    _score(session, a, s, score=10.0, trophies=2)
    _score(session, b, s, score=0.0,  trophies=0)
    _score(session, c, s, score=5.0,  trophies=1)
    session.commit()

    data = process_leaderboard(session, viewer_discord_id=None, top_n=10)
    assert [e.display_name for e in data.top] == ["Alice", "Carol"]


def test_leaderboard_zero_point_viewer_still_sees_their_rank(session):
    """0-point viewer should still get a viewer entry so 'You are #N' renders."""
    s = _seed_set(session)
    a = _seed_player(session, "Top",  "1", "a")
    me = _seed_player(session, "Me",  "viewer", "z")
    _score(session, a, s, score=10.0, trophies=2)
    _score(session, me, s, score=0.0, trophies=0)
    session.commit()

    data = process_leaderboard(session, viewer_discord_id="viewer", top_n=10)
    assert data.top == [e for e in data.top if e.score > 0]
    assert data.viewer is not None
    assert data.viewer.display_name == "Me"
    assert data.viewer.score == 0.0


# ---------------------------------------------------------------------------
# process_leaderboard drafter_count
# ---------------------------------------------------------------------------


def _stat(session, p, s, format="PremierDraft", expansion="SOS", events=1):
    session.add(PlayerStats(
        player_id=p.id, set_id=s.id, format=format, expansion=expansion,
        events=events, wins=0, losses=0, games_played=0, trophies=0,
    ))


def test_drafter_count_counts_only_players_with_events_in_current_set(session):
    s = _seed_set(session)
    a = _seed_player(session, "Alice", "1", "a")
    b = _seed_player(session, "Bob", "2", "b")
    c = _seed_player(session, "Carol", "3", "c")
    _score(session, a, s, score=10.0)
    _score(session, b, s, score=0.0)
    _score(session, c, s, score=5.0)
    _stat(session, a, s, events=2)         # counted
    _stat(session, b, s, events=0)         # zero events — not counted
    _stat(session, c, s, events=1)         # counted
    session.commit()

    data = process_leaderboard(session, viewer_discord_id=None, top_n=10)
    assert data.drafter_count == 2


def test_drafter_count_excludes_inactive_players(session):
    s = _seed_set(session)
    a = _seed_player(session, "Alice", "1", "a", active=True)
    b = _seed_player(session, "Bob", "2", "b", active=False)
    _score(session, a, s, score=10.0)
    _score(session, b, s, score=20.0)
    _stat(session, a, s, events=2)
    _stat(session, b, s, events=5)
    session.commit()

    data = process_leaderboard(session, viewer_discord_id=None, top_n=10)
    assert data.drafter_count == 1
