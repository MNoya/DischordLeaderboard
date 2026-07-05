import asyncio

from bot.config import settings
from bot.services.pod_draft_manager import PodDraftManager


def test_posts_voice_link_once_at_half_table():
    mgr = _manager()
    channel = _Channel(settings.pod_draft_voice_channel_name)
    thread = _thread([channel])

    asyncio.run(mgr._maybe_post_voice_link(_classified(4), thread))
    asyncio.run(mgr._maybe_post_voice_link(_classified(6), thread))

    assert thread.sent == [channel.jump_url]


def test_no_voice_link_below_half():
    mgr = _manager()
    thread = _thread([_Channel(settings.pod_draft_voice_channel_name)])

    asyncio.run(mgr._maybe_post_voice_link(_classified(3), thread))

    assert thread.sent == []


def test_voice_link_skips_and_latches_when_channel_absent():
    mgr = _manager()
    thread = _thread([])

    asyncio.run(mgr._maybe_post_voice_link(_classified(4), thread))

    assert thread.sent == []
    assert mgr._voice_link_posted is True


def _manager() -> PodDraftManager:
    return PodDraftManager(object(), "evt", "sid", 123, "SOS", 8)


def _classified(n: int) -> list[tuple[str, str]]:
    return [(f"a{i}", f"d{i}") for i in range(n)]


class _Channel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.jump_url = f"https://discord.com/channels/1/{name}"


class _Guild:
    def __init__(self, voice_channels: list) -> None:
        self.voice_channels = voice_channels


class _Thread:
    def __init__(self, guild: _Guild) -> None:
        self.guild = guild
        self.sent: list[str] = []

    async def send(self, content: str) -> None:
        self.sent.append(content)


def _thread(voice_channels: list) -> _Thread:
    return _Thread(_Guild(voice_channels))
