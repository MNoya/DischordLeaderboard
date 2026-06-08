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
MONDAY_KIND_SEASON_OVER = "season_over"


# User-facing copy

MSG_SCHEDULE_HEADER = "📅 {set_code} Pod Drafts this week:"

MSG_MONDAY_DRAFT_INTRO = "Weekly schedule draft — paste it as-is, tweak it first, or press a button:"

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
    "👑 Final week of **{set_code}**! The Set Championship <t:{champ_unix}:D> closes out the season — regular "
    "pods are paused this week. **{next_name}** arrives <t:{unix}:R>."
)

MSG_SEASON_OVER = (
    "🏁 That's a wrap on **{set_code}** — the champion's crowned and the season's done. Regular pods are paused "
    "until **{next_name}** drops <t:{unix}:R>."
)

MSG_UNDERFILL = (
    "[{thread_name}]({thread_url}): {needed} more player{plural} needed in <t:{unix}:R> "
    "- [Sign Up Link]({jump_url})"
)

MSG_UNDERFILL_FILLED = "[{thread_name}]({thread_url}): Pod is full ✅"

MSG_CREATE_BLOCKS_HEADER = "Sesh commands for this week's pods:"

POD_DRAFTERS_ROLE_NAME = "Pod Drafters"

CREATE_CHANNEL_REF = "#🚀-pod-draft-coordination"
CREATE_MENTIONS = f"@{POD_DRAFTERS_ROLE_NAME}"
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
    championship_date: date | None = None


UPCOMING_RELEASES: tuple[UpcomingRelease, ...] = (
    UpcomingRelease(date(2026, 6, 23), "MSH", "Marvel Super Heroes", championship_date=date(2026, 6, 13)),
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
    """Classify a week against the next release and the season-closing championship that precedes it.

    Release week wins outright; otherwise the explicit championship date decides — the week holding it
    is championship week, any week after it (but before release week) is the paused season-over gap.
    """
    release = next_release_after(monday)
    if release is None:
        return MONDAY_KIND_NORMAL, None
    if (release.release_date - monday).days <= 7:
        return MONDAY_KIND_RELEASE_WEEK, release
    championship = release.championship_date
    if championship is not None:
        if monday <= championship < monday + timedelta(days=7):
            return MONDAY_KIND_CHAMPIONSHIP_WEEK, release
        if championship < monday:
            return MONDAY_KIND_SEASON_OVER, release
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
        return MSG_CHAMPIONSHIP_WEEK.format(
            set_code=set_code,
            next_name=release.name,
            champ_unix=championship_unix(release),
            unix=release_unix(release),
        )
    if kind == MONDAY_KIND_SEASON_OVER:
        return MSG_SEASON_OVER.format(set_code=set_code, next_name=release.name, unix=release_unix(release))
    blurb = monday_blurb(set_code, week_index_for(set_code, monday))
    header = MSG_SCHEDULE_HEADER.format(set_code=set_code)
    slot_lines = []
    for slot in slots_for_week(monday):
        unix = int(slot.timestamp())
        slot_lines.append(f"• <t:{unix}:F> (<t:{unix}:R>)")
    return blurb + "\n\n" + header + "\n" + "\n".join(slot_lines)


def release_unix(release: UpcomingRelease) -> int:
    return _noon_unix(release.release_date)


def championship_unix(release: UpcomingRelease) -> int:
    return _noon_unix(release.championship_date)


def _noon_unix(day: date) -> int:
    return int(datetime.combine(day, time(12, 0), tzinfo=SCHEDULE_TZ).timestamp())


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
    thread_name: str,
    thread_url: str,
    yes_count: int,
    target: int,
    event_time: datetime,
    jump_url: str,
) -> str:
    needed = target - yes_count
    return MSG_UNDERFILL.format(
        thread_name=thread_name,
        thread_url=thread_url,
        needed=needed,
        plural="s" if needed != 1 else "",
        unix=int(event_time.timestamp()),
        jump_url=jump_url,
    )


def build_underfill_filled_message(thread_name: str, thread_url: str) -> str:
    return MSG_UNDERFILL_FILLED.format(thread_name=thread_name, thread_url=thread_url)


def format_clock(slot_start: datetime) -> str:
    hour = slot_start.strftime("%I").lstrip("0")
    minute = f":{slot_start.minute:02d}" if slot_start.minute else ""
    return f"{hour}{minute}{slot_start.strftime('%p').lower()}"
