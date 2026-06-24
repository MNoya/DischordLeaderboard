import asyncio
from dataclasses import dataclass

import pytest

from bot.config import settings
from bot.listeners import sesh_listener
from bot.listeners.sesh_listener import SeshListener

POD_CHANNEL_ID = 555


@dataclass
class _DeletePayload:
    channel_id: int
    message_id: int


@pytest.fixture
def listener(monkeypatch):
    monkeypatch.setattr(settings, "pod_draft_channel_id", POD_CHANNEL_ID)
    return SeshListener(bot=object())


@pytest.fixture
def cancel_calls(monkeypatch):
    calls = []

    async def fake_cancel(event_id, *, actor):
        calls.append((event_id, actor))

    monkeypatch.setattr(sesh_listener, "cancel_pod_event", fake_cancel)
    return calls


def _patch_lookup(monkeypatch, result):
    monkeypatch.setattr(sesh_listener, "event_for_sesh_message_sync", lambda _mid: result)


def test_deleted_sesh_message_cancels_pending_pod(listener, cancel_calls, monkeypatch):
    _patch_lookup(monkeypatch, ("evt-1", "pending"))

    asyncio.run(listener.on_raw_message_delete(_DeletePayload(POD_CHANNEL_ID, 42)))

    assert cancel_calls == [("evt-1", "sesh cancellation")]


def test_deleted_message_in_other_channel_is_ignored(listener, cancel_calls, monkeypatch):
    looked_up = []
    monkeypatch.setattr(
        sesh_listener, "event_for_sesh_message_sync", lambda mid: looked_up.append(mid),
    )

    asyncio.run(listener.on_raw_message_delete(_DeletePayload(POD_CHANNEL_ID + 1, 42)))

    assert looked_up == []
    assert cancel_calls == []


def test_deleted_message_with_no_tracked_event_is_ignored(listener, cancel_calls, monkeypatch):
    _patch_lookup(monkeypatch, None)

    asyncio.run(listener.on_raw_message_delete(_DeletePayload(POD_CHANNEL_ID, 42)))

    assert cancel_calls == []


@pytest.mark.parametrize("status", ["draft_done", "complete"])
def test_finalized_pod_is_kept_when_its_sesh_message_is_deleted(listener, cancel_calls, monkeypatch, status):
    _patch_lookup(monkeypatch, ("evt-1", status))

    asyncio.run(listener.on_raw_message_delete(_DeletePayload(POD_CHANNEL_ID, 42)))

    assert cancel_calls == []
