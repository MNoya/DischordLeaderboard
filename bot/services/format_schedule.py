"""Channel routing and selection logic for the daily Scribe-driven format-schedule tick.

Pure data/date logic — no Discord, no DB. The APScheduler wiring and Discord I/O live in
bot/tasks/format_schedule_post.py; the rendering builders are reused from bot/commands/event_scribe.

Each pinned schedule is one filtered /event-scribe view living in a community channel (matched by a
name substring). A channel can host more than one: the quick-or-flashback channel carries a separate
Quick Draft pin and Flashback pin. Limited Competitive events route to the newest set's channel,
which moves with each rotation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import bot.services.mtgscribe as mtgscribe
from bot.sets import ALL_SETS

OPEN_TZ = ZoneInfo("America/Los_Angeles")
ANNOUNCE_WINDOWS: tuple[time, ...] = (time(6, 0), time(8, 0), time(14, 0))
DEDUP_LOOKBACK = timedelta(hours=24)

PERMANENT_CUBE_CODE = "CUBE"


ANNOUNCE_NONE = "none"
ANNOUNCE_ROTATION = "rotation"
ANNOUNCE_COMPETITIVE = "competitive"


@dataclass(frozen=True)
class SchedulePin:
    """A channel's schedule policy. ``maintain_pin`` keeps a pinned /event-scribe fresh: ``pin_filters``
    selects its formats (empty → the whole active set, the set channel) and ``scope_label`` is its title
    scope (``None`` → the active set's name). ``announce_filters`` selects which start-today events get a
    callout — independent of the pin, so the set channel shows the full set but announces competitive
    only, and an announce-only channel (cube) keeps no pin at all."""
    key: str
    channel_name: str | None
    pin_filters: tuple[str, ...]
    scope_label: str | None = None
    announce: str = ANNOUNCE_ROTATION
    announce_filters: tuple[str, ...] = ()
    maintain_pin: bool = True


SCHEDULE_PINS: tuple[SchedulePin, ...] = (
    SchedulePin("quick", "quick-or-flashback-draft", ("quick",), "Quick Draft", ANNOUNCE_ROTATION, ("quick",)),
    SchedulePin(
        "flashback", "quick-or-flashback-draft", ("flashback",), "Flashback", ANNOUNCE_ROTATION, ("flashback",)
    ),
    SchedulePin("cube", "cube-talk", (), None, ANNOUNCE_ROTATION, ("cube",), maintain_pin=False),
    SchedulePin("sealed", "sealed-discussion", ("sealed",), "Sealed", ANNOUNCE_NONE),
    SchedulePin("set", None, (), None, ANNOUNCE_COMPETITIVE, ("competitive",)),
)


def channel_name_for(pin: SchedulePin) -> str:
    """The channel-name fragment a pin routes to. The competitive pin leaves it unset and follows the
    newest registered set, so the channel moves with each rotation without a config edit."""
    if pin.channel_name is not None:
        return pin.channel_name
    return slugify(newest_set().name)


def newest_set():
    candidates = [seed for seed in ALL_SETS if seed.code != PERMANENT_CUBE_CODE]
    newest = candidates[0]
    for seed in candidates[1:]:
        if seed.start_date > newest.start_date:
            newest = seed
    return newest


def slugify(name: str) -> str:
    return name.lower().replace(":", "").replace(" ", "-")


def previous_window_start(now: datetime) -> datetime:
    """The announce window immediately before ``now`` (UTC). A tick announces events that opened since
    this instant — a span that ends at the current window, so consecutive ticks never overlap and each
    event is announced exactly once. Windows are Pacific (MTGA's clock) so they hold across DST."""
    now_local = now.astimezone(OPEN_TZ)
    fired: list[datetime] = []
    for day_offset in (0, -1):
        day = (now_local + timedelta(days=day_offset)).date()
        for window in ANNOUNCE_WINDOWS:
            moment = datetime.combine(day, window, tzinfo=OPEN_TZ)
            if moment <= now_local + timedelta(minutes=1):
                fired.append(moment)
    fired.sort()
    previous = fired[-2] if len(fired) >= 2 else now_local - timedelta(days=1)
    return previous.astimezone(timezone.utc)


def newly_opened(groups: list[mtgscribe.EventGroup], since: datetime, now: datetime) -> list:
    """Groups that opened in ``(since, now]`` — events that went live since the previous window."""
    return [group for group in groups if since < group.start <= now]


def next_rotation(groups: list[mtgscribe.EventGroup], current: mtgscribe.EventGroup):
    """The soonest group that begins after ``current`` — the next rotation of the same pin's format,
    used for the announcement's "Next Up" preview. ``None`` when nothing follows."""
    upcoming = None
    for group in groups:
        if group.start <= current.start:
            continue
        if upcoming is None or group.start < upcoming.start:
            upcoming = group
    return upcoming


def announcement_format(group: mtgscribe.EventGroup) -> str:
    """The rotation-type word in an announcement heading ("**<set>** <word> is live!"), keyed on the
    group's tags rather than the routed channel so a quick-or-flashback channel labels its Flashback
    and Quick posts distinctly. Empty for a cube, whose set name already names the format."""
    if group.flashback:
        return "Flashback"
    if group.competitive:
        return "Competitive"
    if group.cube:
        return ""
    if "Quick Draft" in group.formats:
        return "Quick Draft"
    return "Sealed"


def already_announced(recent_contents: list[str], lead: str, label: str) -> bool:
    """An announcement is a repeat when the day's own messages already carry its type lead and set
    label — the table-free dedup that survives a restart or a re-tick on the same day."""
    for content in recent_contents:
        if lead in content and label in content:
            return True
    return False
