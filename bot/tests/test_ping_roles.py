import asyncio
from datetime import datetime
from types import SimpleNamespace

from bot.services.ping_roles import (
    EARLY_POD_ROLE_NAME,
    LATE_POD_ROLE_NAME,
    WEEKEND_POD_ROLE_NAME,
    _first_welcome_for,
    auto_grant_spec_for_event,
    blurb_with_time,
    button_custom_id,
    forget_welcome,
)
from bot.services.pod_roles import consume_bot_umbrella_grant, grant_role
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


def test_blurb_with_time_pairs_a_weekday_slot_with_its_local_time():
    blurb = blurb_with_time(_spec_named(EARLY_POD_ROLE_NAME))

    assert "<t:" in blurb and ":t>" in blurb


def test_blurb_with_time_lists_all_three_weekend_slots():
    blurb = blurb_with_time(_spec_named(WEEKEND_POD_ROLE_NAME))

    assert blurb.count("<t:") == 3


def test_first_welcome_fires_once_until_forgotten():
    member_id = 90909

    assert _first_welcome_for(member_id) is True
    assert _first_welcome_for(member_id) is False
    forget_welcome(member_id)
    assert _first_welcome_for(member_id) is True


def test_consume_bot_umbrella_grant_is_a_one_shot_flag():
    grant_role_marks_umbrella_grant()

    assert consume_bot_umbrella_grant(4242) is True
    assert consume_bot_umbrella_grant(4242) is False


def test_bot_mediated_umbrella_grant_is_marked_so_the_listener_skips_it():
    member = _FakeMember(4343)
    umbrella = SimpleNamespace(name=POD_DRAFTERS_ROLE_NAME)

    asyncio.run(grant_role(member, umbrella))

    assert consume_bot_umbrella_grant(4343) is True


def test_slot_role_grant_leaves_the_umbrella_unmarked():
    member = _FakeMember(4444)
    slot_role = SimpleNamespace(name=EARLY_POD_ROLE_NAME)

    asyncio.run(grant_role(member, slot_role))

    assert consume_bot_umbrella_grant(4444) is False


def grant_role_marks_umbrella_grant():
    member = _FakeMember(4242)
    umbrella = SimpleNamespace(name=POD_DRAFTERS_ROLE_NAME)
    asyncio.run(grant_role(member, umbrella))


class _FakeMember:
    def __init__(self, member_id):
        self.id = member_id
        self.roles = []

    async def add_roles(self, *roles, reason=None):
        self.roles.extend(roles)


def _spec_named(name):
    from bot.services.ping_roles import PING_ROLES

    for spec in PING_ROLES:
        if spec.name == name:
            return spec
    raise AssertionError(f"no spec named {name}")
