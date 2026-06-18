from datetime import date, datetime, time, timedelta, timezone

import pytest

from bot.commands.event_scribe import build_announcement, select_groups
from bot.services import mtgscribe
from bot.services.format_schedule import (
    ANNOUNCE_COMPETITIVE,
    ANNOUNCE_NONE,
    OPEN_TZ,
    SCHEDULE_PINS,
    already_announced,
    announcement_format,
    channel_name_for,
    newest_set,
    newly_opened,
    next_rotation,
    previous_window_start,
    slugify,
)
from bot.sets import ALL_SETS
from bot.tasks.format_schedule_post import announcement_for


def _event(format_label, group_label, tags, now, start_off, end_off):
    start = now + timedelta(days=start_off)
    end = now + timedelta(days=end_off)
    return mtgscribe.ScribeEvent(
        title=f"{format_label}: {group_label}",
        format_label=format_label,
        group_label=group_label,
        start=start,
        end=end,
        start_local=start.replace(tzinfo=None),
        end_local=end.replace(tzinfo=None),
        tag_slugs=tags,
    )


def _group(label, tags, formats, start, end):
    return mtgscribe.EventGroup(
        label=label,
        formats=list(formats),
        start=start,
        end=end,
        start_local=start.replace(tzinfo=None),
        end_local=end.replace(tzinfo=None),
        flashback="flashback" in tags,
        cube="cube" in tags,
        competitive="qualifier" in tags,
    )


def test_slugify_drops_colons_and_spaces():
    assert slugify("Marvel Super Heroes") == "marvel-super-heroes"
    assert slugify("Avatar: The Last Airbender") == "avatar-the-last-airbender"


def test_newest_set_ignores_permanent_cube():
    newest = newest_set()

    assert newest.code != "CUBE"
    assert all(seed.start_date <= newest.start_date for seed in ALL_SETS if seed.code != "CUBE")


def test_set_channel_follows_newest_set():
    set_pin = next(pin for pin in SCHEDULE_PINS if pin.key == "set")

    assert channel_name_for(set_pin) == slugify(newest_set().name)


def test_set_pin_renders_whole_set_but_announces_competitive_only():
    set_pin = next(pin for pin in SCHEDULE_PINS if pin.key == "set")

    assert set_pin.pin_filters == ()
    assert set_pin.announce_filters == ("competitive",)


def test_named_channels_use_their_fixed_substring():
    cube = next(pin for pin in SCHEDULE_PINS if pin.key == "cube")

    assert channel_name_for(cube) == "cube-talk"


def test_cube_announcement_links_known_list_only():
    now = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    end = now + timedelta(days=6)
    known = _group("Arena Powered Cube", ("cube",), ["Premier Draft"], now, end)
    unknown = _group("Some Kind of new Cube", ("cube",), ["Premier Draft"], now, end)

    assert "cubecobra.com/cube/about/mtgapc" in build_announcement(known, {}, format_word="").description
    assert "cubecobra" not in build_announcement(unknown, {}, format_word="").description


def test_cube_is_announce_only_no_pin():
    cube = next(pin for pin in SCHEDULE_PINS if pin.key == "cube")

    assert cube.maintain_pin is False
    assert cube.announce_filters == ("cube",)


def test_quick_and_flashback_are_separate_pins_in_one_channel():
    quick = next(pin for pin in SCHEDULE_PINS if pin.key == "quick")
    flashback = next(pin for pin in SCHEDULE_PINS if pin.key == "flashback")

    assert channel_name_for(quick) == channel_name_for(flashback) == "quick-or-flashback-draft"
    assert quick.scope_label == "Quick Draft"
    assert flashback.scope_label == "Flashback"
    assert quick.pin_filters == ("quick",)
    assert flashback.pin_filters == ("flashback",)


def test_previous_window_is_the_window_before_the_current_one():
    # Firing at the 08:00 PDT window (15:00 UTC); the previous window is 06:00 PDT the same day
    now = datetime(2026, 6, 16, 15, 0, tzinfo=timezone.utc)

    previous = previous_window_start(now).astimezone(OPEN_TZ)

    assert previous.date() == date(2026, 6, 16)
    assert previous.timetz().replace(tzinfo=None) == time(6, 0)


def test_previous_window_wraps_to_yesterdays_last_window():
    # Firing at the first window of the day (06:00 PDT, 13:00 UTC); the previous is yesterday's 14:00
    now = datetime(2026, 6, 16, 13, 0, tzinfo=timezone.utc)

    previous = previous_window_start(now).astimezone(OPEN_TZ)

    assert previous.date() == date(2026, 6, 15)
    assert previous.timetz().replace(tzinfo=None) == time(14, 0)


def test_newly_opened_keeps_events_opened_since_the_window():
    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=2)
    fresh = _group("Fresh", (), ["Quick Draft"], now - timedelta(minutes=10), now + timedelta(days=7))
    stale = _group("Stale", (), ["Quick Draft"], since - timedelta(hours=1), now + timedelta(days=7))
    future = _group("Future", (), ["Quick Draft"], now + timedelta(hours=1), now + timedelta(days=7))

    assert newly_opened([fresh, stale, future], since, now) == [fresh]


def test_sealed_is_pin_only_and_set_channel_announces_competitive():
    sealed = next(pin for pin in SCHEDULE_PINS if pin.key == "sealed")
    set_pin = next(pin for pin in SCHEDULE_PINS if pin.key == "set")

    assert sealed.announce == ANNOUNCE_NONE
    assert set_pin.announce == ANNOUNCE_COMPETITIVE


def test_announcement_for_dispatches_by_pin_policy():
    now = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    competitive_pin = next(pin for pin in SCHEDULE_PINS if pin.key == "set")
    flashback_pin = next(pin for pin in SCHEDULE_PINS if pin.key == "flashback")
    comp = _group("Marvel Super Heroes", ("qualifier",), ["Qualifier Play-In Bo3"], now, now + timedelta(days=2))
    flash = _group("Aetherdrift", ("flashback",), ["Premier Draft"], now, now + timedelta(days=7))

    _, comp_marker = announcement_for(competitive_pin, comp, [comp], {})
    _, flash_marker = announcement_for(flashback_pin, flash, [flash], {})

    assert comp_marker == "Marvel Super Heroes"
    assert flash_marker == "Flashback"


def test_next_rotation_returns_soonest_after_current():
    now = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    current = _group("Aetherdrift", ("flashback",), ["Premier Draft"], now, now + timedelta(days=7))
    soon = _group("Bloomburrow", ("flashback",), ["Premier Draft"], now + timedelta(days=7), now + timedelta(days=14))
    later = _group("Duskmourn", ("flashback",), ["Premier Draft"], now + timedelta(days=14), now + timedelta(days=21))

    assert next_rotation([current, later, soon], current) is soon


def test_announcement_previews_next_rotation_beyond_the_freshly_opened_slice():
    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=6)
    flashback_pin = next(pin for pin in SCHEDULE_PINS if pin.key == "flashback")
    live = _group("Final Fantasy", ("flashback",), ["Premier Draft"], now - timedelta(hours=1), now + timedelta(days=7))
    later_start = now + timedelta(days=7)
    upcoming = _group("Bloomburrow", ("flashback",), ["Premier Draft"], later_start, later_start + timedelta(days=7))
    scheduled = [live, upcoming]

    fresh = newly_opened(scheduled, since, now)
    embed, _ = announcement_for(flashback_pin, fresh[0], scheduled, {})

    assert fresh == [live]
    assert "Next Up:" in embed.description
    assert "Bloomburrow" in embed.description


def test_next_rotation_is_none_when_nothing_follows():
    now = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    current = _group("Arena Powered Cube", ("cube",), ["Premier Draft"], now, now + timedelta(days=6))

    assert next_rotation([current], current) is None


def test_select_groups_ors_flashback_and_quick():
    now = datetime.now(timezone.utc)
    events = [
        _event("Premier Draft", "Aetherdrift", ("arena", "limited", "flashback", "premier-draft"), now, 1, 8),
        _event("Quick Draft", "Bloomburrow", ("arena", "limited", "quick-draft"), now, 1, 8),
        _event("Premier Draft", "Secrets of Strixhaven", ("arena", "limited", "premier-draft"), now, 1, 8),
    ]

    _, upcoming = select_groups(events, ["flashback", "quick"], apply_horizon=True)

    labels = {group.label for group in upcoming}
    assert labels == {"Aetherdrift", "Bloomburrow"}


def test_select_groups_cube_filter_matches_cube_tag():
    now = datetime.now(timezone.utc)
    events = [
        _event("Premier Draft", "Arena Powered Cube", ("arena", "limited", "premier-draft", "cube"), now, 1, 8),
        _event("Premier Draft", "Secrets of Strixhaven", ("arena", "limited", "premier-draft"), now, 1, 8),
    ]

    _, upcoming = select_groups(events, ["cube"], apply_horizon=True)

    assert [group.label for group in upcoming] == ["Arena Powered Cube"]


@pytest.mark.parametrize("tags,formats,expected", [
    (("flashback",), ["Premier Draft"], "Flashback"),
    (("qualifier",), ["Qualifier Play-In"], "Competitive"),
    (("cube",), ["Premier Draft"], ""),
    ((), ["Quick Draft"], "Quick Draft"),
    ((), ["Sealed"], "Sealed"),
])
def test_announcement_format_keys_on_group_type(tags, formats, expected):
    now = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    group = _group("Set", tags, formats, now, now + timedelta(days=7))

    assert announcement_format(group) == expected


def test_already_announced_matches_word_and_label_together():
    word = "Flashback"
    recent = ["### **Aetherdrift** Flashback is live!\nEnds June 23 (in 7 days)"]

    assert already_announced(recent, word, "Aetherdrift")
    assert not already_announced(recent, word, "Bloomburrow")
    assert not already_announced(recent, "Quick Draft", "Aetherdrift")
