"""Pure slot/day/threshold logic for on-demand pods — no Discord, no DB.

Feeds the daily poll (bot/tasks/pod_daily_poll.py) and the dynamic queue
(bot/commands/pod_queue.py). ET anchoring reuses pod_schedule.SCHEDULE_TZ so the
poll slots share one clock with the fixed weekly slots.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from bot.services.pod_schedule import SCHEDULE_TZ


SATURDAY = 5

WEEKDAY_POST_HOUR_ET = 11
WEEKEND_POST_HOUR_ET = 8

KIND_POLL = "poll"
KIND_QUEUE = "queue"
KIND_SCHEDULED = "scheduled"

QUEUE_BUCKET = "queue"
SCHEDULED_BUCKET = "scheduled"

STATUS_OPEN = "open"
STATUS_FIRED = "fired"
STATUS_EXPIRED = "expired"

RSVP_YES = "yes"
RSVP_MAYBE = "maybe"
RSVP_NO = "no"
RSVP_STATES = (RSVP_YES, RSVP_MAYBE, RSVP_NO)


@dataclass(frozen=True)
class PollBucket:
    key: str
    name: str
    emoji: str
    start: time


WEEKDAY_BUCKETS: tuple[PollBucket, ...] = (
    PollBucket("EARLY", "Early Pod", "💫", time(14, 0)),
    PollBucket("LATE", "Late Pod", "☄️", time(20, 0)),
)
WEEKEND_BUCKETS: tuple[PollBucket, ...] = (
    PollBucket("MORNING", "Morning Pod", "🌅", time(10, 0)),
    PollBucket("AFTERNOON", "Early Pod", "💫", time(15, 0)),
    PollBucket("EVENING", "Late Pod", "☄️", time(20, 0)),
)
ALL_BUCKETS: tuple[PollBucket, ...] = WEEKDAY_BUCKETS + WEEKEND_BUCKETS
WEEKEND_BUCKET_KEYS: frozenset[str] = frozenset(bucket.key for bucket in WEEKEND_BUCKETS)


def is_weekend(day: date) -> bool:
    return day.weekday() >= SATURDAY


def poll_buckets_for(day: date) -> tuple[PollBucket, ...]:
    return WEEKEND_BUCKETS if is_weekend(day) else WEEKDAY_BUCKETS


def poll_post_hour_for(day: date) -> int:
    return WEEKEND_POST_HOUR_ET if is_weekend(day) else WEEKDAY_POST_HOUR_ET


def is_weekend_bucket(key: str) -> bool:
    """Weekend slot headers drop the role mention (three of them would spam @Weekend Pod and wrap)."""
    return key in WEEKEND_BUCKET_KEYS


def bucket_by_key(key: str) -> PollBucket | None:
    for bucket in ALL_BUCKETS:
        if bucket.key == key:
            return bucket
    return None


def slot_event_time(signal_date: date, bucket_key: str) -> datetime | None:
    """The ET wall-clock start for a poll slot on `signal_date`, or None for an unknown bucket."""
    bucket = bucket_by_key(bucket_key)
    if bucket is None:
        return None
    return datetime.combine(signal_date, bucket.start, tzinfo=SCHEDULE_TZ)


def should_fire(member_count: int, threshold: int) -> bool:
    return member_count >= threshold


def teardown_at(last_activity: datetime, minutes: int) -> datetime:
    return last_activity + timedelta(minutes=minutes)
