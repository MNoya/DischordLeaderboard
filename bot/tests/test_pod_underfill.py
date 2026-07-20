from datetime import datetime
from zoneinfo import ZoneInfo

from bot.config import settings
from bot.tasks.pod_underfill import _nudge_ping_role


ET = ZoneInfo("America/New_York")
WEDNESDAY_LATE = datetime(2026, 6, 24, 20, 0, tzinfo=ET)
WEDNESDAY_OFF_GRID = datetime(2026, 6, 24, 9, 0, tzinfo=ET)


class _Role:
    def __init__(self, name: str) -> None:
        self.name = name


class _Guild:
    def __init__(self, roles: list[_Role]) -> None:
        self.roles = roles


class _Channel:
    def __init__(self, guild: _Guild) -> None:
        self.guild = guild


def test_nudge_ping_role_silent_when_check_hour_not_in_ping_set(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_ping_hours", "1")
    channel = _Channel(_Guild([_Role("Late Pod")]))

    role = _nudge_ping_role(channel, WEDNESDAY_LATE, yes_count=7, hours_before=3)

    assert role is None


def test_nudge_ping_role_silent_when_far_from_the_aim(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_ping_hours", "1")
    monkeypatch.setattr(settings, "pod_underfill_ping_close_gap", 2)
    channel = _Channel(_Guild([_Role("Late Pod")]))

    role = _nudge_ping_role(channel, WEDNESDAY_LATE, yes_count=4, hours_before=1)

    assert role is None


def test_nudge_ping_role_silent_when_already_at_the_aim(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_ping_hours", "1")
    monkeypatch.setattr(settings, "pod_draft_target_players", 8)
    channel = _Channel(_Guild([_Role("Late Pod")]))

    role = _nudge_ping_role(channel, WEDNESDAY_LATE, yes_count=8, hours_before=1)

    assert role is None


def test_nudge_ping_role_resolves_slot_role_when_close_to_the_aim(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_ping_hours", "1")
    monkeypatch.setattr(settings, "pod_draft_target_players", 8)
    monkeypatch.setattr(settings, "pod_underfill_ping_close_gap", 2)
    channel = _Channel(_Guild([_Role("Late Pod")]))

    needs_one = _nudge_ping_role(channel, WEDNESDAY_LATE, yes_count=7, hours_before=1)
    needs_two = _nudge_ping_role(channel, WEDNESDAY_LATE, yes_count=6, hours_before=1)

    assert needs_one is not None and needs_one.name == "Late Pod"
    assert needs_two is not None and needs_two.name == "Late Pod"


def test_nudge_ping_role_silent_for_an_off_grid_event(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_ping_hours", "1")
    channel = _Channel(_Guild([_Role("Late Pod")]))

    role = _nudge_ping_role(channel, WEDNESDAY_OFF_GRID, yes_count=7, hours_before=1)

    assert role is None
