from datetime import date, datetime, timezone

import pytest

from bot.services.pod_schedule import (
    GENERIC_MONDAY_BLURBS,
    MONDAY_KIND_CHAMPIONSHIP_WEEK,
    MONDAY_KIND_NORMAL,
    MONDAY_KIND_RELEASE_WEEK,
    SCHEDULE_TZ,
    build_create_command,
    build_underfill_message,
    compose_monday_message,
    format_clock,
    monday_blurb,
    monday_kind,
    next_release_after,
    release_unix,
    slots_for_week,
    week_index_for,
)


def test_slots_for_week_returns_wednesday_and_thursday_eastern():
    slots = slots_for_week(date(2026, 6, 8))

    assert slots == [
        datetime(2026, 6, 10, 20, 0, tzinfo=SCHEDULE_TZ),
        datetime(2026, 6, 11, 14, 0, tzinfo=SCHEDULE_TZ),
    ]
    assert all(slot.utcoffset().total_seconds() == -4 * 3600 for slot in slots)


def test_slots_for_week_tracks_dst_end():
    slots = slots_for_week(date(2026, 11, 2))

    assert all(slot.utcoffset().total_seconds() == -5 * 3600 for slot in slots)


@pytest.mark.parametrize(
    ("monday", "expected_kind", "expected_code"),
    [
        (date(2026, 6, 8), MONDAY_KIND_NORMAL, None),
        (date(2026, 6, 15), MONDAY_KIND_CHAMPIONSHIP_WEEK, "MSH"),
        (date(2026, 6, 22), MONDAY_KIND_RELEASE_WEEK, "MSH"),
        (date(2026, 6, 29), MONDAY_KIND_NORMAL, None),
        (date(2026, 8, 10), MONDAY_KIND_RELEASE_WEEK, "HOB"),
        (date(2026, 11, 9), MONDAY_KIND_RELEASE_WEEK, "TRE"),
        (date(2026, 12, 7), MONDAY_KIND_NORMAL, None),
    ],
)
def test_monday_kind(monday, expected_kind, expected_code):
    kind, release = monday_kind(monday)

    assert kind == expected_kind
    if expected_code is None:
        assert kind == MONDAY_KIND_NORMAL
    else:
        assert release.code == expected_code


def test_week_index_counts_weeks_since_set_start():
    assert week_index_for("SOS", date(2026, 4, 27)) == 0
    assert week_index_for("SOS", date(2026, 6, 8)) == 6


def test_week_index_for_unknown_set_falls_back_to_iso_week():
    assert week_index_for("ZZZ", date(2026, 6, 8)) == date(2026, 6, 8).isocalendar().week


def test_monday_blurbs_fall_back_to_generic_and_wrap():
    assert monday_blurb("ZZZ", 0) == GENERIC_MONDAY_BLURBS[0]
    assert monday_blurb("ZZZ", len(GENERIC_MONDAY_BLURBS)) == GENERIC_MONDAY_BLURBS[0]
    assert monday_blurb("MSH", 1) == GENERIC_MONDAY_BLURBS[1]


def test_compose_monday_message_normal_week_opens_with_the_blurb_and_lists_both_slots():
    monday = date(2026, 6, 8)

    message = compose_monday_message(monday, "SOS")

    expected_blurb = monday_blurb("SOS", week_index_for("SOS", monday))
    assert message.split("\n\n")[0] == expected_blurb
    assert "SOS" in message
    for slot in slots_for_week(monday):
        assert f"<t:{int(slot.timestamp())}:F>" in message


def test_compose_monday_message_release_week_counts_down_to_the_drop():
    monday = date(2026, 6, 22)

    message = compose_monday_message(monday, "SOS")

    release = next_release_after(monday)
    assert release.name in message
    assert str(release_unix(release)) in message


def test_compose_monday_message_championship_week_names_both_sets():
    message = compose_monday_message(date(2026, 6, 15), "SOS")

    assert "SOS" in message
    assert "Marvel Super Heroes" in message


def test_build_create_command_interpolates_event_data():
    slot = datetime(2026, 6, 24, 20, 0, tzinfo=SCHEDULE_TZ)

    command = build_create_command("MSH", 5, slot)

    assert command.startswith("/create ")
    assert "MSH" in command
    assert "#5" in command
    assert "June 24" in command
    assert "8pm" in command


@pytest.mark.parametrize(
    ("slot", "expected"),
    [
        (datetime(2026, 6, 24, 20, 0, tzinfo=SCHEDULE_TZ), "8pm"),
        (datetime(2026, 6, 25, 14, 0, tzinfo=SCHEDULE_TZ), "2pm"),
        (datetime(2026, 6, 25, 9, 30, tzinfo=SCHEDULE_TZ), "9:30am"),
    ],
)
def test_format_clock(slot, expected):
    assert format_clock(slot) == expected


def test_underfill_message_interpolates_role_count_time_and_link():
    event_time = datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)
    jump_url = "https://discord.com/channels/1/2/3"

    body = build_underfill_message(1234, 5, 8, event_time, jump_url)

    assert "<@&1234>" in body
    assert "3 more" in body
    assert f"<t:{int(event_time.timestamp())}:" in body
    assert jump_url in body


def test_underfill_message_without_role_skips_the_mention():
    event_time = datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

    body = build_underfill_message(None, 7, 8, event_time, "url")

    assert "<@&" not in body
    assert "1 more" in body
