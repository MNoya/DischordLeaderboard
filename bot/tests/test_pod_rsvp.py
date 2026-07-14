from datetime import datetime, timedelta, timezone

import pytest

from bot.commands.pod_rsvp import parse_new_time
from bot.models import PodDraftEvent, PodSignal
from bot.services import pod_signals
from bot.services.pod_launch import _fired_slot_thread_id, set_card_yes, set_rsvp
from bot.services.pod_schedule import SCHEDULE_TZ


MESSAGE_ID = "9001"


@pytest.fixture
def scheduled_signal(session):
    signal = PodSignal(
        kind=pod_signals.KIND_SCHEDULED,
        bucket=pod_signals.SCHEDULED_BUCKET,
        guild_id="1",
        channel_id="2",
        message_id=MESSAGE_ID,
        signal_date=datetime.now(SCHEDULE_TZ).date(),
        slot_time=datetime.now(timezone.utc) + timedelta(days=2),
        status=pod_signals.STATUS_FIRED,
    )
    session.add(signal)
    session.flush()
    return signal


def test_first_yes_click_joins(session, scheduled_signal):
    result = set_rsvp(session, MESSAGE_ID, "u1", "Nissa Revane", pod_signals.RSVP_YES)

    assert result.joined
    assert result.rsvp == pod_signals.RSVP_YES
    assert result.rosters[pod_signals.RSVP_YES] == ["Nissa Revane"]
    assert result.state.count == 1


def test_clicking_another_state_moves_the_member(session, scheduled_signal):
    set_rsvp(session, MESSAGE_ID, "u1", "Nissa Revane", pod_signals.RSVP_YES)

    result = set_rsvp(session, MESSAGE_ID, "u1", "Nissa Revane", pod_signals.RSVP_MAYBE)

    assert not result.joined
    assert result.rsvp == pod_signals.RSVP_MAYBE
    assert result.rosters[pod_signals.RSVP_YES] == []
    assert result.rosters[pod_signals.RSVP_MAYBE] == ["Nissa Revane"]


def test_clicking_the_held_state_removes_the_rsvp(session, scheduled_signal):
    set_rsvp(session, MESSAGE_ID, "u1", "Nissa Revane", pod_signals.RSVP_YES)

    result = set_rsvp(session, MESSAGE_ID, "u1", "Nissa Revane", pod_signals.RSVP_YES)

    assert result.rsvp is None
    assert not result.joined
    assert all(names == [] for names in result.rosters.values())


def test_moving_from_maybe_to_yes_counts_as_joining(session, scheduled_signal):
    set_rsvp(session, MESSAGE_ID, "u1", "Nissa Revane", pod_signals.RSVP_MAYBE)

    result = set_rsvp(session, MESSAGE_ID, "u1", "Nissa Revane", pod_signals.RSVP_YES)

    assert result.joined


def test_a_no_click_never_joins(session, scheduled_signal):
    result = set_rsvp(session, MESSAGE_ID, "u1", "Nissa Revane", pod_signals.RSVP_NO)

    assert not result.joined
    assert result.rosters[pod_signals.RSVP_NO] == ["Nissa Revane"]
    assert result.state.count == 0


def test_expired_signal_refuses_without_mutating(session, scheduled_signal):
    scheduled_signal.status = pod_signals.STATUS_EXPIRED
    session.flush()

    result = set_rsvp(session, MESSAGE_ID, "u1", "Nissa Revane", pod_signals.RSVP_YES)

    assert result.closed
    assert all(names == [] for names in result.rosters.values())


def test_unknown_message_returns_none(session, scheduled_signal):
    assert set_rsvp(session, "555", "u1", "Nissa Revane", pod_signals.RSVP_YES) is None


def test_mirror_message_resolves_the_same_signal(session, scheduled_signal):
    scheduled_signal.thread_message_id = "9002"
    session.flush()

    set_rsvp(session, MESSAGE_ID, "u1", "Nissa Revane", pod_signals.RSVP_YES)
    result = set_rsvp(session, "9002", "u2", "Chandra Nalaar", pod_signals.RSVP_YES)

    assert result is not None
    assert result.rosters[pod_signals.RSVP_YES] == ["Nissa Revane", "Chandra Nalaar"]


def test_fired_slot_links_to_the_scheduled_pod_thread(session):
    slot_time = datetime.now(timezone.utc) + timedelta(days=1)
    event = PodDraftEvent(
        event_date=slot_time.date(), event_time=slot_time, set_code="TST",
        name="TST Pod Draft #1", draftmancer_session="s1", discord_thread_id="tid-1",
        socket_status="pending",
    )
    session.add(event)
    session.flush()
    session.add(PodSignal(
        kind=pod_signals.KIND_SCHEDULED, bucket=pod_signals.SCHEDULED_BUCKET, guild_id="1",
        channel_id="2", message_id="card-1", signal_date=slot_time.date(), slot_time=slot_time,
        status=pod_signals.STATUS_FIRED, event_id=event.id,
    ))
    poll_signal = PodSignal(
        kind=pod_signals.KIND_POLL, bucket="EARLY", guild_id="1", channel_id="2",
        message_id="poll-1", signal_date=slot_time.date(), slot_time=slot_time,
        status=pod_signals.STATUS_FIRED,
    )
    session.add(poll_signal)
    session.flush()

    assert _fired_slot_thread_id(session, poll_signal) == "tid-1"


def test_open_slot_has_no_thread(session):
    poll_signal = PodSignal(
        kind=pod_signals.KIND_POLL, bucket="EARLY", guild_id="1", channel_id="2",
        message_id="poll-1", signal_date=datetime.now(timezone.utc).date(),
        slot_time=datetime.now(timezone.utc) + timedelta(days=1), status=pod_signals.STATUS_OPEN,
    )
    session.add(poll_signal)
    session.flush()

    assert _fired_slot_thread_id(session, poll_signal) is None


def _scheduled_pod_with_event(session) -> str:
    slot_time = datetime.now(timezone.utc) + timedelta(days=1)
    event = PodDraftEvent(
        event_date=slot_time.date(), event_time=slot_time, set_code="TST",
        name="TST Pod Draft #1", draftmancer_session="s1", discord_thread_id="tid-1",
        socket_status="pending",
    )
    session.add(event)
    session.flush()
    session.add(PodSignal(
        kind=pod_signals.KIND_SCHEDULED, bucket=pod_signals.SCHEDULED_BUCKET, guild_id="1",
        channel_id="2", message_id="card-1", signal_date=slot_time.date(), slot_time=slot_time,
        status=pod_signals.STATUS_FIRED, event_id=event.id,
    ))
    session.flush()
    return event.id


def test_set_card_yes_is_idempotent(session):
    event_id = _scheduled_pod_with_event(session)
    set_card_yes(session, event_id, "u1", "Nissa Revane", joining=True)

    rosters = set_card_yes(session, event_id, "u1", "Nissa Revane", joining=True)

    assert rosters[pod_signals.RSVP_YES] == ["Nissa Revane"]


def test_set_card_yes_removes_on_leave(session):
    event_id = _scheduled_pod_with_event(session)
    set_card_yes(session, event_id, "u1", "Nissa Revane", joining=True)

    rosters = set_card_yes(session, event_id, "u1", "Nissa Revane", joining=False)

    assert rosters[pod_signals.RSVP_YES] == []


def test_set_card_yes_promotes_a_maybe_to_yes(session):
    event_id = _scheduled_pod_with_event(session)
    set_rsvp(session, "card-1", "u1", "Nissa Revane", pod_signals.RSVP_MAYBE)

    rosters = set_card_yes(session, event_id, "u1", "Nissa Revane", joining=True)

    assert rosters[pod_signals.RSVP_YES] == ["Nissa Revane"]
    assert rosters[pod_signals.RSVP_MAYBE] == []


def test_set_card_yes_without_a_scheduled_signal_returns_none(session):
    assert set_card_yes(session, "no-event", "u1", "Nissa Revane", joining=True) is None


CURRENT = datetime(2026, 7, 15, 20, 0, tzinfo=SCHEDULE_TZ)
NOW = datetime(2026, 7, 14, 12, 0, tzinfo=SCHEDULE_TZ)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("+2h", CURRENT + timedelta(hours=2)),
        ("+30m", CURRENT + timedelta(minutes=30)),
        ("+2h30m", CURRENT + timedelta(hours=2, minutes=30)),
        ("21:00", datetime(2026, 7, 15, 21, 0, tzinfo=SCHEDULE_TZ)),
        ("2026-07-18 21:00", datetime(2026, 7, 18, 21, 0, tzinfo=SCHEDULE_TZ)),
        ("half past nine", None),
        ("+", None),
        ("2020-01-01 12:00", None),
    ],
)
def test_parse_new_time(raw, expected):
    assert parse_new_time(raw, CURRENT, NOW) == expected


def test_parse_new_time_refuses_a_past_result():
    late_now = CURRENT + timedelta(hours=3)

    assert parse_new_time("+2h", CURRENT, late_now) is None
