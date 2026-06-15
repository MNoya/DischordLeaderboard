"""Client for the MTG Scribe events calendar and grouping of its queues.

Source is The Events Calendar REST API on mtgscribe.com, which returns each
queue with ``utc_start_date``/``utc_end_date`` — the stock ``/events/feed/`` RSS
only carries a start date, so the REST endpoint is the one worth consuming.

Queues that share a set and a calendar-day window collapse into one group: the
three Secrets of Strixhaven drafts become a single ``EventGroup`` listing all
three formats, instead of three near-duplicate callouts. Grouping keys on the
date, not the timestamp, so queues that open an hour apart still merge.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

import requests

logger = logging.getLogger(__name__)

EVENTS_URL = "https://mtgscribe.com/wp-json/tribe/events/v1/events"
PER_PAGE = 50
REQUEST_TIMEOUT = 15


@dataclass(frozen=True)
class ScribeEvent:
    title: str
    format_label: str
    group_label: str
    start: datetime
    end: datetime
    start_local: datetime
    end_local: datetime
    tag_slugs: tuple[str, ...]


@dataclass
class EventGroup:
    label: str
    formats: list[str] = field(default_factory=list)
    start: datetime = None
    end: datetime = None
    start_local: datetime = None
    end_local: datetime = None
    flashback: bool = False
    cube: bool = False


ARENA_TAG = "arena"
FLASHBACK_TAG = "flashback"
CUBE_TAG = "cube"


def fetch_events(start_date: date, *, arena_only: bool = True) -> list[ScribeEvent]:
    """Pull every event starting on/after ``start_date``, following pagination.

    The API caps each page at 50 and reports ``total_pages``; an explicit past
    ``start_date`` is required to surface in-progress events, whose start has
    already passed and which the default (today-onward) window drops.

    ``arena_only`` keeps MTG Arena client events (the ``arena`` tag) and drops tabletop
    programs. The Limited-vs-Constructed cut is left to the caller, so the Midweek view
    can surface constructed queues.

    The cache-bust is per-invocation, not daily: a daily bucket let a stale-date copy (a
    corrected end date, a duplicate queue) persist on the CDN for the rest of the day. This is
    an on-demand command, so a fresh origin fetch each call is cheap and always matches the site.
    """
    events: list[ScribeEvent] = []
    cache_bust = time.strftime("%Y%m%d%H%M%S")
    page = 1
    while True:
        payload = _get_page(start_date, page, cache_bust)
        batch = payload.get("events", [])
        events.extend(_parse_event(raw) for raw in batch)
        total_pages = payload.get("total_pages", page)
        if page >= total_pages or not batch:
            break
        page += 1
    if arena_only:
        return [event for event in events if ARENA_TAG in event.tag_slugs]
    return events


def group_events(events: list[ScribeEvent]) -> list[EventGroup]:
    groups: dict[tuple, EventGroup] = {}
    for event in events:
        key = (event.group_label, event.start.date(), event.end.date())
        group = groups.get(key)
        if group is None:
            group = EventGroup(
                label=event.group_label,
                start=event.start,
                end=event.end,
                start_local=event.start_local,
                end_local=event.end_local,
            )
            groups[key] = group
        if event.format_label and event.format_label not in group.formats:
            group.formats.append(event.format_label)
        if FLASHBACK_TAG in event.tag_slugs:
            group.flashback = True
        if any(CUBE_TAG in tag for tag in event.tag_slugs):
            group.cube = True
    return list(groups.values())


def partition_by_now(groups: list[EventGroup], now: datetime) -> tuple[list[EventGroup], list[EventGroup]]:
    """Split groups into (in-progress, upcoming), dropping anything already ended.

    In-progress leads with the latest end (most time left at the top); upcoming leads
    with whatever begins next.
    """
    in_progress: list[EventGroup] = []
    upcoming: list[EventGroup] = []
    for group in groups:
        if group.end < now:
            continue
        if group.start <= now:
            in_progress.append(group)
        else:
            upcoming.append(group)
    in_progress.sort(key=lambda group: group.end, reverse=True)
    upcoming.sort(key=lambda group: group.start)
    return in_progress, upcoming


def _get_page(start_date: date, page: int, cache_bust: str) -> dict:
    """``_cb`` busts MTG Scribe's CDN cache, which keys on the query string and otherwise
    serves stale dates (a Cache-Control header doesn't reach origin, a unique param does)."""
    params = {"start_date": start_date.isoformat(), "per_page": PER_PAGE, "page": page, "_cb": cache_bust}
    response = requests.get(EVENTS_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _parse_event(raw: dict) -> ScribeEvent:
    title = raw.get("title", "").strip()
    format_label, group_label = _split_title(title)
    tag_slugs = tuple(tag.get("slug", "") for tag in raw.get("tags", []))
    return ScribeEvent(
        title=title,
        format_label=format_label,
        group_label=group_label,
        start=_parse_utc(raw["utc_start_date"]),
        end=_parse_utc(raw["utc_end_date"]),
        start_local=_parse_naive(raw["start_date"]),
        end_local=_parse_naive(raw["end_date"]),
        tag_slugs=tag_slugs,
    )


def _split_title(title: str) -> tuple[str, str]:
    """Titles read ``"<format>: <set>"`` ("Premier Draft: Secrets of Strixhaven").

    The set is the grouping label; the format is what gets listed under it. Titles
    without a colon (release weekends, prereleases) carry no format and group on the
    whole title.
    """
    if ": " in title:
        format_label, group_label = title.split(": ", 1)
        return format_label, group_label
    return "", title


def _parse_utc(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _parse_naive(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
