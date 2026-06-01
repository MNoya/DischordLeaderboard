from datetime import date, datetime

from bot.commands.leaderboard import (
    LeaderboardData,
    LeaderboardEntry,
    PersonalStanding,
    PersonalStandingsData,
    process_leaderboard,
    process_personal_standings,
    render_personal_embed,
    render_public_embed,
)
from bot.services.player_stats import StatsData, render_embed as render_stats_embed
from bot.models import MagicSet, Player, PlayerStats


def _seed_set(session, code="SOS"):
    s = MagicSet(code=code, name=code, start_date=date(2026, 4, 21))
    session.add(s)
    session.flush()
    return s


def _seed_player(session, name, discord_id, token_suffix, active=True, leaderboard_opt_in=True):
    token = (token_suffix * 32)[:32]
    p = Player(
        slug=f"{name.lower()}-{discord_id}",
        discord_id=discord_id,
        discord_username=name.lower(),
        display_name=name,
        seventeenlands_token=token,
        active=active,
        leaderboard_opt_in=leaderboard_opt_in,
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


def test_leaderboard_excludes_opted_out_players(session):
    s = _seed_set(session)
    a = _seed_player(session, "Alice", "1", "a")
    b = _seed_player(session, "Bob", "2", "b", leaderboard_opt_in=False)
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


def test_stats_embed_opted_out_hides_rank_and_points_keeps_trophies():
    data = StatsData(
        set_code="SOS", set_name="SOS", player_name="Bob", player_slug="bob",
        rank=None, total_score=42.0, total_trophies=3, opted_out=True,
        breakdown=[{"label": "Premier", "events": 2, "wins": 7, "losses": 3, "trophies": 3, "score": 42.0}],
    )
    desc = render_stats_embed(data).description or ""
    summary = desc.split("\n", 1)[0]
    assert "3 🏆" in summary
    assert "#" not in summary
    assert "42.0 pts" not in desc
    assert "pts" not in desc
    assert "Not yet on the leaderboard" not in summary


def test_stats_embed_not_yet_on_board_when_not_opted_out_and_no_rank():
    data = StatsData(
        set_code="SOS", set_name="SOS", player_name="Newcomer", player_slug="new",
        rank=None, total_score=0.0, total_trophies=0, opted_out=False,
    )
    assert "Not yet on the leaderboard" in (render_stats_embed(data).description or "")


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


# ---------------------------------------------------------------------------
# historical set override + embed link
# ---------------------------------------------------------------------------


def test_process_leaderboard_renders_non_active_set_via_override(session):
    # No active (SOS) set seeded — only the historical one
    stx = _seed_set(session, code="STX")
    a = _seed_player(session, "Alice", "1", "a")
    _seed_stats(session, a, stx, trophies=3, events=5)
    session.commit()

    assert process_leaderboard(session, viewer_discord_id=None) is None
    data = process_leaderboard(session, viewer_discord_id=None, magic_set=stx)
    assert data is not None
    assert data.set_code == "STX"
    assert [e.display_name for e in data.top] == ["Alice"]


def test_embed_link_strips_path_and_points_at_set_for_historical():
    entry = LeaderboardEntry(rank=1, player_id="p", slug="alice-1", display_name="Alice", score=42.0, trophies=3)
    data = LeaderboardData(set_code="STX", set_name="STX", top=[entry], viewer=None)
    embed = render_public_embed(data)
    assert "[dischord.pages.dev]" in embed.description
    assert "[dischord.pages.dev/leaderboard]" not in embed.description
    assert embed.url.endswith("/STX")


def test_embed_link_active_set_has_no_set_path():
    entry = LeaderboardEntry(rank=1, player_id="p", slug="alice-1", display_name="Alice", score=42.0, trophies=3)
    data = LeaderboardData(set_code="SOS", set_name="SOS", top=[entry], viewer=None)
    embed = render_public_embed(data)
    assert not embed.url.rstrip("/").endswith("/SOS")


# ---------------------------------------------------------------------------
# personal standings (scope:Me)
# ---------------------------------------------------------------------------


def test_personal_standings_unfiltered_aggregates_all_formats(session):
    s = _seed_set(session)
    alice = _seed_player(session, "Alice", "1", "a")
    _seed_stats(session, alice, s, trophies=2, events=4, fmt="PremierDraft")
    _seed_stats(session, alice, s, trophies=1, events=2, fmt="QuickDraft")
    session.commit()

    data = process_personal_standings(session, "1")
    assert data.format_label is None
    assert len(data.rows) == 1
    assert (data.rows[0].events, data.rows[0].trophies) == (6, 3)


def test_personal_standings_format_filter_scopes_to_group(session):
    s = _seed_set(session)
    alice = _seed_player(session, "Alice", "1", "a")
    _seed_stats(session, alice, s, trophies=2, events=4, fmt="PremierDraft")
    _seed_stats(session, alice, s, trophies=1, events=2, fmt="QuickDraft")
    session.commit()

    data = process_personal_standings(session, "1", format_label="Premier")
    assert data.format_label == "Premier"
    assert len(data.rows) == 1
    assert (data.rows[0].events, data.rows[0].trophies) == (4, 2)


def test_personal_standings_format_rank_uses_format_board(session):
    s = _seed_set(session)
    alice = _seed_player(session, "Alice", "1", "a")
    bob = _seed_player(session, "Bob", "2", "b")
    _seed_stats(session, alice, s, trophies=2, events=3, fmt="PremierDraft")
    _seed_stats(session, bob, s, trophies=5, events=6, fmt="PremierDraft")
    session.commit()

    data = process_personal_standings(session, "1", format_label="Premier")
    assert data.rows[0].rank == 2


def test_personal_standings_format_excludes_sets_without_group_events(session):
    s = _seed_set(session)
    alice = _seed_player(session, "Alice", "1", "a")
    _seed_stats(session, alice, s, trophies=1, events=2, fmt="QuickDraft")
    session.commit()

    data = process_personal_standings(session, "1", format_label="Premier")
    assert data.rows == []


def _personal(rows=None, opted_out=False, format_label=None):
    return PersonalStandingsData(
        player_name="Alice", player_slug="alice",
        rows=rows if rows is not None else [
            PersonalStanding(set_code="SOS", score=42.0, trophies=3, events=5, wins=21, losses=4, rank=1),
        ],
        opted_out=opted_out, format_label=format_label,
    )


def test_personal_embed_omits_winrate_column():
    desc = render_personal_embed(_personal()).description or ""
    assert "Win%" not in desc


def test_personal_embed_title_appends_format_suffix():
    embed = render_personal_embed(_personal(format_label="Premier"))
    assert embed.title.endswith("· Premier")


def test_personal_embed_title_plain_without_filter():
    embed = render_personal_embed(_personal())
    assert "·" not in embed.title
