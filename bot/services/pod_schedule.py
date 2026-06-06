"""Slot table, release calendar, and every user-facing string the pod-draft scheduler emits.

Pure date/selection logic — no Discord, no DB. The APScheduler wiring lives in
bot/tasks/pod_schedule_post.py and bot/tasks/pod_underfill.py.

Monday blurbs are curated offline (generated with an LLM, hand-picked per set) — see
spec/pod-draft-scheduler.md for the prompt guidance. A set with a missing or empty pool
falls back to GENERIC_MONDAY_BLURBS.
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


# User-facing copy

MSG_SCHEDULE_HEADER = "📅 {set_code} Pod Drafts this week:"

MSG_MONDAY_DM_INTRO = "Monday schedule draft — paste it as-is, tweak it first, or press a button:"

BTN_POST_FOR_ME = "Post it for me"
BTN_GOT_IT = "I've got it"
BTN_SKIP = "Skip this week"

MSG_BTN_POSTED = "Posted ✅"
MSG_BTN_ALREADY_POSTED = "The schedule is already up — nothing posted."
MSG_BTN_GOT_IT = "All yours — no fallback post this week."
MSG_BTN_SKIPPED = "Skipped — no schedule post this week."

MSG_RELEASE_WEEK = (
    "🌀 **{set_name}** drops <t:{unix}:R>! Regular pods are paused this week while the new set hits the queues.\n"
    "React with 👍 if you still want a pod this week."
)

MSG_CHAMPIONSHIP_WEEK = (
    "🏆 Final week of **{set_code}**! The Set Championship closes out the season — regular pods are paused "
    "this week. **{next_name}** arrives <t:{unix}:R>."
)

MSG_UNDERFILL = (
    "{role_mention}{needed} more player{plural} needed for the pod draft on <t:{unix}:F> (<t:{unix}:R>) — "
    "{yes_count}/{target} in so far. RSVP: {jump_url}"
)

MSG_CREATE_DM_HEADER = "Sesh commands for this week's pods:"

CREATE_CHANNEL_REF = "#🚀-pod-draft-coordination"
CREATE_MENTIONS = "@Any Pronouns"
CREATE_COMMAND_TEMPLATE = (
    "/create title:{set_code} Pod Draft #{event_number} - {day} "
    "datetime:{day} {clock} ET "
    "channel:{channel} "
    "on_create_mentions:{mentions}"
)

GENERIC_MONDAY_BLURBS: tuple[str, ...] = (
    "📜 **Weekly Draft Bulletin**\nThe packs are sealed. The seats are open. The lanes remain, for now, unclaimed.",
    "📜 **Notice from the Pairings Office**\nTwo pods are scheduled this week. History shows the best seats go to "
    "those who react early.",
    "📜 **Weekly Records Update**\nArchivists note that every memorable draft began the same way: somebody RSVP'd.",
)

MONDAY_BLURBS: dict[str, tuple[str, ...]] = {
    "MSH": (),
}


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
    pool = MONDAY_BLURBS.get(set_code) or GENERIC_MONDAY_BLURBS
    return pool[week_index % len(pool)]


def compose_monday_message(monday: date, set_code: str) -> str:
    """The paste-ready weekly post — plain text so it reads identically from the owner or the bot."""
    kind, release = monday_kind(monday)
    if kind == MONDAY_KIND_RELEASE_WEEK:
        return MSG_RELEASE_WEEK.format(set_name=release.name, unix=release_unix(release))
    if kind == MONDAY_KIND_CHAMPIONSHIP_WEEK:
        return MSG_CHAMPIONSHIP_WEEK.format(set_code=set_code, next_name=release.name, unix=release_unix(release))
    blurb = monday_blurb(set_code, week_index_for(set_code, monday))
    header = MSG_SCHEDULE_HEADER.format(set_code=set_code)
    slot_lines = []
    for slot in slots_for_week(monday):
        unix = int(slot.timestamp())
        slot_lines.append(f"• <t:{unix}:F> (<t:{unix}:R>)")
    return blurb + "\n\n" + header + "\n" + "\n".join(slot_lines)


def release_unix(release: UpcomingRelease) -> int:
    release_moment = datetime.combine(release.release_date, time(12, 0), tzinfo=SCHEDULE_TZ)
    return int(release_moment.timestamp())


def build_create_command(set_code: str, event_number: int, slot_start: datetime) -> str:
    return CREATE_COMMAND_TEMPLATE.format(
        set_code=set_code,
        event_number=event_number,
        day=f"{slot_start:%B} {slot_start.day}",
        clock=format_clock(slot_start),
        channel=CREATE_CHANNEL_REF,
        mentions=CREATE_MENTIONS,
    )


def build_underfill_message(
    role_id: int | None,
    yes_count: int,
    target: int,
    event_time: datetime,
    jump_url: str,
) -> str:
    needed = target - yes_count
    return MSG_UNDERFILL.format(
        role_mention=f"<@&{role_id}> " if role_id else "",
        needed=needed,
        plural="s" if needed != 1 else "",
        unix=int(event_time.timestamp()),
        yes_count=yes_count,
        target=target,
        jump_url=jump_url,
    )


def format_clock(slot_start: datetime) -> str:
    hour = slot_start.strftime("%I").lstrip("0")
    minute = f":{slot_start.minute:02d}" if slot_start.minute else ""
    return f"{hour}{minute}{slot_start.strftime('%p').lower()}"
