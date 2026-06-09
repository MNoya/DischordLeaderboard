from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from bot.config import settings
from bot.models import MagicSet, Player, PodDraftEvent, PodDraftParticipant
from bot.services.pod_drafts import (
    build_mock_session,
    capture_deck_screenshot,
    finalize_mock_event,
    record_mock_event,
)
from bot.services.pod_format_select import format_options
from bot.sets import ACTIVE_SET_CODE, is_known_set, upcoming_sets


def _seed_player(session, discord_id="901", username="cap", display_name="Cap"):
    player = Player(
        slug=f"{username}-{discord_id}",
        discord_id=discord_id,
        discord_username=username,
        display_name=display_name,
        seventeenlands_token="t" * 32,
        active=True,
    )
    session.add(player)
    session.flush()
    return player


def test_upcoming_sets_and_known_set():
    upcoming_codes = [s.code for s in upcoming_sets()]

    assert ACTIVE_SET_CODE not in upcoming_codes
    assert "MSH" in upcoming_codes
    assert is_known_set("msh") and not is_known_set("zzz")


def test_format_options_offers_active_and_upcoming_sets():
    values = [opt.value for opt in format_options(None)]

    assert values[0] == ACTIVE_SET_CODE
    assert "MSH" in values


def test_build_mock_session_numbers_per_set(session, monkeypatch):
    monkeypatch.setattr(settings, "pod_draft_session_prefix", "LLU")

    first_id, first_n = build_mock_session(session, "MSH")
    record_mock_event(
        session, set_code="MSH",
        event_time=datetime(2026, 6, 23, tzinfo=timezone.utc), discord_thread_id="t1",
    )
    second_id, second_n = build_mock_session(session, "MSH")
    other_id, other_n = build_mock_session(session, "SOS")

    assert (first_id, first_n) == ("LLU-MSH-Mock-1", 1)
    assert (second_id, second_n) == ("LLU-MSH-Mock-2", 2)
    assert (other_id, other_n) == ("LLU-SOS-Mock-1", 1)


def test_record_mock_event_fields(session, monkeypatch):
    monkeypatch.setattr(settings, "pod_draft_session_prefix", "LLU")
    session.add(MagicSet(code="MSH", name="Marvel Super Heroes", start_date=date(2026, 6, 23)))
    session.flush()

    event = record_mock_event(
        session, set_code="msh",
        event_time=datetime(2026, 6, 23, 18, tzinfo=timezone.utc), discord_thread_id="thread-1",
    )

    assert event.kind == "mock"
    assert event.set_code == "MSH"
    assert event.sesh_message_id is None
    assert event.name == "MSH Mock Draft 1"
    assert event.draftmancer_session == "LLU-MSH-Mock-1"
    assert event.set_id is not None


def test_finalize_mock_event_marks_complete(session, monkeypatch):
    monkeypatch.setattr(settings, "pod_draft_session_prefix", "LLU")
    event = record_mock_event(
        session, set_code="MSH",
        event_time=datetime(2026, 6, 23, tzinfo=timezone.utc), discord_thread_id="t1",
    )

    finalized = finalize_mock_event(session, event.id)

    assert finalized is event
    assert event.socket_status == "complete"
    assert event.finalized_at is not None


def test_manager_imports_finalize_mock_event():
    from bot.services import pod_draft_manager, pod_drafts

    assert pod_draft_manager.finalize_mock_event is pod_drafts.finalize_mock_event


@pytest.mark.parametrize(
    "socket_status, captured",
    [("pending", False), ("connected", False), ("draft_done", True), ("complete", True)],
)
def test_mock_screenshot_gate_opens_on_draft_completion(session, socket_status, captured):
    player = _seed_player(session)
    event = PodDraftEvent(
        event_date=date(2026, 6, 23), event_time=datetime(2026, 6, 23, tzinfo=timezone.utc),
        set_code="MSH", name="MSH Mock Draft 1", draftmancer_session="LLU-MSH-Mock-1",
        discord_thread_id="mock-thread", sesh_message_id=None, socket_status=socket_status,
        kind="mock", current_round=None,
    )
    session.add(event)
    session.flush()
    session.add(PodDraftParticipant(event_id=event.id, player_id=player.id, display_name="Cap"))
    session.flush()

    result = capture_deck_screenshot(session, "mock-thread", "901", "https://cdn.test/deck.png", None)

    stored = session.execute(
        select(PodDraftParticipant).where(PodDraftParticipant.event_id == event.id)
    ).scalar_one()
    if captured:
        assert result == event.id
        assert stored.deck_screenshot_url == "https://cdn.test/deck.png"
    else:
        assert result is None
        assert stored.deck_screenshot_url is None
