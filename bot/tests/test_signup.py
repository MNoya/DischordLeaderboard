from __future__ import annotations

from sqlalchemy import select

from bot.commands.signup import check_signup_eligibility, process_signup
from bot.models import Player


VALID_TOKEN = "10c0f8918a2b4fa7b230448caee0b2ca"
OTHER_TOKEN = "abcdef0123456789abcdef0123456789"


class FakeClient:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.calls: list[str] = []

    def verify_token(self, token: str) -> bool:
        self.calls.append(token)
        return self.ok


def test_creates_new_player_when_token_unknown(session):
    client = FakeClient(ok=True)

    result = process_signup(
        session=session,
        client=client,
        discord_id="111",
        discord_username="alice#0001",
        display_name="Alice",
        token_input=f"https://www.17lands.com/user_history/{VALID_TOKEN}",
    )

    assert result.kind == "created"
    rows = session.execute(select(Player)).scalars().all()
    assert len(rows) == 1
    p = rows[0]
    assert p.discord_id == "111"
    assert p.discord_username == "alice#0001"
    assert p.display_name == "Alice"
    assert p.seventeenlands_token == VALID_TOKEN
    assert p.seventeenlands_url == f"https://www.17lands.com/user_history/{VALID_TOKEN}"
    assert p.active is True
    assert client.calls == [VALID_TOKEN]


def test_links_seeded_player_with_null_discord_fields(session):
    seeded = Player(
        slug="legacyalice",
        display_name="LegacyAlice",
        seventeenlands_token=VALID_TOKEN,
        seventeenlands_url=f"https://www.17lands.com/user_history/{VALID_TOKEN}",
        active=True,
    )
    session.add(seeded)
    session.commit()

    result = process_signup(
        session=session,
        client=FakeClient(ok=True),
        discord_id="222",
        discord_username="alice#0001",
        display_name="Alice",
        token_input=VALID_TOKEN,
    )

    assert result.kind == "linked"
    rows = session.execute(select(Player)).scalars().all()
    assert len(rows) == 1
    p = rows[0]
    assert p.id == seeded.id
    assert p.discord_id == "222"
    assert p.discord_username == "alice#0001"
    # display_name is preserved from the seed — we don't overwrite it on link
    assert p.display_name == "LegacyAlice"
    assert p.token_invalid is False
    assert p.active is True


def test_invalid_token_format_returns_kind_and_writes_nothing(session):
    client = FakeClient(ok=True)

    result = process_signup(
        session=session,
        client=client,
        discord_id="333",
        discord_username="bob#0002",
        display_name="Bob",
        token_input="this is definitely not a token",
    )

    assert result.kind == "invalid_format"
    assert session.execute(select(Player)).scalars().all() == []
    assert client.calls == []


def test_rejected_by_17lands_writes_nothing(session):
    client = FakeClient(ok=False)

    result = process_signup(
        session=session,
        client=client,
        discord_id="444",
        discord_username="carol#0003",
        display_name="Carol",
        token_input=VALID_TOKEN,
    )

    assert result.kind == "rejected_by_17lands"
    assert session.execute(select(Player)).scalars().all() == []
    assert client.calls == [VALID_TOKEN]


def test_token_already_linked_to_another_discord_user(session):
    other = Player(
        slug="someone",
        discord_id="999",
        discord_username="someone#0009",
        display_name="Someone",
        seventeenlands_token=VALID_TOKEN,
        seventeenlands_url=f"https://www.17lands.com/user_history/{VALID_TOKEN}",
        active=True,
    )
    session.add(other)
    session.commit()

    result = process_signup(
        session=session,
        client=FakeClient(ok=True),
        discord_id="555",
        discord_username="dave#0004",
        display_name="Dave",
        token_input=VALID_TOKEN,
    )

    assert result.kind == "token_in_use"
    p = session.execute(select(Player).where(Player.id == other.id)).scalar_one()
    assert p.discord_id == "999"
    assert p.discord_username == "someone#0009"
    assert session.execute(select(Player)).scalars().all() == [p]


def test_already_signed_up_short_circuits(session):
    me = Player(
        slug="eve",
        discord_id="666",
        discord_username="eve#0005",
        display_name="Eve",
        seventeenlands_token=OTHER_TOKEN,
        seventeenlands_url=f"https://www.17lands.com/user_history/{OTHER_TOKEN}",
        active=True,
    )
    session.add(me)
    session.commit()

    client = FakeClient(ok=True)
    result = process_signup(
        session=session,
        client=client,
        discord_id="666",
        discord_username="eve#0005",
        display_name="Eve",
        token_input=VALID_TOKEN,
    )

    assert result.kind == "already_signed_up"
    # 17lands was never consulted because we short-circuit before token validation
    assert client.calls == []
    rows = session.execute(select(Player)).scalars().all()
    assert len(rows) == 1
    assert rows[0].seventeenlands_token == OTHER_TOKEN


def _seed(session, discord_id, token, active=True):
    p = Player(
        slug=f"x-{discord_id}",
        discord_id=discord_id,
        discord_username="x",
        display_name="X",
        seventeenlands_token=token,
        seventeenlands_url=f"https://www.17lands.com/user_history/{token}",
        active=active,
    )
    session.add(p)
    session.commit()
    return p


def test_check_signup_fresh_user(session):
    check = check_signup_eligibility(session, "999")
    assert check.kind == "fresh"
    assert check.player_id is None


def test_check_signup_already_active(session):
    p = _seed(session, "111", VALID_TOKEN, active=True)
    check = check_signup_eligibility(session, "111")
    assert check.kind == "already_signed_up"
    assert check.player_id == p.id
    session.refresh(p)
    assert p.active is True


def test_check_signup_reactivates_signed_out_player(session):
    p = _seed(session, "111", VALID_TOKEN, active=False)
    check = check_signup_eligibility(session, "111")
    assert check.kind == "reactivated"
    assert check.player_id == p.id
    session.refresh(p)
    assert p.active is True
