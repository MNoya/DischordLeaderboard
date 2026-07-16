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


def test_nudge_ping_role_silent_when_one_short_gate_on_and_count_is_not_one_short(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_ping_hours", "1")
    monkeypatch.setattr(settings, "pod_underfill_ping_one_short_only", True)
    channel = _Channel(_Guild([_Role("Late Pod")]))

    role = _nudge_ping_role(channel, WEDNESDAY_LATE, yes_count=4, hours_before=1)

    assert role is None


def test_nudge_ping_role_resolves_slot_role_when_one_short_at_a_ping_hour(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_ping_hours", "1")
    channel = _Channel(_Guild([_Role("Late Pod")]))

    role = _nudge_ping_role(channel, WEDNESDAY_LATE, yes_count=7, hours_before=1)

    assert role is not None
    assert role.name == "Late Pod"


def test_nudge_ping_role_silent_for_an_off_grid_event(monkeypatch):
    monkeypatch.setattr(settings, "pod_underfill_ping_hours", "1")
    channel = _Channel(_Guild([_Role("Late Pod")]))

    role = _nudge_ping_role(channel, WEDNESDAY_OFF_GRID, yes_count=7, hours_before=1)

    assert role is None
