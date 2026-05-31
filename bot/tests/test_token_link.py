from __future__ import annotations

from sqlalchemy import select

from bot.models import Player
from bot.services.token_link import link_token

VALID_TOKEN = "10c0f8918a2b4fa7b230448caee0b2ca"
OTHER_TOKEN = "abcdef0123456789abcdef0123456789"


class FakeClient:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.calls: list[str] = []

    def verify_token(self, token: str) -> bool:
        self.calls.append(token)
        return self.ok


def _seed(session, discord_id, token=None, leaderboard_opt_in=False, active=True):
    p = Player(
        slug=f"x-{discord_id}",
        discord_id=discord_id,
        discord_username="x",
        display_name="X",
        seventeenlands_token=token,
        active=active,
        leaderboard_opt_in=leaderboard_opt_in,
    )
    session.add(p)
    session.commit()
    return p


def test_link_creates_player_with_requested_opt_in(session):
    client = FakeClient()
    result = link_token(session, client, "111", "alice#1", "Alice", VALID_TOKEN, opt_in=False)
    assert result.kind == "linked"
    assert result.created is True
    p = session.execute(select(Player).where(Player.discord_id == "111")).scalar_one()
    assert p.seventeenlands_token == VALID_TOKEN
    assert p.leaderboard_opt_in is False
    assert p.active is True


def test_link_sets_token_on_existing_pod_only_player(session):
    pod_player = _seed(session, "111", token=None, leaderboard_opt_in=False)
    client = FakeClient()
    result = link_token(session, client, "111", "alice#1", "Alice", VALID_TOKEN, opt_in=True)
    assert result.kind == "linked"
    assert result.created is False
    assert result.player_id == pod_player.id
    session.refresh(pod_player)
    assert pod_player.seventeenlands_token == VALID_TOKEN
    assert pod_player.leaderboard_opt_in is True


def test_link_clears_token_invalid_flag(session):
    p = _seed(session, "111", token=None)
    p.token_invalid = True
    session.commit()
    link_token(session, FakeClient(), "111", "alice#1", "Alice", VALID_TOKEN, opt_in=False)
    session.refresh(p)
    assert p.token_invalid is False


def test_link_invalid_format_writes_nothing(session):
    client = FakeClient()
    result = link_token(session, client, "111", "alice#1", "Alice", "not-a-token", opt_in=True)
    assert result.kind == "invalid_format"
    assert session.execute(select(Player)).scalars().all() == []
    assert client.calls == []


def test_link_rejected_by_17lands_writes_nothing(session):
    client = FakeClient(ok=False)
    result = link_token(session, client, "111", "alice#1", "Alice", VALID_TOKEN, opt_in=True)
    assert result.kind == "rejected_by_17lands"
    assert session.execute(select(Player)).scalars().all() == []


def test_link_token_already_owned_by_another_account(session):
    owner = _seed(session, "999", token=VALID_TOKEN, leaderboard_opt_in=True)
    result = link_token(session, FakeClient(), "111", "alice#1", "Alice", VALID_TOKEN, opt_in=True)
    assert result.kind == "token_in_use"
    assert result.player_id == owner.id
    assert session.execute(select(Player)).scalars().all() == [owner]


def test_relinking_own_token_is_allowed(session):
    p = _seed(session, "111", token=VALID_TOKEN, leaderboard_opt_in=True)
    result = link_token(session, FakeClient(), "111", "alice#1", "Alice", VALID_TOKEN, opt_in=True)
    assert result.kind == "linked"
    assert result.player_id == p.id


def test_relink_preserves_existing_opt_in(session):
    p = _seed(session, "111", token=VALID_TOKEN, leaderboard_opt_in=False)
    result = link_token(session, FakeClient(), "111", "alice#1", "Alice", OTHER_TOKEN, opt_in=True)
    assert result.kind == "linked"
    assert result.relinked is True
    assert result.created is False
    session.refresh(p)
    assert p.seventeenlands_token == OTHER_TOKEN
    assert p.leaderboard_opt_in is False


def test_first_link_on_tokenless_row_is_not_a_relink(session):
    p = _seed(session, "111", token=None, leaderboard_opt_in=False)
    result = link_token(session, FakeClient(), "111", "alice#1", "Alice", VALID_TOKEN, opt_in=True)
    assert result.relinked is False
    session.refresh(p)
    assert p.leaderboard_opt_in is True
