"""Pure slot/day/threshold logic for on-demand pods — no Discord, no DB.

Feeds the daily poll (bot/tasks/pod_daily_poll.py) and the dynamic queue
(bot/commands/pod_queue.py). ET anchoring reuses pod_schedule.SCHEDULE_TZ so the
poll slots share one clock with the fixed weekly slots.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from bot.services.pod_schedule import SCHEDULE_TZ


MONDAY, TUESDAY, FRIDAY, SUNDAY = 0, 1, 4, 6
POLL_WEEKDAYS: tuple[int, ...] = (MONDAY, TUESDAY, FRIDAY, SUNDAY)

POLL_POST_HOUR_ET = 11

KIND_POLL = "poll"
KIND_QUEUE = "queue"

QUEUE_BUCKET = "queue"

STATUS_OPEN = "open"
STATUS_FIRED = "fired"
STATUS_EXPIRED = "expired"


@dataclass(frozen=True)
class PollBucket:
    key: str
    name: str
    emoji: str
    start: time


POLL_BUCKETS: tuple[PollBucket, ...] = (
    PollBucket("EARLY", "Early Pod", "💫", time(14, 0)),
    PollBucket("LATE", "Late Pod", "☄️", time(20, 0)),
)


def is_poll_day(day: date) -> bool:
    return day.weekday() in POLL_WEEKDAYS


def bucket_by_key(key: str) -> PollBucket | None:
    for bucket in POLL_BUCKETS:
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
