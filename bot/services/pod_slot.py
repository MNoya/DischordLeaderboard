"""Date + time-of-day naming for pods — the identity a pod carries from creation.

A pod's Discord name is `SET Mon Day Slot Pod` (`MSH Jul 16 Early Pod`), fixed when the card is
posted and never renumbered: the slot label comes from the poll buckets by weekend and time of day,
so a launcher pod and a weekly-schedule pod at the same slot read the same. The website's `#N`
milestone is a separate, execution-ordered projection computed in `public_pod_draft_events`, not
part of this name. Pure — no Discord, no DB.
"""
from __future__ import annotations

from datetime import datetime

from bot.services.pod_schedule import SCHEDULE_TZ
from bot.services.pod_signals import PollBucket, poll_buckets_for


def pod_display_name(set_code: str, event_time: datetime) -> str:
    local = event_time.astimezone(SCHEDULE_TZ)
    return f"{set_code.upper()} {local:%b %-d} {pod_slot_label(event_time)}"


def pod_slot_label(event_time: datetime) -> str:
    return slot_bucket_for(event_time).name


def slot_bucket_for(event_time: datetime) -> PollBucket:
    """The poll bucket a pod at this instant belongs to, by weekend and nearest start time. An
    exact-grid pod lands on its own slot; an off-grid `/draft` snaps to the closest slot, ties going
    to the later one so a mid-afternoon pod reads Late rather than Early."""
    local = event_time.astimezone(SCHEDULE_TZ)
    buckets = poll_buckets_for(local.date())
    minutes = local.hour * 60 + local.minute
    best = buckets[0]
    best_delta = abs(minutes - (best.start.hour * 60 + best.start.minute))
    for bucket in buckets[1:]:
        delta = abs(minutes - (bucket.start.hour * 60 + bucket.start.minute))
        if delta <= best_delta:
            best_delta = delta
            best = bucket
    return best
