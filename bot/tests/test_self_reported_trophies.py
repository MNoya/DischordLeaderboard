from datetime import date, datetime, timezone

import pytest

from bot.discord_helpers import parse_message_link
from bot.models import MagicSet, Player, SelfReportedTrophy
from bot.services.self_reported_trophies import get_or_create_player, upsert_trophy


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://discord.com/channels/100/200/300", (100, 200, 300)),
        ("https://discordapp.com/channels/1/2/3", (1, 2, 3)),
        ("https://ptb.discord.com/channels/10/20/30", (10, 20, 30)),
        ("https://canary.discord.com/channels/10/20/30", (10, 20, 30)),
        ("look here https://discord.com/channels/5/6/7 thanks", (5, 6, 7)),
    ],
)
def test_parse_message_link_valid(url, expected):
    assert parse_message_link(url) == expected


@pytest.mark.parametrize("url", ["", "not a link", "https://discord.com/channels/5/6", "https://example.com/a/b/c"])
def test_parse_message_link_invalid(url):
    assert parse_message_link(url) is None


def _seed_player(session, discord_id="111"):
    player = Player(slug=f"alice-{discord_id}", discord_id=discord_id, display_name="Alice", active=True)
    session.add(player)
    session.add(MagicSet(code="SOS", name="Secrets of Strixhaven", start_date=date(2026, 4, 21)))
    session.flush()
    return player


def test_get_or_create_player_creates_tokenless_row(session):
    player = get_or_create_player(
        session, discord_id="999", discord_username="newbie", display_name="Newbie", avatar_hash=None,
    )

    assert player.seventeenlands_token is None
    assert player.slug
    assert player.active is True


def test_get_or_create_player_returns_existing(session):
    existing = _seed_player(session, discord_id="111")

    player = get_or_create_player(
        session, discord_id="111", discord_username="alice2", display_name="Alice Renamed", avatar_hash=None,
    )

    assert player.id == existing.id
    assert session.query(Player).count() == 1


def test_upsert_resolves_set_id_from_code(session):
    player = _seed_player(session)

    trophy = upsert_trophy(
        session, player_id=player.id, set_code="SOS", record="3-0", colors="WR",
        platform="MTGO", caption="finally hit it", screenshot_url="https://cdn/x.png",
        source_channel_id="c1", source_message_id="m1", source_url="u1",
    )

    assert trophy.set_id is not None
    assert trophy.caption == "finally hit it"
    assert session.get(MagicSet, trophy.set_id).code == "SOS"


def test_upsert_is_idempotent_per_message(session):
    player = _seed_player(session)
    kwargs = dict(
        player_id=player.id, set_code="SOS", caption=None, screenshot_url=None,
        source_channel_id="c1", source_message_id="m1", source_url="u1",
    )

    upsert_trophy(session, record="3-0", colors="WR", platform="MTGO", **kwargs)
    upsert_trophy(session, record="7-2", colors="UBg", platform="MTGA Mobile", **kwargs)

    rows = session.query(SelfReportedTrophy).all()
    assert len(rows) == 1
    assert (rows[0].record, rows[0].colors, rows[0].platform) == ("7-2", "UBg", "MTGA Mobile")


def test_upsert_distinct_messages_create_distinct_rows(session):
    player = _seed_player(session)

    upsert_trophy(
        session, player_id=player.id, set_code="SOS", record="3-0", colors=None,
        platform="Paper", caption=None, screenshot_url=None,
        source_channel_id="c1", source_message_id="m1", source_url="u1",
    )
    upsert_trophy(
        session, player_id=player.id, set_code="SOS", record="3-1", colors=None,
        platform="Paper", caption=None, screenshot_url=None,
        source_channel_id="c1", source_message_id="m2", source_url="u2",
    )

    assert session.query(SelfReportedTrophy).count() == 2


def test_upsert_timestamps_with_supplied_event_time(session):
    player = _seed_player(session)
    posted = datetime(2026, 4, 22, 15, 30, tzinfo=timezone.utc)

    trophy = upsert_trophy(
        session, player_id=player.id, set_code="SOS", record="3-0", colors=None,
        platform="MTGO", caption=None, screenshot_url=None, reported_at=posted,
        source_channel_id="c1", source_message_id="m1", source_url="u1",
    )

    assert trophy.reported_at == posted


def test_upsert_unknown_set_code_leaves_set_id_null(session):
    player = _seed_player(session)

    trophy = upsert_trophy(
        session, player_id=player.id, set_code="ZZZ", record="3-0", colors=None,
        platform="MTGA Mobile", caption=None, screenshot_url=None,
        source_channel_id="c1", source_message_id="m9", source_url="u9",
    )

    assert trophy.set_id is None
    assert trophy.set_code == "ZZZ"
