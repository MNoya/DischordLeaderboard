from datetime import datetime

from bot.services.ping_roles import (
    EARLY_POD_ROLE_NAME,
    LATE_POD_ROLE_NAME,
    WEEKEND_POD_ROLE_NAME,
    auto_grant_spec_for_event,
    blurb_with_time,
    button_custom_id,
)
from bot.services.pod_schedule import POD_DRAFTERS_ROLE_NAME, SCHEDULE_TZ


def test_auto_grant_maps_timed_weekday_slots_to_their_roles():
    thursday = datetime(2026, 6, 11, 14, 0, tzinfo=SCHEDULE_TZ)
    wednesday = datetime(2026, 6, 10, 20, 0, tzinfo=SCHEDULE_TZ)
    saturday = datetime(2026, 6, 13, 15, 0, tzinfo=SCHEDULE_TZ)
    off_grid = datetime(2026, 6, 9, 11, 0, tzinfo=SCHEDULE_TZ)

    assert auto_grant_spec_for_event(thursday).name == EARLY_POD_ROLE_NAME
    assert auto_grant_spec_for_event(wednesday).name == LATE_POD_ROLE_NAME
    assert auto_grant_spec_for_event(saturday).name == WEEKEND_POD_ROLE_NAME
    assert auto_grant_spec_for_event(off_grid) is None


def test_button_custom_id_is_a_stable_slug():
    assert button_custom_id(_spec_named(POD_DRAFTERS_ROLE_NAME)) == "role-toggle-pod-drafters"


def test_blurb_with_time_renders_the_next_occurrence_for_slot_roles():
    blurb = blurb_with_time(_spec_named(EARLY_POD_ROLE_NAME))

    assert "<t:" in blurb and ":F>" in blurb


def _spec_named(name):
    from bot.services.ping_roles import PING_ROLES

    for spec in PING_ROLES:
        if spec.name == name:
            return spec
    raise AssertionError(f"no spec named {name}")
