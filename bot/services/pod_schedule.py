"""Slot table, release calendar, and every user-facing string the pod-draft scheduler emits.

Pure date/selection logic — no Discord, no DB. The APScheduler wiring lives in
bot/tasks/pod_schedule_post.py and bot/tasks/pod_underfill.py.

Monday blurbs are curated offline (generated with an LLM, hand-picked per set) — see
spec/pod-draft-scheduler.md for the prompt guidance. A set with a missing or empty pool
falls back to GENERIC_MONDAY_BLURBS; with both empty the post carries no blurb line.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from bot import emojis
from bot.services.sesh_parser import NUM_RE
from bot.sets import ALL_SETS


SCHEDULE_TZ = ZoneInfo("America/New_York")

WEDNESDAY = 2
THURSDAY = 3
SATURDAY = 5

CREATE_LEAD_HOURS = 50
NA_CREATE_SEND_HOUR_ET = 12

MONDAY_KIND_NORMAL = "normal"
MONDAY_KIND_RELEASE_WEEK = "release_week"
MONDAY_KIND_CHAMPIONSHIP_WEEK = "championship_week"
MONDAY_KIND_SEASON_OVER = "season_over"


# User-facing copy

MSG_SCHEDULE_HEADER = "🗓️ {set_code} Pod Drafts {set_emoji} Week {week}"

MSG_MONDAY_DRAFT_INTRO = "Weekly schedule draft — paste it as-is, tweak it first, or press a button:"

BTN_POST = "Post it"
BTN_GOT_IT = "I've got it"
BTN_SKIP = "Skip this week"

BTN_EMOJI_POST = "🚀"
BTN_EMOJI_GOT_IT = "📝"
BTN_EMOJI_SKIP = "⏩"

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
    "🏁 That's a wrap on **{set_code}** — the champion's crowned and the season's done.\n"
    "Regular pods are paused until **{next_name}** drops <t:{unix}:R>."
)

MSG_UNDERFILL = (
    "{hello}**{name}** looking for **{needed} more player{plural}** <t:{unix}:R> "
    "- [**Sign up here**]({jump_url}) {manat}"
)

MSG_CREATE_COMMAND_LEAD = "{emoji} {day} pod — paste the next message as-is to open RSVPs:"

SLOT_EMOJI_AMERICAS = "🌎"
SLOT_EMOJI_EU = "🇪🇺"
SLOT_EMOJI_SATURDAY = "🪐"

POD_DRAFTERS_ROLE_NAME = "Pod Drafters"
EARLY_POD_ROLE_NAME = "Early Pod"
LATE_POD_ROLE_NAME = "Late Pod"
WEEKEND_POD_ROLE_NAME = "Weekend Pod"
POD_QUEUE_ROLE_NAME = "Pod Draft Queue"

CREATE_MENTIONS = f"@{POD_DRAFTERS_ROLE_NAME}"
CREATE_MENTIONS_EARLY = f"@{EARLY_POD_ROLE_NAME}"
CREATE_MENTIONS_LATE = f"@{LATE_POD_ROLE_NAME}"
CREATE_MENTIONS_WEEKEND = f"@{WEEKEND_POD_ROLE_NAME}"
CREATE_DESCRIPTION = f"{SLOT_EMOJI_AMERICAS} Please RSVP"
CREATE_DESCRIPTION_EARLY = f"{SLOT_EMOJI_EU} Early Draft! Please RSVP"
CREATE_DESCRIPTION_SAT = f"{SLOT_EMOJI_SATURDAY} Weekend Draft! Please RSVP"
CREATE_COMMAND_TEMPLATE = (
    "/create title:{set_code} Pod Draft #{event_number} - {day} "
    "datetime:{day} {year} {clock} {zone} "
    "duration:2 hours "
    "description:{description} "
    "on_create_mentions:{mentions}"
)

GENERIC_MONDAY_BLURBS: tuple[str, ...] = ()

MONDAY_BLURBS: dict[str, tuple[str, ...]] = {
    "MSH": (),
}


@dataclass(frozen=True)
class WeeklySlot:
    weekday: int
    start: time
    description: str
    emoji: str
    mentions: str
    send_monday_noon: bool = False


WEEKLY_SLOTS: tuple[WeeklySlot, ...] = (
    WeeklySlot(
        WEDNESDAY, time(20, 0), CREATE_DESCRIPTION, SLOT_EMOJI_AMERICAS, CREATE_MENTIONS_LATE, send_monday_noon=True
    ),
    WeeklySlot(THURSDAY, time(14, 0), CREATE_DESCRIPTION_EARLY, SLOT_EMOJI_EU, CREATE_MENTIONS_EARLY),
    WeeklySlot(SATURDAY, time(15, 0), CREATE_DESCRIPTION_SAT, SLOT_EMOJI_SATURDAY, CREATE_MENTIONS_WEEKEND),
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


def monday_of(moment: datetime) -> date:
    local_date = moment.astimezone(SCHEDULE_TZ).date()
    return local_date - timedelta(days=local_date.weekday())


def upcoming_slots(reference: datetime, count: int = len(WEEKLY_SLOTS)) -> list[datetime]:
    """The next `count` weekly pod slots at or after `reference`, chronological across week boundaries."""
    week_monday = monday_of(reference)
    upcoming: list[datetime] = []
    while len(upcoming) < count:
        for start in slots_for_week(week_monday):
            if start >= reference:
                upcoming.append(start)
        week_monday += timedelta(days=7)
    return upcoming[:count]


def slot_instant(moment: datetime) -> datetime:
    """UTC-normalized key for matching a slot start against an already-created pod's event time."""
    return moment.astimezone(timezone.utc).replace(microsecond=0)


def next_unscheduled_slots(
    reference: datetime, scheduled_instants: set[datetime], count: int = len(WEEKLY_SLOTS), max_weeks: int = 6
) -> list[datetime]:
    """The next `count` pod slots from `reference` with no pod created yet, stopping at a paused boundary week.

    Walks forward slot by slot, skipping instants already in `scheduled_instants`, so a rotation that already
    has this week's early slots announced rolls straight to the next open ones.
    """
    week_monday = monday_of(reference)
    open_slots: list[datetime] = []
    for _ in range(max_weeks + 1):
        if monday_kind(week_monday)[0] != MONDAY_KIND_NORMAL:
            break
        for start in slots_for_week(week_monday):
            if start < reference or slot_instant(start) in scheduled_instants:
                continue
            open_slots.append(start)
            if len(open_slots) == count:
                return open_slots
        week_monday += timedelta(days=7)
    return open_slots


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
    """Zero-based count of weeks since the set opened, aligned to the Monday of its release week.

    A mid-week release still counts its whole opening week as week 0, so the Monday after a Tuesday
    drop advances to week 1 — the human "Week N" the community uses is this index plus one.
    """
    for s in ALL_SETS:
        if s.code == set_code:
            start_monday = s.start_date - timedelta(days=s.start_date.weekday())
            return max(0, (monday - start_monday).days // 7)
    return monday.isocalendar().week


def monday_blurb(set_code: str, week_index: int) -> str:
    pool = MONDAY_BLURBS.get(set_code) or GENERIC_MONDAY_BLURBS
    if not pool:
        return ""
    return pool[week_index % len(pool)]


def compose_schedule_message(reference: datetime, set_code: str, count: int = len(WEEKLY_SLOTS)) -> str:
    """The paste-ready post listing the next `count` pod slots from `reference`, in chronological order.

    Boundary weeks pause pods, so the first upcoming slot's week decides the message: a boundary week wins
    outright, and on a normal week only upcoming slots that themselves fall in normal weeks are listed, so a
    window spilling into a paused week never advertises paused slots. Plain text so it reads identically from
    the owner or the bot.
    """
    slots = upcoming_slots(reference, count)
    first_monday = monday_of(slots[0])
    kind, release = monday_kind(first_monday)
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
    week_index = week_index_for(set_code, first_monday)
    blurb = monday_blurb(set_code, week_index)
    set_emoji = emojis.get(set_code.lower()) or emojis.get(set_code)
    header = MSG_SCHEDULE_HEADER.format(set_code=set_code, set_emoji=set_emoji, week=week_index + 1)
    slot_lines = []
    for start in slots:
        if monday_kind(monday_of(start))[0] != MONDAY_KIND_NORMAL:
            continue
        slot = slot_by_weekday(start.weekday())
        unix = int(start.timestamp())
        slot_lines.append(f"{slot.emoji} <t:{unix}:F> (<t:{unix}:R>)")
    body = header + "\n" + "\n".join(slot_lines)
    return f"{blurb}\n\n{body}" if blurb else body


def compose_monday_message(monday: date, set_code: str) -> str:
    """Render a whole week's schedule from its Monday — the specific-week preview and the Monday post."""
    return compose_schedule_message(datetime.combine(monday, time.min, tzinfo=SCHEDULE_TZ), set_code)


def release_unix(release: UpcomingRelease) -> int:
    return _noon_unix(release.release_date)


def championship_unix(release: UpcomingRelease) -> int:
    return _noon_unix(release.championship_date)


def _noon_unix(day: date) -> int:
    return int(datetime.combine(day, time(12, 0), tzinfo=SCHEDULE_TZ).timestamp())


def build_create_command(
    set_code: str, event_number: int, slot_start: datetime, description: str, mentions: str = CREATE_MENTIONS,
) -> str:
    return CREATE_COMMAND_TEMPLATE.format(
        set_code=set_code,
        event_number=event_number,
        day=f"{slot_start:%B} {slot_start.day}",
        year=slot_start.year,
        clock=format_clock(slot_start),
        zone=slot_start.strftime("%Z"),
        description=description,
        mentions=mentions,
    )


def create_command_send_time(slot: WeeklySlot, monday: date) -> datetime:
    """When to DM a slot's standalone /create command.

    The late slot goes out Monday midday alongside the weekly overview; the other slots fire a fixed
    lead before slot start so they don't clutter the channel days ahead.
    """
    if slot.send_monday_noon:
        return datetime.combine(monday, time(NA_CREATE_SEND_HOUR_ET, 0), tzinfo=SCHEDULE_TZ)
    slot_start = datetime.combine(monday + timedelta(days=slot.weekday), slot.start, tzinfo=SCHEDULE_TZ)
    return slot_start - timedelta(hours=CREATE_LEAD_HOURS)


def slot_for_event_time(event_time: datetime) -> WeeklySlot | None:
    """The weekly slot whose local ET (weekday, time) matches this event, or None for an off-grid time."""
    local = event_time.astimezone(SCHEDULE_TZ)
    for slot in WEEKLY_SLOTS:
        if slot.weekday == local.weekday() and slot.start == local.time():
            return slot
    return None


def slot_by_weekday(weekday: int) -> WeeklySlot | None:
    for slot in WEEKLY_SLOTS:
        if slot.weekday == weekday:
            return slot
    return None


def next_slot_datetime(slot: WeeklySlot, *, now: datetime | None = None) -> datetime:
    """The next future occurrence of a slot in ET, for rendering a localized Discord timestamp."""
    now = now or datetime.now(SCHEDULE_TZ)
    candidate = datetime.combine(
        now.date() + timedelta(days=(slot.weekday - now.weekday()) % 7), slot.start, tzinfo=SCHEDULE_TZ
    )
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def highest_event_number(event_names: Iterable[str]) -> int:
    """Largest '#N' across recorded pod names; the weekly forecast numbers up from here."""
    highest = 0
    for name in event_names:
        match = NUM_RE.search(name or "")
        if match is not None:
            highest = max(highest, int(match.group(1)))
    return highest


_DATE_SUFFIX_RE = re.compile(r"\s+-\s+[A-Z][a-z]+\s+\d{1,2}$")


def short_event_name(name: str) -> str:
    """Pod name without the trailing ' - Month Day' suffix the scheduler appends, for tight inline copy."""
    return _DATE_SUFFIX_RE.sub("", name)


def build_underfill_message(
    thread_name: str,
    yes_count: int,
    target: int,
    event_time: datetime,
    jump_url: str,
) -> str:
    needed = target - yes_count
    body = MSG_UNDERFILL.format(
        hello=emojis.prefix("chordoHello"),
        name=short_event_name(thread_name),
        needed=needed,
        plural="s" if needed != 1 else "",
        unix=int(event_time.timestamp()),
        jump_url=jump_url,
        manat=emojis.get("manat"),
    )
    return body.rstrip()


def format_clock(slot_start: datetime) -> str:
    hour = slot_start.strftime("%I").lstrip("0")
    minute = f":{slot_start.minute:02d}" if slot_start.minute else ""
    return f"{hour}{minute}{slot_start.strftime('%p').lower()}"
