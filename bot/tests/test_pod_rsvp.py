from datetime import datetime, timedelta, timezone

import pytest

from bot.commands.pod_rsvp import parse_new_time
from bot.models import PodDraftEvent, PodSignal
from bot.services import pod_signals
from bot.services.pod_launch import _committed_slot, _event_id_for_slot, set_rsvp
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


def _pod_event(session, slot_time: datetime, *, sesh: bool = False) -> str:
    event = PodDraftEvent(
        event_date=slot_time.date(), event_time=slot_time, set_code="TST",
        name="TST Pod Draft #1", draftmancer_session="s1", discord_thread_id="tid-1",
        socket_status="pending", sesh_message_id="sesh-1" if sesh else None,
    )
    session.add(event)
    session.flush()
    return event.id


def _scheduled_pod(session, slot_time: datetime, yes: list[str]) -> str:
    event_id = _pod_event(session, slot_time)
    signal = PodSignal(
        kind=pod_signals.KIND_SCHEDULED, bucket=pod_signals.SCHEDULED_BUCKET, guild_id="1",
        channel_id="2", message_id="card-1", signal_date=slot_time.date(), slot_time=slot_time,
        status=pod_signals.STATUS_FIRED, event_id=event_id,
    )
    session.add(signal)
    session.flush()
    for i, name in enumerate(yes):
        set_rsvp(session, "card-1", f"u{i}", name, pod_signals.RSVP_YES)
    session.flush()
    return event_id


def test_reflection_binds_a_slot_to_the_pod_at_its_instant(session):
    slot_time = datetime.now(timezone.utc) + timedelta(days=1)
    event_id = _scheduled_pod(session, slot_time, [])

    assert _event_id_for_slot(session, slot_time) == event_id


def test_reflection_binds_a_sesh_pod_with_no_signal(session):
    slot_time = datetime.now(timezone.utc) + timedelta(days=1)
    event_id = _pod_event(session, slot_time, sesh=True)

    assert _event_id_for_slot(session, slot_time) == event_id


def test_reflection_ignores_a_pod_at_a_different_time(session):
    slot_time = datetime.now(timezone.utc) + timedelta(days=1)
    _scheduled_pod(session, slot_time, [])

    off_grid = slot_time + timedelta(hours=1)
    assert _event_id_for_slot(session, off_grid) is None


def test_committed_slot_reads_count_and_thread_off_the_event(session):
    slot_time = datetime.now(timezone.utc) + timedelta(days=1)
    event_id = _scheduled_pod(session, slot_time, ["Nissa Revane", "Chandra Nalaar"])

    slot = _committed_slot(session, "AFTERNOON", event_id)

    assert slot.committed
    assert slot.count == 2
    assert slot.thread_id == "tid-1"
    assert slot.names == []


def test_committed_slot_for_a_sesh_pod_shows_no_count(session):
    slot_time = datetime.now(timezone.utc) + timedelta(days=1)
    event_id = _pod_event(session, slot_time, sesh=True)

    slot = _committed_slot(session, "LATE", event_id)

    assert slot.committed
    assert slot.count == 0
    assert slot.thread_id == "tid-1"


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


REF = datetime(2026, 7, 14, 12, 0, tzinfo=SCHEDULE_TZ)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Today 10pm ET", datetime(2026, 7, 14, 22, 0, tzinfo=SCHEDULE_TZ)),
        ("tonight 8pm", datetime(2026, 7, 14, 20, 0, tzinfo=SCHEDULE_TZ)),
        ("tomorrow 8:30pm", datetime(2026, 7, 15, 20, 30, tzinfo=SCHEDULE_TZ)),
        ("fri 9pm", datetime(2026, 7, 17, 21, 0, tzinfo=SCHEDULE_TZ)),
        ("friday at 20:00", datetime(2026, 7, 17, 20, 0, tzinfo=SCHEDULE_TZ)),
        ("next tuesday 8pm", datetime(2026, 7, 21, 20, 0, tzinfo=SCHEDULE_TZ)),
        ("10pm", datetime(2026, 7, 14, 22, 0, tzinfo=SCHEDULE_TZ)),
        ("8am", datetime(2026, 7, 15, 8, 0, tzinfo=SCHEDULE_TZ)),
        ("12pm", datetime(2026, 7, 14, 12, 0, tzinfo=SCHEDULE_TZ) + timedelta(days=1)),
        ("today 8am", None),
        ("half past nine", None),
    ],
)
def test_parse_new_time_natural_language(raw, expected):
    assert parse_new_time(raw, REF, REF) == expected


def test_parse_new_time_accepts_a_pasted_discord_timestamp():
    future = datetime(2026, 7, 18, 21, 0, tzinfo=SCHEDULE_TZ)

    parsed = parse_new_time(f"<t:{int(future.timestamp())}:F>", REF, REF)

    assert parsed == future


def test_parse_new_time_rejects_a_past_discord_timestamp():
    past = datetime(2020, 1, 1, 12, 0, tzinfo=SCHEDULE_TZ)

    assert parse_new_time(f"<t:{int(past.timestamp())}:F>", REF, REF) is None
