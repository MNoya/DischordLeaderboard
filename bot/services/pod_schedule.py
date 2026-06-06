"""Slot table, release calendar and flavor pools driving the weekly pod-draft schedule automation.

Pure date/selection logic — no Discord, no DB. The APScheduler wiring lives in
bot/tasks/pod_schedule_post.py and bot/tasks/pod_underfill.py.

Flavor pools are curated offline (generated with an LLM, hand-picked per set) — see
spec/pod-draft-scheduler.md for the prompt guidance. A set with missing or empty pools
falls back to GENERIC_FLAVOR.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from bot.sets import ALL_SETS


SCHEDULE_TZ = ZoneInfo("America/New_York")

WEDNESDAY = 2
THURSDAY = 3

MONDAY_KIND_NORMAL = "normal"
MONDAY_KIND_RELEASE_WEEK = "release_week"
MONDAY_KIND_CHAMPIONSHIP_WEEK = "championship_week"

CREATE_CHANNEL_REF = "#🚀-pod-draft-coordination"
CREATE_MENTIONS = "@Any Pronouns"


@dataclass(frozen=True)
class WeeklySlot:
    weekday: int
    start: time


WEEKLY_SLOTS: tuple[WeeklySlot, ...] = (
    WeeklySlot(weekday=WEDNESDAY, start=time(20, 0)),
    WeeklySlot(weekday=THURSDAY, start=time(14, 0)),
)


@dataclass(frozen=True)
class UpcomingRelease:
    release_date: date
    code: str
    name: str


UPCOMING_RELEASES: tuple[UpcomingRelease, ...] = (
    UpcomingRelease(date(2026, 6, 23), "MSH", "Marvel Super Heroes"),
    UpcomingRelease(date(2026, 8, 11), "HOB", "The Hobbit"),
    UpcomingRelease(date(2026, 9, 29), "FRA", "Reality Fracture"),
    UpcomingRelease(date(2026, 11, 10), "TRE", "Star Trek"),
)


@dataclass(frozen=True)
class SetFlavor:
    monday_blurbs: tuple[str, ...]
    event_descriptions: tuple[str, ...]


GENERIC_FLAVOR = SetFlavor(
    monday_blurbs=(
        "📜 **Weekly Draft Bulletin**\nThe packs are sealed. The seats are open. The lanes remain, for now, unclaimed.",
        "📜 **Notice from the Pairings Office**\nTwo pods are scheduled this week. History shows the best seats go to "
        "those who react early.",
        "📜 **Weekly Records Update**\nArchivists note that every memorable draft began the same way: somebody RSVP'd.",
    ),
    event_descriptions=(
        "Eight seats. Three rounds. One trophy. The math checks out.",
        "The packs are sealed and the seats are waiting.",
        "Officials confirm the open lane exists. Someone will find it.",
        "A trophy will be awarded. Witnesses expected.",
    ),
)

SET_FLAVOR: dict[str, SetFlavor] = {
    "MSH": SetFlavor(
        monday_blurbs=(),
        event_descriptions=(),
    ),
}


def slots_for_week(monday: date) -> list[datetime]:
    return [
        datetime.combine(monday + timedelta(days=slot.weekday), slot.start, tzinfo=SCHEDULE_TZ)
        for slot in WEEKLY_SLOTS
    ]


def next_release_after(day: date) -> UpcomingRelease | None:
    for release in UPCOMING_RELEASES:
        if release.release_date > day:
            return release
    return None


def monday_kind(monday: date) -> tuple[str, UpcomingRelease | None]:
    release = next_release_after(monday)
    if release is None:
        return MONDAY_KIND_NORMAL, None
    days_out = (release.release_date - monday).days
    if days_out <= 7:
        return MONDAY_KIND_RELEASE_WEEK, release
    if days_out <= 13:
        return MONDAY_KIND_CHAMPIONSHIP_WEEK, release
    return MONDAY_KIND_NORMAL, None


def week_index_for(set_code: str, monday: date) -> int:
    for s in ALL_SETS:
        if s.code == set_code:
            return max(0, (monday - s.start_date).days // 7)
    return monday.isocalendar().week


def monday_blurb(set_code: str, week_index: int) -> str:
    pool = _pool(set_code, "monday_blurbs")
    return pool[week_index % len(pool)]


def event_description(set_code: str, event_index: int) -> str:
    pool = _pool(set_code, "event_descriptions")
    return pool[event_index % len(pool)]


def build_create_command(set_code: str, event_number: int, slot_start: datetime, description: str) -> str:
    day = f"{slot_start:%B} {slot_start.day}"
    clock = format_clock(slot_start)
    return (
        f"/create title:{set_code} Pod Draft #{event_number} - {day} "
        f"datetime:{day} {clock} ET "
        f"channel:{CREATE_CHANNEL_REF} "
        f"on_create_mentions:{CREATE_MENTIONS} "
        f"description:{description}"
    )


def format_clock(slot_start: datetime) -> str:
    hour = slot_start.strftime("%I").lstrip("0")
    minute = f":{slot_start.minute:02d}" if slot_start.minute else ""
    return f"{hour}{minute}{slot_start.strftime('%p').lower()}"


def _pool(set_code: str, pool_name: str) -> tuple[str, ...]:
    flavor = SET_FLAVOR.get(set_code)
    pool: tuple[str, ...] = getattr(flavor, pool_name) if flavor else ()
    return pool or getattr(GENERIC_FLAVOR, pool_name)
