from datetime import date, datetime, timezone

import pytest

from bot.services import pod_format_interest as fi
from bot.services.pod_schedule import (
    SCHEDULE_TZ,
    build_underfill_message,
    highest_event_number,
    short_event_name,
    slots_for_week,
)


def test_slots_for_week_returns_wednesday_thursday_and_saturday_eastern():
    slots = slots_for_week(date(2026, 6, 8))

    assert slots == [
        datetime(2026, 6, 10, 20, 0, tzinfo=SCHEDULE_TZ),
        datetime(2026, 6, 11, 14, 0, tzinfo=SCHEDULE_TZ),
        datetime(2026, 6, 13, 15, 0, tzinfo=SCHEDULE_TZ),
    ]
    assert all(slot.utcoffset().total_seconds() == -4 * 3600 for slot in slots)


def test_slots_for_week_tracks_dst_end():
    slots = slots_for_week(date(2026, 11, 2))

    assert all(slot.utcoffset().total_seconds() == -5 * 3600 for slot in slots)


def test_highest_event_number_takes_the_max_and_ignores_unnumbered_names():
    names = ["SOS Pod Draft #3 - May 15", "SOS Pod Draft #5 - May 22", "SOS Pod Draft - aborted"]

    assert highest_event_number(names) == 5


def test_highest_event_number_defaults_to_zero_with_no_numbers():
    assert highest_event_number([]) == 0
    assert highest_event_number(["Pod Draft - no number"]) == 0


def test_underfill_message_interpolates_name_count_time_and_signup_link():
    event_time = datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)
    jump_url = "https://discord.com/channels/1/2/3"

    body = build_underfill_message("FIN Pod Draft #1 - Jun 24", 4, 8, event_time, jump_url)

    assert "FIN Pod Draft #1" in body
    assert "Jun 24" not in body
    assert "4 more players" in body
    assert f"<t:{int(event_time.timestamp())}:R>" in body
    assert ":F>" not in body
    assert f"]({jump_url})" in body


def test_underfill_message_never_pings_a_role():
    event_time = datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

    body = build_underfill_message("Pod", 7, 8, event_time, "url")

    assert "<@&" not in body


def test_underfill_message_one_short_uses_singular_plain_count():
    event_time = datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

    body = build_underfill_message("Pod", 7, 8, event_time, "url")

    assert "1 more player" in body
    assert "1 more players" not in body


def test_underfill_message_at_the_aim_shows_ready_and_keeps_the_signup_link():
    event_time = datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)
    jump_url = "https://discord.com/channels/1/2/3"

    body = build_underfill_message("FIN Pod Draft #1 - Jun 24", 8, 8, event_time, jump_url)

    assert "more player" not in body
    assert "ready" in body.lower()
    assert f"]({jump_url})" in body


def test_underfill_message_past_the_aim_still_reads_ready_not_a_negative_count():
    event_time = datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

    body = build_underfill_message("Pod", 9, 8, event_time, "url")

    assert "-1" not in body
    assert "ready" in body.lower()


def test_underfill_message_branches_by_yes_plus_maybe_without_crashing():
    event_time = datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)
    interests = [(fi.LATEST,)] * 7 + [(fi.FLASHBACK,)] * 3 + [(fi.LATEST, fi.FLASHBACK)] * 4 + [()] * 2

    plain = build_underfill_message("Pod", 9, 8, event_time, "url", maybe_count=6)
    overflow = build_underfill_message(
        "Pod", 10, 8, event_time, "url", maybe_count=6, composition=fi.composition(interests),
    )
    overflow_no_signal = build_underfill_message(
        "Pod", 10, 8, event_time, "url", maybe_count=6, composition=fi.composition([None] * 16),
    )

    assert plain and overflow and overflow_no_signal
    assert overflow != plain
    assert overflow_no_signal != overflow


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("MSH Pod Draft #2 - Jun 25", "MSH Pod Draft #2"),
        ("SOS Pod Draft #3 - May 5", "SOS Pod Draft #3"),
        ("MSH Pod Draft #2", "MSH Pod Draft #2"),
        ("Throwback Cube Night", "Throwback Cube Night"),
    ],
)
def test_short_event_name_strips_trailing_date(name, expected):
    assert short_event_name(name) == expected
