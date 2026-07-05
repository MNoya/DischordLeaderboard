from datetime import date, datetime, timedelta, timezone

import pytest

from bot.services.pod_schedule import (
    CREATE_DESCRIPTION,
    CREATE_LEAD_HOURS,
    CREATE_MENTIONS_EURO,
    MONDAY_KIND_CHAMPIONSHIP_WEEK,
    MONDAY_KIND_NORMAL,
    MONDAY_KIND_RELEASE_WEEK,
    MONDAY_KIND_SEASON_OVER,
    SCHEDULE_TZ,
    SLOT_EMOJI_SATURDAY,
    WEEKLY_SLOTS,
    build_create_command,
    build_underfill_message,
    compose_monday_message,
    compose_schedule_message,
    create_command_send_time,
    format_clock,
    highest_event_number,
    monday_blurb,
    monday_kind,
    next_release_after,
    next_unscheduled_slots,
    short_event_name,
    release_unix,
    slot_for_event_time,
    slot_instant,
    slots_for_week,
    upcoming_slots,
    week_index_for,
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


def test_upcoming_slots_from_midweek_rolls_into_next_week_in_order():
    friday = datetime(2026, 12, 11, 10, 0, tzinfo=SCHEDULE_TZ)

    slots = upcoming_slots(friday)

    assert slots == [
        datetime(2026, 12, 12, 15, 0, tzinfo=SCHEDULE_TZ),
        datetime(2026, 12, 16, 20, 0, tzinfo=SCHEDULE_TZ),
        datetime(2026, 12, 17, 14, 0, tzinfo=SCHEDULE_TZ),
    ]


def test_upcoming_slots_from_monday_returns_that_weeks_slots():
    monday = datetime(2026, 12, 7, 0, 0, tzinfo=SCHEDULE_TZ)

    slots = upcoming_slots(monday)

    assert slots == slots_for_week(date(2026, 12, 7))


def test_compose_schedule_message_starts_at_the_next_upcoming_slot():
    friday = datetime(2026, 12, 11, 10, 0, tzinfo=SCHEDULE_TZ)

    message = compose_schedule_message(friday, "MSH")

    saturday = int(datetime(2026, 12, 12, 15, 0, tzinfo=SCHEDULE_TZ).timestamp())
    next_wednesday = int(datetime(2026, 12, 16, 20, 0, tzinfo=SCHEDULE_TZ).timestamp())
    assert f"{SLOT_EMOJI_SATURDAY} <t:{saturday}:F>" in message
    assert message.index(f"<t:{saturday}:") < message.index(f"<t:{next_wednesday}:")


def test_compose_schedule_message_does_not_advertise_a_paused_release_week():
    friday_before_release = datetime(2026, 8, 7, 10, 0, tzinfo=SCHEDULE_TZ)

    message = compose_schedule_message(friday_before_release, "MSH")

    this_saturday = int(datetime(2026, 8, 8, 15, 0, tzinfo=SCHEDULE_TZ).timestamp())
    release_week_wednesday = int(datetime(2026, 8, 12, 20, 0, tzinfo=SCHEDULE_TZ).timestamp())
    assert f"<t:{this_saturday}:F>" in message
    assert f"<t:{release_week_wednesday}:" not in message


def test_next_unscheduled_slots_skips_already_scheduled_and_rolls_forward():
    wednesday = datetime(2026, 12, 9, 9, 0, tzinfo=SCHEDULE_TZ)
    scheduled = {
        slot_instant(datetime(2026, 12, 9, 20, 0, tzinfo=SCHEDULE_TZ)),
        slot_instant(datetime(2026, 12, 10, 14, 0, tzinfo=SCHEDULE_TZ)),
    }

    slots = next_unscheduled_slots(wednesday, scheduled)

    assert slots == [
        datetime(2026, 12, 12, 15, 0, tzinfo=SCHEDULE_TZ),
        datetime(2026, 12, 16, 20, 0, tzinfo=SCHEDULE_TZ),
        datetime(2026, 12, 17, 14, 0, tzinfo=SCHEDULE_TZ),
    ]


def test_next_unscheduled_slots_stops_before_a_paused_release_week():
    friday_before_release = datetime(2026, 8, 7, 9, 0, tzinfo=SCHEDULE_TZ)

    slots = next_unscheduled_slots(friday_before_release, set())

    assert slots == [datetime(2026, 8, 8, 15, 0, tzinfo=SCHEDULE_TZ)]


@pytest.mark.parametrize(
    ("monday", "expected_kind", "expected_code"),
    [
        (date(2026, 6, 1), MONDAY_KIND_NORMAL, None),
        (date(2026, 6, 8), MONDAY_KIND_CHAMPIONSHIP_WEEK, "MSH"),
        (date(2026, 6, 15), MONDAY_KIND_SEASON_OVER, "MSH"),
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


def test_week_index_counts_weeks_from_the_release_week_monday():
    assert week_index_for("MSH", date(2026, 6, 22)) == 0
    assert week_index_for("MSH", date(2026, 6, 29)) == 1
    assert week_index_for("MSH", date(2026, 7, 6)) == 2
    assert week_index_for("SOS", date(2026, 6, 8)) == 7


def test_week_index_for_unknown_set_falls_back_to_iso_week():
    assert week_index_for("ZZZ", date(2026, 6, 8)) == date(2026, 6, 8).isocalendar().week


def test_monday_blurb_is_empty_when_no_pool_is_curated():
    assert monday_blurb("ZZZ", 0) == ""
    assert monday_blurb("MSH", 3) == ""


def test_compose_monday_message_normal_week_lists_both_slots_without_a_blurb():
    monday = date(2026, 6, 1)

    message = compose_monday_message(monday, "SOS")

    assert not message.startswith("\n")
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
    message = compose_monday_message(date(2026, 6, 8), "SOS")

    assert "SOS" in message
    assert "Marvel Super Heroes" in message


def test_compose_monday_message_season_over_counts_down_to_the_next_drop():
    monday = date(2026, 6, 15)

    message = compose_monday_message(monday, "SOS")

    release = next_release_after(monday)
    assert "SOS" in message
    assert release.name in message
    assert str(release_unix(release)) in message


def test_build_create_command_interpolates_event_data():
    slot = datetime(2026, 6, 24, 20, 0, tzinfo=SCHEDULE_TZ)

    command = build_create_command("MSH", 5, slot, CREATE_DESCRIPTION)

    assert command.startswith("/create ")
    assert "MSH" in command
    assert "#5" in command
    assert "June 24" in command
    assert "8pm" in command


def test_build_create_command_carries_the_year_in_the_datetime_not_the_title():
    slot = datetime(2026, 6, 24, 20, 0, tzinfo=SCHEDULE_TZ)

    command = build_create_command("MSH", 5, slot, CREATE_DESCRIPTION)

    title, _, datetime_part = command.partition("datetime:")
    assert "2026" in datetime_part
    assert "2026" not in title


def test_build_create_command_uses_supplied_mentions():
    slot = datetime(2026, 6, 25, 14, 0, tzinfo=SCHEDULE_TZ)

    command = build_create_command("MSH", 6, slot, CREATE_DESCRIPTION, CREATE_MENTIONS_EURO)

    assert CREATE_MENTIONS_EURO in command


@pytest.mark.parametrize(
    ("event_time", "expected_weekday"),
    [
        (datetime(2026, 6, 10, 20, 0, tzinfo=SCHEDULE_TZ), 2),
        (datetime(2026, 6, 11, 14, 0, tzinfo=SCHEDULE_TZ), 3),
        (datetime(2026, 6, 13, 15, 0, tzinfo=SCHEDULE_TZ), 5),
        (datetime(2026, 6, 13, 20, 0, tzinfo=SCHEDULE_TZ), None),
    ],
)
def test_slot_for_event_time_maps_to_its_slot(event_time, expected_weekday):
    slot = slot_for_event_time(event_time)

    assert (slot.weekday if slot else None) == expected_weekday


def test_slot_for_event_time_converts_utc_to_eastern():
    eastern = datetime(2026, 6, 11, 14, 0, tzinfo=SCHEDULE_TZ)

    slot = slot_for_event_time(eastern.astimezone(timezone.utc))

    assert slot is not None and slot.weekday == 3


def test_off_grid_time_has_no_slot():
    assert slot_for_event_time(datetime(2026, 6, 9, 11, 0, tzinfo=SCHEDULE_TZ)) is None


def test_americas_create_command_sends_monday_noon_eastern():
    monday = date(2026, 7, 6)
    slot = WEEKLY_SLOTS[0]

    send_at = create_command_send_time(slot, monday)

    assert send_at == datetime(2026, 7, 6, 12, 0, tzinfo=SCHEDULE_TZ)


def test_euro_create_commands_send_a_fixed_lead_before_the_event():
    monday = date(2026, 7, 6)

    for slot, start in zip(WEEKLY_SLOTS[1:], slots_for_week(monday)[1:]):
        assert create_command_send_time(slot, monday) == start - timedelta(hours=CREATE_LEAD_HOURS)


def test_compose_monday_message_marks_each_slot_with_its_emoji():
    monday = date(2026, 6, 1)

    message = compose_monday_message(monday, "SOS")

    assert "• " not in message
    for slot, start in zip(WEEKLY_SLOTS, slots_for_week(monday)):
        assert f"{slot.emoji} <t:{int(start.timestamp())}:F>" in message


def test_highest_event_number_takes_the_max_and_ignores_unnumbered_names():
    names = ["SOS Pod Draft #3 - May 15", "SOS Pod Draft #5 - May 22", "SOS Pod Draft - aborted"]

    assert highest_event_number(names) == 5


def test_highest_event_number_defaults_to_zero_with_no_numbers():
    assert highest_event_number([]) == 0
    assert highest_event_number(["Pod Draft - no number"]) == 0


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


def test_underfill_message_interpolates_name_count_time_and_signup_link():
    event_time = datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)
    jump_url = "https://discord.com/channels/1/2/3"

    body = build_underfill_message("FIN Pod Draft #1 - Jun 24", 5, 8, event_time, jump_url)

    assert "FIN Pod Draft #1" in body
    assert "Jun 24" not in body
    assert "3 more players" in body
    assert f"<t:{int(event_time.timestamp())}:R>" in body
    assert ":F>" not in body
    assert f"]({jump_url})" in body


def test_underfill_message_never_pings_a_role():
    event_time = datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

    body = build_underfill_message("Pod", 7, 8, event_time, "url")

    assert "<@&" not in body
    assert "1 more player" in body


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
