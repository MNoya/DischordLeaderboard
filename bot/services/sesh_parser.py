"""Parse sesh.fyi RSVP embeds into pod-draft fields.

Pure parsing — no Discord client, no DB. Takes a ``discord.Embed`` and returns
ParsedSeshFields if the embed is recognisably a pod-draft RSVP, else None.
The listener combines the result with sesh_message_id and discord_thread_id
before calling pod_drafts.record_event.

Ground-truth embed shape (from a real sesh embed JSON dump):

    title:        ":calendar_spiral:  **SOS Pod Draft Test #1**"
                  (Discord markdown — emoji shortcodes + bold)
    fields:
      "Time"                  -> "<t:1778720421:F> (<t:1778720421:R>) [[+]](url)"
                                 (Discord native timestamps — unix seconds UTC)
      "✅ Attendees (N)"      -> attendees, one per line, may be "> -" when empty
      "🤷 Maybe (N)"          -> ignored
      "❌ No (N)"             -> ignored

sesh's "is starting now!" reminder messages have a different title shape with
no Time field — naturally rejected here.
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


# Discord native timestamp: <t:UNIX[:FORMAT]>. Captures the unix-seconds value.
TIMESTAMP_RE = re.compile(r"<t:(\d+)(?::[A-Za-z])?>")

# Set code (2-5 uppercase letters) and event number from the title after
# stripping Discord markdown. Extra words like "Test" between them are allowed.
SET_RE = re.compile(r"\b([A-Z]{2,5})\b")
NUM_RE = re.compile(r"#(\d+)")

# Discord shortcode emoji form, e.g. :calendar_spiral:
SHORTCODE_RE = re.compile(r":[a-z0-9_+-]+:")


@dataclass(frozen=True)
class ParsedSeshFields:
    """Output of the parser before the listener attaches sesh_message_id and
    discord_thread_id."""
    event_number: int
    event_date: date            # date in POD_DRAFT_FALLBACK_TZ
    event_time: datetime        # tz-aware UTC moment
    set_code: str
    format_label: str | None    # always None in Phase 1
    name: str                   # cleaned title text, used for pod_draft_events.name
    attendees: Sequence[str]


def parse_sesh_embed(embed: discord.Embed) -> ParsedSeshFields | None:
    """Return parsed fields if this embed is a pod-draft RSVP, else None."""
    if not embed.title:
        return None

    clean_title = _strip_markdown(embed.title).strip()

    set_match = SET_RE.search(clean_title)
    num_match = NUM_RE.search(clean_title)
    if set_match is None or num_match is None:
        return None

    set_code = set_match.group(1)
    event_number = int(num_match.group(1))

    time_field = _find_field(embed, "Time", exact=True)
    attendees_field = _find_field(embed, "Attendees")
    if time_field is None or attendees_field is None:
        log.warning(
            "sesh embed %r matched title but is missing required fields "
            "(time=%s attendees=%s)",
            embed.title, time_field is not None, attendees_field is not None,
        )
        return None

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

    return ParsedSeshFields(
        event_number=event_number,
        event_date=event_date,
        event_time=event_time,
        set_code=set_code,
        format_label=None,
        name=clean_title,
        attendees=attendees,
    )


def _strip_markdown(title: str) -> str:
    """Remove Discord shortcode emojis (:foo:) and bold/italic asterisks.

    Unicode emojis pass through unchanged — they don't interfere with regex
    matches on ASCII letters and digits.
    """
    t = SHORTCODE_RE.sub("", title)
    t = t.replace("**", "").replace("__", "")
    return t


def _find_field(embed: discord.Embed, name: str, *, exact: bool = False) -> discord.embeds.EmbedProxy | None:
    """Look up an embed field by name. The Attendees field name carries an emoji
    prefix in sesh's output (e.g. "✅ Attendees (7)"), so name-substring matching
    is the default; exact=True for the Time field.
    """
    target = name.lower()
    for field in embed.fields:
        fname = (field.name or "").lower()
        if exact and fname == target:
            return field
        if not exact and target in fname:
            return field
    return None


def _parse_event_time(field_value: str) -> datetime | None:
    """Extract the unix-seconds timestamp from a `<t:UNIX:F>` token."""
    m = TIMESTAMP_RE.search(field_value)
    if m is None:
        return None
    return datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc)


def _parse_attendees(field_value: str) -> list[str]:
    """Split the Attendees field into clean display names.

    sesh prefixes lines with Discord block-quote markdown (``> ``) and uses
    a bare dash as the "no entries" placeholder. Both get stripped so the
    placeholder doesn't become a participant named "-".
    """
    result: list[str] = []
    for raw in field_value.splitlines():
        line = raw.strip()
        if line.startswith("> "):
            line = line[2:].strip()
        elif line.startswith(">"):
            line = line[1:].strip()
        if not line or line in {"-", "—"}:
            continue
        result.append(line)
    return result
