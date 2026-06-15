from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import format_dt

from bot import audit
from bot.commands import descriptions as desc
from bot.discord_helpers import NBSP
from bot.services import mtgscribe
from bot.services.scribe_formats import short_format
from bot.sets import ALL_SETS

logger = logging.getLogger(__name__)

LOOKBACK = timedelta(days=90)
UPCOMING_HORIZON = timedelta(days=45)

IN_PROGRESS_EMOJI = "⚡"
COMING_UP_EMOJI = "🗓️"

MTGA_EMOJI_NAME = "mtga"
SET_LABEL_ALIASES: dict[str, str] = {"Arena Cube": "CUBE"}

ARENA_DIRECT_TAG = "arena-direct"
MIDWEEK_TAG = "midweek-magic"
COMPETITIVE_TAGS = ("play-in", "qualifier", "arena-championship", "arena-limited-championship-qualifier")
PREMIER_FORMATS = ("Premier Draft", "Contender Draft")
BOOSTER_LABELS = {"play-boosters": "Play", "collector-booster": "Collector"}
PACKAGE_EMOJI = "📦"
COLLECTOR_EMOJI_NAME = "8000gems"
ARENA_CHAMP_TEXT = "Arena Championship"
ARENA_CHAMP_EMOJI_NAME = "arenachamp"

SCRIBE_LOGO = Path(__file__).resolve().parents[2] / "bot" / "assets" / "mtg-scribe.png"
SCRIBE_LOGO_FILENAME = "mtg-scribe.png"
SCRIBE_URL = "https://mtgscribe.com/events/"


class EventScribe(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="event-scribe", description=desc.EVENT_SCRIBE)
    @app_commands.describe(format="Only show this format family", set="Only show this set")
    @app_commands.choices(format=[
        app_commands.Choice(name="Premier", value="premier"),
        app_commands.Choice(name="Quick", value="quick"),
        app_commands.Choice(name="Draft (all draft formats)", value="draft"),
        app_commands.Choice(name="Sealed (incl. Arena Direct)", value="sealed"),
        app_commands.Choice(name="Midweek", value="midweek"),
        app_commands.Choice(name="Competitive (play-in, qualifiers)", value="competitive"),
    ])
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def event_scribe(self, interaction: discord.Interaction,
                           format: app_commands.Choice[str] | None = None,
                           set: str | None = None) -> None:
        await interaction.response.defer()
        start_date = date.today() - LOOKBACK
        selected = format.value if format else None
        try:
            events = await asyncio.to_thread(mtgscribe.fetch_events, start_date)
        except Exception:
            logger.exception(f"event-scribe fetch failed for start_date={start_date}")
            await interaction.followup.send("MTG Scribe events are unavailable right now. Try again later.")
            return
        in_progress, upcoming = process_events(events, selected, set)
        emojis = {emoji.name: emoji for emoji in await self.bot.fetch_application_emojis()}
        audit.event(
            "event_scribe_invoked",
            user_id=str(interaction.user.id),
            format=selected or "all",
            set=set or "all",
            in_progress=len(in_progress),
            upcoming=len(upcoming),
        )
        subtitle = _subtitle(set, selected)
        await interaction.followup.send(**build_schedule_payload(in_progress, upcoming, emojis, subtitle))

    @event_scribe.autocomplete("set")
    async def event_scribe_set_autocomplete(
        self, interaction: discord.Interaction, current: str,
    ) -> list[app_commands.Choice[str]]:
        lowered = current.lower()
        matches = [app_commands.Choice(name=seed.name, value=seed.name)
                   for seed in ALL_SETS if lowered in seed.name.lower()]
        return matches[:25]


def process_events(events: list, selected: str | None = None, set_query: str | None = None) -> tuple[list, list]:
    """The shared event-scribe pipeline: scope → filter → normalize → group → partition. Both the
    /event-scribe command and `!test scribe` route through this so they can't drift. The unfiltered
    view drops upcoming events past the horizon; an explicit filter shows everything it matches."""
    normalized = [normalize_event(event) for event in events]
    kept = [event for event in normalized
            if _in_scope(event, selected) and _passes_format(event, selected) and _passes_set(event, set_query)]
    groups = mtgscribe.group_events(kept)
    now = datetime.now(timezone.utc)
    in_progress, upcoming = mtgscribe.partition_by_now(groups, now)
    if selected is None and set_query is None:
        horizon = now + UPCOMING_HORIZON
        upcoming = [group for group in upcoming if group.start <= horizon]
    return in_progress, upcoming


def _in_scope(event: mtgscribe.ScribeEvent, selected: str | None) -> bool:
    """The schedule is Limited-only, except the Midweek filter, which surfaces every Midweek
    queue (Brawl, Pauper, Momir included)."""
    if selected == "midweek":
        return True
    return "limited" in event.tag_slugs


def build_schedule_payload(in_progress: list, upcoming: list, emojis: dict, subtitle: str | None = None) -> dict:
    logo_url = f"attachment://{SCRIBE_LOGO_FILENAME}" if SCRIBE_LOGO.exists() else None
    view = discord.ui.View()
    view.add_item(discord.ui.Button(
        style=discord.ButtonStyle.link,
        label="View on MTG Scribe",
        url=SCRIBE_URL,
        emoji=emojis.get("scribe"),
    ))
    embed = render_schedule_embed(in_progress, upcoming, emojis, logo_url, subtitle)
    payload = {"embed": embed, "view": view}
    if logo_url:
        payload["file"] = discord.File(SCRIBE_LOGO, filename=SCRIBE_LOGO_FILENAME)
    return payload


def render_schedule_embed(in_progress: list, upcoming: list, emojis: dict, logo_url: str | None,
                          subtitle: str | None = None) -> discord.Embed:
    embed = discord.Embed(color=discord.Color.blurple())
    mtga = emojis.get(MTGA_EMOJI_NAME)
    heading = f"Limited Event Schedule - {subtitle}" if subtitle else "Limited Event Schedule"
    title = f"### {mtga} {heading}" if mtga else f"### {heading}"
    sections = [title]
    if in_progress:
        sections.append(f"### {IN_PROGRESS_EMOJI} In Progress")
        sections.extend(_set_block(label, windows, emojis, upcoming=False)
                        for label, windows in _by_set(in_progress).items())
    if upcoming:
        sections.append(f"### {COMING_UP_EMOJI} Coming Up")
        sections.extend(_set_block(label, windows, emojis, upcoming=True)
                        for label, windows in _by_set(upcoming).items())
    if not in_progress and not upcoming:
        sections.append("No Limited events right now.")
    embed.description = "\n".join(sections)
    if logo_url:
        embed.set_thumbnail(url=logo_url)
    return embed


def _by_set(groups: list) -> dict:
    """Collapse same-set windows under one header; insertion order keeps sets start-sorted."""
    ordered: dict[str, list] = {}
    for group in groups:
        ordered.setdefault(group.label, []).append(group)
    return ordered


def _set_block(label: str, windows: list, emojis: dict, *, upcoming: bool) -> str:
    items = [_format_line(group, emojis, upcoming=upcoming) for group in _by_format(windows)]
    lines = [f"{_set_emoji_prefix(label, emojis)}**{label}**"]
    for index, item in enumerate(items):
        corner = "└" if index == len(items) - 1 else "├"
        lines.append(f"{NBSP}{corner}{NBSP}{NBSP}{item}")
    return "\n".join(lines)


def _by_format(windows: list) -> list:
    """Collapse same-format windows (e.g. several Arena Direct Play) onto one line."""
    grouped: dict[str, list] = {}
    for window in windows:
        grouped.setdefault(_format_label(window), []).append(window)
    return list(grouped.values())


def _format_line(windows: list, emojis: dict, *, upcoming: bool) -> str:
    """Render one format's line content (no branch). When a format recurs across several windows,
    only the soonest is shown, with its countdown."""
    first = windows[0]
    label = _decorate_arena_champ(_format_label(first), emojis)
    suffix = _booster_emoji_suffix(first, emojis)
    if not label:
        lead = ""
    elif suffix:
        lead = f"{label}{suffix} "
    else:
        lead = f"{label} · "
    if upcoming:
        window = _date_range(first.start_local, first.end_local)
        return f"{lead}{window} · starts {format_dt(first.start, 'R')}"
    return f"{lead}ends {first.end_local:%B %-d} {format_dt(first.end, 'R')}"


def _decorate_arena_champ(formats: str, emojis: dict) -> str:
    emoji = emojis.get(ARENA_CHAMP_EMOJI_NAME)
    return formats.replace(ARENA_CHAMP_TEXT, str(emoji)) if emoji else formats


def _booster_emoji_suffix(group: mtgscribe.EventGroup, emojis: dict) -> str:
    joined = " ".join(group.formats)
    if "Arena Direct Play" in joined:
        return f" {PACKAGE_EMOJI}"
    if "Arena Direct Collector" in joined:
        emoji = emojis.get(COLLECTOR_EMOJI_NAME)
        return f" {emoji}" if emoji else ""
    return ""


FORMAT_PRIORITY = {"Premier Draft": 0, "Traditional Draft": 1, "Pick Two": 2, "Pick 2 Draft": 2, "Quick Draft": 3}


def _format_label(group: mtgscribe.EventGroup) -> str:
    if not group.formats:
        return ""
    if len(group.formats) == 1:
        return group.formats[0]
    if len(group.formats) > 3:
        ranked = sorted(group.formats, key=lambda label: FORMAT_PRIORITY.get(label, 99))
        return f"{_join_formats(ranked[:2])} and others"
    return _join_formats(group.formats)


def _join_formats(formats: list) -> str:
    joined = ", ".join(short_format(label) for label in formats)
    return joined if "Draft" in joined else f"{joined} Draft"


def _date_range(start: datetime, end: datetime) -> str:
    if (start.year, start.month) == (end.year, end.month):
        return f"{start:%B %-d}–{end:%-d}"
    return f"{start:%B %-d}–{end:%B %-d}"


def _set_emoji_prefix(label: str, emojis: dict) -> str:
    seed = _seed_for_label(label)
    code = SET_LABEL_ALIASES.get(label) or (seed.code if seed else None)
    emoji = emojis.get(code.lower()) if code else None
    return f"{emoji} " if emoji else ""


def _clean_set_label(label: str) -> str:
    """Collapse a set name buried in qualifier words (e.g. "Sealed Marvel Super Heroes Bo3") to
    the bare set, so every queue for a set groups under one header."""
    seed = _seed_for_label(label)
    return seed.name if seed else label


def _seed_for_label(label: str):
    lowered = label.lower()
    for seed in ALL_SETS:
        if seed.name.lower() in lowered:
            return seed
    return None


def _passes_format(event: mtgscribe.ScribeEvent, selected: str | None) -> bool:
    if selected is None:
        return True
    if selected == "premier":
        return event.format_label in PREMIER_FORMATS
    if selected == "quick":
        return event.format_label == "Quick Draft"
    if selected == "draft":
        return any("draft" in tag for tag in event.tag_slugs)
    if selected == "sealed":
        return any(tag in ("sealed", "traditional-sealed") for tag in event.tag_slugs)
    if selected == "midweek":
        return MIDWEEK_TAG in event.tag_slugs
    if selected == "competitive":
        return _is_competitive(event.tag_slugs)
    return True


def _is_competitive(tag_slugs: tuple) -> bool:
    return any(tag in tag_slugs for tag in COMPETITIVE_TAGS)


def _passes_set(event: mtgscribe.ScribeEvent, set_query: str | None) -> bool:
    return not set_query or set_query.lower() in event.group_label.lower()


def _subtitle(set_query: str | None, selected: str | None) -> str | None:
    parts = []
    if set_query:
        parts.append(set_query)
    if selected:
        parts.append(selected.capitalize())
    return " · ".join(parts) if parts else None


def normalize_event(event: mtgscribe.ScribeEvent) -> mtgscribe.ScribeEvent:
    """Clean the set label so every queue groups under one header, and fix up the format label for
    event families whose title structure hides it:
    - Arena Direct ("Arena Direct: <set> <product>") → set from tags, product as format.
    - Midweek Magic ("Midweek Magic: <set> <format>") → the real format (Quick Draft, Phantom Sealed).
    - Competitive (play-in / qualifier) → keep the Bo1/Bo3 differentiator from the title.
    """
    if ARENA_DIRECT_TAG in event.tag_slugs:
        set_name = _set_name_from_tags(event.tag_slugs) or _clean_set_label(event.group_label)
        booster = next((label for slug, label in BOOSTER_LABELS.items() if slug in event.tag_slugs), None)
        format_label = f"Arena Direct {booster}" if booster else "Arena Direct"
        return replace(event, group_label=set_name, format_label=format_label)
    if MIDWEEK_TAG in event.tag_slugs:
        return _normalize_midweek(event)
    set_name = _clean_set_label(event.group_label)
    format_label = event.format_label
    if _is_competitive(event.tag_slugs):
        format_label = _with_best_of(format_label, event.title)
    if set_name == event.group_label and format_label == event.format_label:
        return event
    return replace(event, group_label=set_name, format_label=format_label)


def _normalize_midweek(event: mtgscribe.ScribeEvent) -> mtgscribe.ScribeEvent:
    """Set-bearing Midweeks ("Midweek Magic: SoS Phantom Sealed") group under the set with the real
    format; set-less ones ("Midweek Magic: Brawl", crossovers) group under a "Midweek Magic" header."""
    label = event.group_label
    seed = None if "+" in label else _seed_for_label(label)
    if seed:
        leftover = label.replace(seed.name, "").strip()
        return replace(event, group_label=seed.name, format_label=leftover or event.format_label)
    return replace(event, group_label="Midweek Magic", format_label=label)


def _with_best_of(format_label: str, title: str) -> str:
    for best_of in ("Bo1", "Bo3"):
        if best_of in title and best_of not in format_label:
            return f"{format_label} {best_of}"
    return format_label


def _set_name_from_tags(tag_slugs: tuple) -> str | None:
    for seed in ALL_SETS:
        if _slugify(seed.name) in tag_slugs:
            return seed.name
    return None


def _slugify(name: str) -> str:
    return name.lower().replace(":", "").replace(" ", "-")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventScribe(bot))
