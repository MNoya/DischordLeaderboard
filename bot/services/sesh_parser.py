"""Parse sesh.fyi RSVP embeds into pod-draft fields. Pure parsing — no Discord client, no DB.

Ground-truth shape from a captured sesh embed:
    title:                  ":calendar_spiral:  **SOS Pod Draft Test #1**"   (Discord markdown)
    field "Time":           "<t:1778720421:F> (<t:1778720421:R>) [[+]](url)"  (unix seconds UTC)
    field "Attendees (N)":  names one per line, "> -" placeholder when empty

"is starting now!" reminders have no Time field and are naturally rejected.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord

from bot.config import settings


log = logging.getLogger(__name__)


# Discord native timestamp: <t:UNIX[:FORMAT]>, captures the unix-seconds value
TIMESTAMP_RE = re.compile(r"<t:(\d+)(?::[A-Za-z])?>")

# Title regex: set code is any 2-5 uppercase letters; event number is "#N"
SET_RE = re.compile(r"\b([A-Z]{2,5})\b")
NUM_RE = re.compile(r"#(\d+)")

# Discord shortcode emoji form, e.g. :calendar_spiral:
SHORTCODE_RE = re.compile(r":[a-z0-9_+-]+:")


@dataclass(frozen=True)
class ParsedSeshFields:
    """Parser output. set_code and event_number are None when missing — caller defaults or skips them."""
    event_date: date            # in POD_DRAFT_FALLBACK_TZ
    event_time: datetime        # tz-aware UTC
    set_code: str | None
    event_number: int | None    # from "#N" in title, used by draftmancer_session naming only
    format_label: str | None    # always None in Phase 1
    name: str                   # cleaned title, becomes pod_draft_events.name
    attendees: Sequence[str]
    maybe_attendees: Sequence[str]


def parse_sesh_embed(embed: discord.Embed) -> ParsedSeshFields | None:
    """Return parsed fields if the embed has a Time field (with <t:UNIX>) and an Attendees field, else None."""
    time_field = _find_field(embed, "Time", exact=True)
    attendees_field = _find_field(embed, "Attendees")
    if time_field is None or attendees_field is None:
        return None

    clean_title = _strip_markdown(embed.title or "").strip()

    set_match = SET_RE.search(clean_title)
    set_code = set_match.group(1) if set_match else None
    num_match = NUM_RE.search(clean_title)
    event_number = int(num_match.group(1)) if num_match else None

    event_time = _parse_event_time(time_field.value or "")
    if event_time is None:
        log.warning("sesh embed %r Time field has no <t:UNIX> timestamp: %r",
                    embed.title, time_field.value)
        return None

    try:
        tz = ZoneInfo(settings.pod_draft_fallback_tz)
    except ZoneInfoNotFoundError:
        log.warning("POD_DRAFT_FALLBACK_TZ=%r is not a known IANA zone; falling back to UTC",
                    settings.pod_draft_fallback_tz)
        tz = ZoneInfo("UTC")
    event_date = event_time.astimezone(tz).date()

    attendees = _parse_attendees(attendees_field.value or "")
    maybe_field = _find_field(embed, "Maybe")
    maybe_attendees = _parse_attendees(maybe_field.value or "") if maybe_field else []

    return ParsedSeshFields(
        event_date=event_date,
        event_time=event_time,
        set_code=set_code,
        event_number=event_number,
        format_label=None,
        name=clean_title,
        attendees=attendees,
        maybe_attendees=maybe_attendees,
    )


def _strip_markdown(title: str) -> str:
    """Strip Discord shortcode emojis (:foo:) and bold/italic markers; Unicode emojis pass through."""
    t = SHORTCODE_RE.sub("", title)
    t = t.replace("**", "").replace("__", "")
    return t


def _find_field(embed: discord.Embed, name: str, *, exact: bool = False) -> discord.embeds.EmbedProxy | None:
    """Find a field by name. Default is substring match (so "Attendees" hits "✅ Attendees (7)")."""
    target = name.lower()
    for field in embed.fields:
        fname = (field.name or "").lower()
        if exact and fname == target:
            return field
        if not exact and target in fname:
            return field
    return None


def _parse_event_time(field_value: str) -> datetime | None:
    m = TIMESTAMP_RE.search(field_value)
    if m is None:
        return None
    return datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc)


def _parse_attendees(field_value: str) -> list[str]:
    """Names, one per line; strips Discord block-quote prefixes (> / >> / >>>) and dash placeholders."""
    result: list[str] = []
    for raw in field_value.splitlines():
        line = raw.lstrip(">").strip()
        if not line or line in {"-", "—"}:
            continue
        result.append(line)
    return result
