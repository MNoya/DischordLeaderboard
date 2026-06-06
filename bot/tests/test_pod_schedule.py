from datetime import date, datetime, timezone

import pytest

from bot.services.pod_schedule import (
    GENERIC_FLAVOR,
    MONDAY_KIND_CHAMPIONSHIP_WEEK,
    MONDAY_KIND_NORMAL,
    MONDAY_KIND_RELEASE_WEEK,
    SCHEDULE_TZ,
    build_create_command,
    build_underfill_message,
    event_description,
    format_clock,
    monday_blurb,
    monday_kind,
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


def test_flavor_pools_fall_back_to_generic_and_wrap():
    blurbs = GENERIC_FLAVOR.monday_blurbs
    descriptions = GENERIC_FLAVOR.event_descriptions

    assert monday_blurb("ZZZ", 0) == blurbs[0]
    assert monday_blurb("ZZZ", len(blurbs)) == blurbs[0]
    assert monday_blurb("MSH", 1) == blurbs[1]
    assert event_description("ZZZ", len(descriptions) + 2) == descriptions[2]


def test_build_create_command():
    slot = datetime(2026, 6, 24, 20, 0, tzinfo=SCHEDULE_TZ)

    command = build_create_command("MSH", 1, slot, "Assemble.")

    assert command == (
        "/create title:MSH Pod Draft #1 - June 24 "
        "datetime:June 24 8pm ET "
        "channel:#🚀-pod-draft-coordination "
        "on_create_mentions:@Any Pronouns "
        "description:Assemble."
    )


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


def test_underfill_message_pings_role_and_counts_missing_players():
    event_time = datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

    body = build_underfill_message(1234, 5, 8, event_time, "https://discord.com/channels/1/2/3")

    unix = int(event_time.timestamp())
    assert body == (
        f"<@&1234> 3 more players needed for the pod draft on <t:{unix}:F> (<t:{unix}:R>) — "
        "5/8 in so far. RSVP: https://discord.com/channels/1/2/3"
    )


def test_underfill_message_singular_and_no_role():
    event_time = datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

    body = build_underfill_message(None, 7, 8, event_time, "url")

    assert body.startswith("1 more player needed")
