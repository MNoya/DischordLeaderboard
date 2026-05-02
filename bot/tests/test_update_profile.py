from bot.commands.update_profile import process_update_profile
from bot.models import Player


VALID = "10c0f8918a2b4fa7b230448caee0b2ca"
OTHER = "0011223344556677889900112233aabb"


class FakeClient:
    def __init__(self, accept=True):
        self.accept = accept

    def verify_token(self, token):
        return self.accept


def _seed(session, discord_id="111", token=VALID, token_invalid=False):
    p = Player(
        discord_id=discord_id,
        discord_username="alice",
        display_name="Alice",
        seventeenlands_token=token,
        seventeenlands_url=f"https://www.17lands.com/user_history/{token}",
        active=True,
        token_invalid=token_invalid,
    )
    session.add(p)
    session.flush()
    return p


def test_update_profile_not_registered(session):
    result = process_update_profile(session, FakeClient(), discord_id="nope", token_input=VALID)
    assert result.kind == "not_registered"


def test_update_profile_invalid_format(session):
    p = _seed(session, discord_id="111", token=VALID)
    result = process_update_profile(session, FakeClient(), discord_id="111", token_input="garbage")
    assert result.kind == "invalid_format"
    assert result.player_id == p.id


def test_update_profile_rejected_by_17lands(session):
    p = _seed(session, discord_id="111", token=VALID)
    result = process_update_profile(session, FakeClient(accept=False), discord_id="111", token_input=OTHER)
    assert result.kind == "rejected_by_17lands"
    assert p.seventeenlands_token == VALID  # unchanged


def test_update_profile_token_in_use_by_someone_else(session):
    _seed(session, discord_id="111", token=VALID)
    _seed(session, discord_id="222", token=OTHER)

    result = process_update_profile(session, FakeClient(), discord_id="111", token_input=OTHER)
    assert result.kind == "token_in_use"


def test_update_profile_updates_token_and_clears_invalid_flag(session):
    p = _seed(session, discord_id="111", token=VALID, token_invalid=True)

    result = process_update_profile(session, FakeClient(), discord_id="111", token_input=OTHER)

    assert result.kind == "updated"
    session.refresh(p)
    assert p.seventeenlands_token == OTHER
    assert p.seventeenlands_url.endswith(OTHER)
    assert p.token_invalid is False
