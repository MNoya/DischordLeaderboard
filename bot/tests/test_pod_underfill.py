from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from bot.config import settings
from bot.tasks.pod_underfill import _arm_underfill_beats, _nudge_ping_role


ET = ZoneInfo("America/New_York")
WEDNESDAY_LATE = datetime(2026, 6, 24, 20, 0, tzinfo=ET)
WEDNESDAY_OFF_GRID = datetime(2026, 6, 24, 9, 0, tzinfo=ET)
SUNDAY_LATE = datetime(2026, 6, 28, 20, 0, tzinfo=ET)
AIM = 8


class _Role:
    def __init__(self, name: str) -> None:
        self.name = name


class _Guild:
    def __init__(self, roles: list[_Role]) -> None:
        self.roles = roles


class _Channel:
    def __init__(self, guild: _Guild) -> None:
        self.guild = guild


def _channel(*role_names: str) -> _Channel:
    return _Channel(_Guild([_Role(name) for name in role_names]))


def test_nudge_ping_role_silent_when_check_hour_not_in_ping_set(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_ping_hours", "1")

    role = _nudge_ping_role(_channel("Late Pod"), WEDNESDAY_LATE, 7, AIM, hours_before=3)

    assert role is None


def test_nudge_ping_role_silent_when_far_from_the_aim(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_ping_hours", "1")
    monkeypatch.setattr(settings, "pod_underfill_ping_close_gap", 2)

    role = _nudge_ping_role(_channel("Late Pod"), WEDNESDAY_LATE, 4, AIM, hours_before=1)

    assert role is None


def test_nudge_ping_role_silent_when_already_at_the_aim(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_ping_hours", "1")

    role = _nudge_ping_role(_channel("Late Pod"), WEDNESDAY_LATE, 8, AIM, hours_before=1)

    assert role is None


def test_nudge_ping_role_resolves_slot_role_when_close_to_the_aim(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_ping_hours", "1")
    monkeypatch.setattr(settings, "pod_underfill_ping_close_gap", 2)
    channel = _channel("Late Pod")

    needs_one = _nudge_ping_role(channel, WEDNESDAY_LATE, 7, AIM, hours_before=1)
    needs_two = _nudge_ping_role(channel, WEDNESDAY_LATE, 6, AIM, hours_before=1)

    assert needs_one is not None and needs_one.name == "Late Pod"
    assert needs_two is not None and needs_two.name == "Late Pod"


def test_nudge_ping_role_honours_the_slot_aim(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_ping_hours", "1")
    monkeypatch.setattr(settings, "pod_underfill_ping_close_gap", 2)
    channel = _channel("Late Pod")

    close_to_fire = _nudge_ping_role(channel, WEDNESDAY_LATE, 4, aim=6, hours_before=1)
    far_from_fire = _nudge_ping_role(channel, WEDNESDAY_LATE, 3, aim=6, hours_before=1)

    assert close_to_fire is not None and close_to_fire.name == "Late Pod"
    assert far_from_fire is None


def test_nudge_ping_role_resolves_weekend_bucket_roles(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_ping_hours", "1")
    monkeypatch.setattr(settings, "pod_underfill_ping_close_gap", 2)

    role = _nudge_ping_role(_channel("Weekend Late Pod"), SUNDAY_LATE, 7, AIM, hours_before=1)

    assert role is not None and role.name == "Weekend Late Pod"


def test_nudge_ping_role_silent_for_an_off_grid_event(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_ping_hours", "1")

    role = _nudge_ping_role(_channel("Late Pod"), WEDNESDAY_OFF_GRID, 7, AIM, hours_before=1)

    assert role is None


class _FakeScheduler:
    def __init__(self) -> None:
        self.jobs: list[dict] = []
        self.removed: list[str] = []

    def add_job(self, fire, trigger, run_date, args, id, replace_existing):
        self.jobs.append({"id": id, "run_date": run_date, "args": args})

    def remove_job(self, job_id: str) -> None:
        self.removed.append(job_id)


async def _fire(key, hours, resurface):
    pass


@pytest.mark.parametrize(
    ("event_in_h", "created_ago_h", "expected_beats", "expected_catch_up"),
    [
        (5.0, 1.0, [3, 2, 1], None),
        (2.5, 4.0, [2, 1], 3),
        (1.5, 2.5, [1], 2),
        (0.5, 2.0, [], 1),
        (0.5, 0.1, [], None),
    ],
)
def test_arm_underfill_beats_arms_future_beats_and_catches_up_downtime_misses(
    monkeypatch, event_in_h, created_ago_h, expected_beats, expected_catch_up,
):
    monkeypatch.setattr(settings, "pod_underfill_check_hours", "3,2,1")
    scheduler = _FakeScheduler()
    now = datetime.now(timezone.utc)
    event_time = now + timedelta(hours=event_in_h)
    created_at = now - timedelta(hours=created_ago_h)

    _arm_underfill_beats(scheduler, _fire, "sig1", "pod-slot-underfill", event_time, created_at)

    beats = [job["args"][1] for job in scheduler.jobs if "catchup" not in job["id"]]
    catch_ups = [job["args"][1] for job in scheduler.jobs if "catchup" in job["id"]]
    assert beats == expected_beats
    assert catch_ups == ([expected_catch_up] if expected_catch_up is not None else [])


def test_arm_underfill_beats_marks_only_the_min_offset_as_resurface(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_check_hours", "3,2,1")
    scheduler = _FakeScheduler()
    now = datetime.now(timezone.utc)

    _arm_underfill_beats(scheduler, _fire, "sig1", "pod-underfill", now + timedelta(hours=5), now)

    resurface_by_hours = {job["args"][1]: job["args"][2] for job in scheduler.jobs}
    assert resurface_by_hours == {3: False, 2: False, 1: True}


def test_arm_underfill_beats_catch_up_inherits_the_missed_beats_resurface(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_check_hours", "3,2,1")
    scheduler = _FakeScheduler()
    now = datetime.now(timezone.utc)

    _arm_underfill_beats(
        scheduler, _fire, "sig1", "pod-underfill",
        now + timedelta(minutes=30), now - timedelta(hours=2),
    )

    (catch_up,) = scheduler.jobs
    assert "catchup" in catch_up["id"]
    assert catch_up["args"][1] == 1
    assert catch_up["args"][2] is True


def test_arm_underfill_beats_never_catches_up_a_past_event(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_check_hours", "3,2,1")
    scheduler = _FakeScheduler()
    now = datetime.now(timezone.utc)

    _arm_underfill_beats(
        scheduler, _fire, "sig1", "pod-underfill",
        now - timedelta(minutes=5), now - timedelta(hours=6),
    )

    assert scheduler.jobs == []
