from bot.commands.leaderboard import process_leaderboard_for_mtgo
from bot.models import Player, SelfReportedEvent


def _seed_player(session, name, discord_id):
    player = Player(
        slug=f"{name.lower()}-{discord_id}",
        discord_id=discord_id,
        discord_username=name.lower(),
        display_name=name,
        active=True,
        leaderboard_opt_in=False,
    )
    session.add(player)
    session.flush()
    return player


def _seed_event(session, player, set_code, message_id, *, is_trophy=True, colors="UR"):
    event = SelfReportedEvent(
        player_id=player.id,
        set_code=set_code,
        record="3-0" if is_trophy else "2-1",
        is_trophy=is_trophy,
        colors=colors,
        platform="MTGO",
        source_channel_id="0",
        source_message_id=message_id,
        source_url="#",
    )
    session.add(event)
    session.flush()
    return event


def test_mtgo_board_ranks_by_trophy_count(session):
    alice = _seed_player(session, "Alice", "1")
    bram = _seed_player(session, "Bram", "2")
    _seed_event(session, alice, "MH1", "m1")
    _seed_event(session, alice, "MH1", "m2")
    _seed_event(session, bram, "MH1", "m3")
    _seed_event(session, bram, "MH2", "m4")

    data = process_leaderboard_for_mtgo(session, "MH1")

    assert data.trophy_board is True
    assert data.show_score is False
    assert [(e.display_name, e.trophies, e.rank) for e in data.top] == [("Alice", 2, 1), ("Bram", 1, 2)]
    assert data.drafter_count == 2


def test_mtgo_board_non_trophies_dont_lift_rank_but_keep_player_on_board(session):
    alice = _seed_player(session, "Alice", "1")
    bram = _seed_player(session, "Bram", "2")
    _seed_event(session, alice, "MH1", "m1", is_trophy=True)
    _seed_event(session, bram, "MH1", "m2", is_trophy=False)
    _seed_event(session, bram, "MH1", "m3", is_trophy=False)

    data = process_leaderboard_for_mtgo(session, "MH1")

    assert [(e.display_name, e.trophies, e.rank) for e in data.top] == [("Alice", 1, 1), ("Bram", 0, 2)]


def test_mtgo_board_breaks_trophy_ties_by_deck_count(session):
    alice = _seed_player(session, "Alice", "1")
    bram = _seed_player(session, "Bram", "2")
    _seed_event(session, alice, "MH1", "m1", is_trophy=True)
    _seed_event(session, bram, "MH1", "m2", is_trophy=True)
    _seed_event(session, bram, "MH1", "m3", is_trophy=False)

    data = process_leaderboard_for_mtgo(session, "MH1")

    assert [(e.display_name, e.trophies, e.rank) for e in data.top] == [("Bram", 1, 1), ("Alice", 1, 2)]


def test_mtgo_board_empty_when_no_events(session):
    data = process_leaderboard_for_mtgo(session, "USG")

    assert data.top == []
    assert data.trophy_board is True
