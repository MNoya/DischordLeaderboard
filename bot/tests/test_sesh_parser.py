from datetime import date, datetime, timezone

import discord
import pytest

from bot.config import settings
from bot.services.sesh_parser import parse_sesh_embed


# Real unix timestamp from a captured sesh embed: 2026-05-14 01:00:21 UTC
SAMPLE_UNIX = 1778720421
SAMPLE_UTC = datetime(2026, 5, 14, 1, 0, 21, tzinfo=timezone.utc)


def _make_embed(
    title: str | None,
    *,
    time_field: str | None = f"<t:{SAMPLE_UNIX}:F> (<t:{SAMPLE_UNIX}:R>) [[+]](http://example.com)",
    attendees_field: str | None = "> Arcyl\n> WaveofShadow\n> Chonce",
    include_maybe_no: bool = True,
) -> discord.Embed:
    embed = discord.Embed(title=title)
    if time_field is not None:
        embed.add_field(name="Time", value=time_field, inline=False)
    if attendees_field is not None:
        embed.add_field(name="✅ Attendees (3)", value=attendees_field, inline=True)
    if include_maybe_no:
        embed.add_field(name="🤷 Maybe (0)", value="> -", inline=True)
        embed.add_field(name="❌ No (0)", value="> -", inline=True)
    return embed


def test_parses_real_sesh_embed():
    embed = _make_embed(":calendar_spiral:  **SOS Pod Draft Test #1**")
    result = parse_sesh_embed(embed)

    assert result is not None
    assert result.event_number == 1
    assert result.set_code == "SOS"
    assert result.event_time == SAMPLE_UTC
    assert result.format_label is None
    assert result.name == "SOS Pod Draft Test #1"
    assert list(result.attendees) == ["Arcyl", "WaveofShadow", "Chonce"]


def test_parses_classic_title_shape():
    embed = _make_embed("📅 SOS Pod Draft #3 - May 13")
    result = parse_sesh_embed(embed)
    assert result is not None
    assert result.set_code == "SOS"
    assert result.event_number == 3


def test_title_with_no_extras_parses():
    embed = _make_embed("SOS Pod Draft #4")
    result = parse_sesh_embed(embed)
    assert result is not None
    assert result.set_code == "SOS"
    assert result.event_number == 4


def test_starting_now_reminder_returns_none():
    embed = discord.Embed(title="SOS Pod Draft #2 - May 6 is starting now!")
    embed.add_field(name="Event Details", value="...", inline=False)
    assert parse_sesh_embed(embed) is None


def test_title_without_event_number_leaves_it_none():
    embed = _make_embed("SOS Pod Draft")
    result = parse_sesh_embed(embed)
    assert result is not None
    assert result.set_code == "SOS"
    assert result.event_number is None


def test_title_without_set_code_leaves_it_none():
    embed = _make_embed("pod draft #1 - May 13")
    result = parse_sesh_embed(embed)
    assert result is not None
    assert result.set_code is None
    assert result.event_number == 1


def test_minimal_title_still_parses():
    embed = _make_embed("test4")
    result = parse_sesh_embed(embed)
    assert result is not None
    assert result.set_code is None
    assert result.event_number is None
    assert result.name == "test4"


def test_missing_time_field_returns_none():
    embed = _make_embed("SOS Pod Draft #5", time_field=None)
    assert parse_sesh_embed(embed) is None


def test_missing_attendees_field_returns_none():
    embed = _make_embed("SOS Pod Draft #5", attendees_field=None)
    assert parse_sesh_embed(embed) is None


def test_time_field_without_timestamp_returns_none():
    embed = _make_embed(
        "SOS Pod Draft #5",
        time_field="Wednesday, May 13, 2026 at 9:00 PM",
    )
    assert parse_sesh_embed(embed) is None


def test_empty_attendees_placeholder_yields_empty_list():
    embed = _make_embed("SOS Pod Draft #1", attendees_field="> -")
    result = parse_sesh_embed(embed)
    assert result is not None
    assert list(result.attendees) == []


def test_attendees_strips_block_quote_and_whitespace():
    embed = _make_embed(
        "SOS Pod Draft #1",
        attendees_field="> Alice  \n>Bob\n>  Carl#1234",
    )
    result = parse_sesh_embed(embed)
    assert result is not None
    assert list(result.attendees) == ["Alice", "Bob", "Carl#1234"]


def test_attendees_skips_blank_and_dash_lines():
    embed = _make_embed(
        "SOS Pod Draft #1",
        attendees_field="> Alice\n\n> -\n> Bob",
    )
    result = parse_sesh_embed(embed)
    assert result is not None
    assert list(result.attendees) == ["Alice", "Bob"]


def test_event_date_defaults_to_utc(monkeypatch):
    monkeypatch.setattr(settings, "pod_draft_fallback_tz", "UTC")
    embed = _make_embed("SOS Pod Draft #1")
    result = parse_sesh_embed(embed)
    assert result is not None
    assert result.event_date == date(2026, 5, 14)


def test_event_date_uses_fallback_tz_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "pod_draft_fallback_tz", "America/Montevideo")
    embed = _make_embed("SOS Pod Draft #1")
    result = parse_sesh_embed(embed)
    assert result is not None
    # 01:00 UTC = 22:00 prev-day in UTC-3
    assert result.event_date == date(2026, 5, 13)


def test_invalid_fallback_tz_falls_back_to_utc(monkeypatch):
    monkeypatch.setattr(settings, "pod_draft_fallback_tz", "Not/A/Zone")
    embed = _make_embed("SOS Pod Draft #1")
    result = parse_sesh_embed(embed)
    assert result is not None
    assert result.event_date == date(2026, 5, 14)


def test_title_markdown_stripped_for_name_and_regex():
    embed = _make_embed(":sparkles:  **TLA Pod Draft Test #7**")
    result = parse_sesh_embed(embed)
    assert result is not None
    assert result.set_code == "TLA"
    assert result.event_number == 7
    assert result.name == "TLA Pod Draft Test #7"


def test_embed_without_title_returns_none():
    embed = discord.Embed()
    assert parse_sesh_embed(embed) is None
