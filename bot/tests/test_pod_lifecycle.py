import asyncio

from bot.services.pod_draft_manager import PodDraftManager


def test_pause_emits_and_sets_flag_when_drafting():
    mgr = _manager()
    mgr.drafting = True

    err = asyncio.run(mgr.pause_draft())

    assert err is None
    assert mgr.draft_paused is True
    assert mgr.sio.emitted == ["pauseDraft"]


def test_pause_rejected_when_not_drafting():
    mgr = _manager()

    err = asyncio.run(mgr.pause_draft())

    assert err is not None
    assert mgr.draft_paused is False
    assert mgr.sio.emitted == []


def test_pause_rejected_when_already_paused():
    mgr = _manager()
    mgr.drafting = True
    mgr.draft_paused = True

    err = asyncio.run(mgr.pause_draft())

    assert err is not None
    assert mgr.sio.emitted == []


def test_pause_rejected_when_disconnected():
    mgr = _manager()
    mgr.drafting = True
    mgr.sio.connected = False

    err = asyncio.run(mgr.pause_draft())

    assert err is not None
    assert mgr.sio.emitted == []


def test_resume_emits_and_clears_flag_when_paused():
    mgr = _manager()
    mgr.drafting = True
    mgr.draft_paused = True

    err = asyncio.run(mgr.resume_draft())

    assert err is None
    assert mgr.draft_paused is False
    assert mgr.sio.emitted == ["resumeDraft"]


def test_resume_rejected_when_not_paused():
    mgr = _manager()
    mgr.drafting = True

    err = asyncio.run(mgr.resume_draft())

    assert err is not None
    assert mgr.sio.emitted == []


def test_end_draft_swallowed_after_restart_stop():
    mgr = _manager()
    mgr.draft_cancelled = True

    asyncio.run(mgr._on_end_draft())

    assert mgr.draft_cancelled is False
    assert mgr.draft_complete is False


def _manager() -> PodDraftManager:
    mgr = PodDraftManager(object(), "evt", "sid", 123, "SOS", 8)
    mgr.sio = _FakeSio()
    return mgr


class _FakeSio:
    def __init__(self, connected: bool = True) -> None:
        self.connected = connected
        self.emitted: list[str] = []

    async def emit(self, event: str, *args, **kwargs) -> None:
        self.emitted.append(event)
