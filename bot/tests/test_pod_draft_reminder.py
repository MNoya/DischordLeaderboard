import asyncio

import discord

from bot.tasks.pod_draft_reminder import _resolve_attendee_names


class _FakeMember:
    def __init__(self, display_name: str) -> None:
        self.display_name = display_name


class _FakeResponse:
    status = 404
    reason = "Not Found"


class _FakeGuild:
    def __init__(self, members: dict[int, _FakeMember]) -> None:
        self._members = members

    def get_member(self, user_id: int) -> _FakeMember | None:
        return self._members.get(user_id)

    async def fetch_member(self, user_id: int) -> _FakeMember:
        raise discord.HTTPException(_FakeResponse(), "unknown member")


def test_resolves_id_and_nick_mentions_to_display_names():
    guild = _FakeGuild({237762740532412416: _FakeMember("Noya")})

    resolved = asyncio.run(
        _resolve_attendee_names(guild, ["<@237762740532412416>", "<@!237762740532412416>"])
    )

    assert resolved == ["Noya", "Noya"]


def test_plain_names_and_unknown_ids_pass_through():
    guild = _FakeGuild({})

    resolved = asyncio.run(_resolve_attendee_names(guild, ["Giant_Tiger", "<@999>"]))

    assert resolved == ["Giant_Tiger", "<@999>"]


def test_resolution_lets_a_mention_dedup_against_the_same_display_name():
    guild = _FakeGuild({237762740532412416: _FakeMember("Noya")})

    resolved = asyncio.run(_resolve_attendee_names(guild, ["Noya", "<@237762740532412416>"]))

    assert {name.casefold() for name in resolved} == {"noya"}
