from datetime import datetime, timedelta, timezone

from bot.commands.pod_queue import _preset_slot_time, _when_options
from bot.services.pod_format_select import WRITE_IN_VALUE


BEFORE_EARLY = datetime(2026, 7, 14, 10, 0, tzinfo=timezone.utc)
AFTER_LATE = datetime(2026, 7, 15, 3, 0, tzinfo=timezone.utc)


def test_preset_slot_time_uses_today_when_slot_is_ahead():
    early = _preset_slot_time("EARLY", BEFORE_EARLY)

    assert early.astimezone(timezone.utc).date() == BEFORE_EARLY.date()
    assert early > BEFORE_EARLY


def test_preset_slot_time_rolls_to_tomorrow_once_slot_has_passed():
    late = _preset_slot_time("LATE", AFTER_LATE)

    assert late > AFTER_LATE
    assert (late - AFTER_LATE) < timedelta(days=1, hours=18)


def test_when_options_default_right_now_when_unscheduled():
    options = _when_options(None, BEFORE_EARLY)

    defaulted = [o for o in options if o.default]
    assert [o.value for o in defaulted] == ["now"]
    assert options[-1].value == WRITE_IN_VALUE
    assert "Schedule for later" in options[-1].label


def test_when_options_defaults_the_selected_preset():
    late = _preset_slot_time("LATE", BEFORE_EARLY)

    options = _when_options(late, BEFORE_EARLY)

    defaulted = [o for o in options if o.default]
    assert [o.value for o in defaulted] == ["LATE"]
    assert options[-1].value == WRITE_IN_VALUE
    assert "Schedule for later" in options[-1].label


def test_when_options_shows_custom_time_as_its_own_defaulted_option():
    custom = datetime(2026, 7, 18, 21, 0, tzinfo=timezone.utc)

    options = _when_options(custom, BEFORE_EARLY)

    defaulted = [o for o in options if o.default]
    assert len(defaulted) == 1
    assert defaulted[0].value == WRITE_IN_VALUE
    assert "Schedule for later" not in defaulted[0].label
