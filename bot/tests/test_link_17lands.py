"""LeaderboardChoicePrompt membership-state transitions for /link-17lands."""
from __future__ import annotations

import discord

import bot.commands.link_17lands as mod
from bot.commands.link_17lands import LeaderboardChoicePrompt
from bot.models import Player


VALID_TOKEN = "10c0f8918a2b4fa7b230448caee0b2ca"


def _seed(session, *, active, opt_in):
    player = Player(
        slug="daniel",
        discord_id="132",
        discord_username="daniel",
        display_name="Daniel",
        seventeenlands_token=VALID_TOKEN,
        active=active,
        leaderboard_opt_in=opt_in,
    )
    session.add(player)
    session.commit()
    return player


def _session_factory(session):
    class _Ctx:
        def __enter__(self):
            return session

        def __exit__(self, *exc):
            return False

    return lambda: _Ctx()


def _prompt(session, player, *, currently_in):
    return LeaderboardChoicePrompt(bot=None, user_id="132", player_id=player.id, currently_in=currently_in)


def test_join_reactivates_and_opts_in(session, monkeypatch):
    player = _seed(session, active=False, opt_in=False)
    monkeypatch.setattr(mod, "SessionLocal", _session_factory(session))

    name = _prompt(session, player, currently_in=False)._set_membership(active=True, opt_in=True)

    session.refresh(player)
    assert name == "Daniel"
    assert player.active is True
    assert player.leaderboard_opt_in is True


def test_leave_opts_out_but_keeps_active(session, monkeypatch):
    player = _seed(session, active=True, opt_in=True)
    monkeypatch.setattr(mod, "SessionLocal", _session_factory(session))

    _prompt(session, player, currently_in=True)._set_membership(opt_in=False)

    session.refresh(player)
    assert player.leaderboard_opt_in is False
    assert player.active is True


def test_off_board_offers_join_path(session):
    player = _seed(session, active=False, opt_in=False)

    buttons = _prompt(session, player, currently_in=False).children

    assert buttons[0].style == discord.ButtonStyle.success


def test_on_board_offers_leave_path(session):
    player = _seed(session, active=True, opt_in=True)

    buttons = _prompt(session, player, currently_in=True).children

    assert buttons[0].style == discord.ButtonStyle.danger
