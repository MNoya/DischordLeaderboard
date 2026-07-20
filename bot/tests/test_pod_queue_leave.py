from datetime import date, datetime, timezone

import pytest

from bot.models import PodSignal, PodSignalMember
from bot.services import pod_signals
from bot.services.pod_launch import (
    LEAVE_CANCELLED,
    LEAVE_GONE,
    LEAVE_LEFT,
    queue_member_count,
    resolve_last_leave,
)

MESSAGE_ID = "9001"


@pytest.fixture
def open_queue(session):
    signal = PodSignal(
        kind=pod_signals.KIND_QUEUE, bucket=pod_signals.QUEUE_BUCKET, guild_id="g1",
        channel_id="c1", message_id=MESSAGE_ID, signal_date=date(2026, 7, 16),
        status=pod_signals.STATUS_OPEN, set_code="MH3", opened_by="u1",
        created_at=datetime(2026, 7, 16, 9, 0, tzinfo=timezone.utc),
    )
    session.add(signal)
    session.flush()
    return signal


def _add_member(session, signal_id, user_id, name):
    session.add(PodSignalMember(signal_id=signal_id, discord_user_id=user_id, display_name=name))
    session.flush()


def test_sole_member_leave_cancels_the_queue(session, open_queue):
    _add_member(session, open_queue.id, "u1", "Jace Beleren")

    resolution = resolve_last_leave(session, MESSAGE_ID, "u1")

    assert resolution.outcome == LEAVE_CANCELLED
    assert open_queue.status == pod_signals.STATUS_EXPIRED
    assert resolution.set_code == "MH3"


def test_leave_when_others_joined_keeps_the_queue_open(session, open_queue):
    _add_member(session, open_queue.id, "u1", "Jace Beleren")
    _add_member(session, open_queue.id, "u2", "Liliana Vess")

    resolution = resolve_last_leave(session, MESSAGE_ID, "u1")

    assert resolution.outcome == LEAVE_LEFT
    assert open_queue.status == pod_signals.STATUS_OPEN
    assert resolution.names == ["Liliana Vess"]


def test_leave_on_already_closed_queue_reports_gone(session, open_queue):
    open_queue.status = pod_signals.STATUS_EXPIRED
    session.flush()

    resolution = resolve_last_leave(session, MESSAGE_ID, "u1")

    assert resolution.outcome == LEAVE_GONE


def test_member_count_reports_membership_and_size(session, open_queue):
    _add_member(session, open_queue.id, "u1", "Jace Beleren")
    _add_member(session, open_queue.id, "u2", "Liliana Vess")

    assert queue_member_count(session, MESSAGE_ID, "u1") == (True, 2)
    assert queue_member_count(session, MESSAGE_ID, "u3") == (False, 2)


def test_member_count_none_when_signal_missing(session, open_queue):
    assert queue_member_count(session, "does-not-exist", "u1") is None
