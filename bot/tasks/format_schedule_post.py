"""Scribe-driven format-schedule tick — fires at the few daily windows when MTGA queues open.

Each tick pulls the MTG Scribe calendar once and, per channel, (1) re-renders the pinned /event-scribe
in place so it never goes stale across a rotation, and (2) announces events that went live since the
previous window. Windows are Pacific (MTGA's clock), so an announcement lands right as the queue opens
and tracks DST. A channel can hold more than one pin (Quick Draft and Flashback share one), so a pin is
matched by its title rather than just authorship; announcement dedup scans recent channel history, so
no table is needed and a restart never double-announces.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from bot.commands.event_scribe import (
    build_announcement,
    build_competitive_reminder,
    build_schedule_view,
    schedule_title_marker,
    select_groups,
)
from bot.config import settings
from bot.services import mtgscribe
from bot.services.format_schedule import (
    ANNOUNCE_COMPETITIVE,
    ANNOUNCE_NONE,
    ANNOUNCE_WINDOWS,
    DEDUP_LOOKBACK,
    OPEN_TZ,
    SCHEDULE_PINS,
    SchedulePin,
    already_announced,
    announcement_format,
    latest_channel_in_category,
    newest_set,
    newly_opened,
    next_rotation,
    previous_window_start,
)

LOOKBACK_DAYS = 90
HISTORY_SCAN_LIMIT = 100

log = logging.getLogger(__name__)

_bot: commands.Bot | None = None


def init_format_schedule(bot: commands.Bot) -> None:
    global _bot
    _bot = bot
    if not settings.format_schedule_enabled:
        log.info("FORMAT_SCHEDULE_ENABLED=false; format-schedule tick disabled")
        return
    for window in ANNOUNCE_WINDOWS:
        bot.pod_scheduler.add_job(
            fire_window,
            "cron",
            hour=window.hour,
            minute=window.minute,
            timezone=OPEN_TZ,
            id=f"format-schedule-{window.hour:02d}{window.minute:02d}",
            replace_existing=True,
        )
    windows = ", ".join(f"{w.hour:02d}:{w.minute:02d}" for w in ANNOUNCE_WINDOWS)
    log.info(f"format-schedule armed: {windows} {OPEN_TZ.key}")


async def fire_window() -> None:
    if _bot is None:
        log.error("fire_window: bot reference is not initialised")
        return
    guild = _bot.get_guild(settings.discord_guild_id) if settings.discord_guild_id else None
    if guild is None:
        log.warning("format-schedule: guild unavailable; skipping tick")
        return

    now = datetime.now(timezone.utc)
    since = previous_window_start(now)
    start_date = (now - timedelta(days=LOOKBACK_DAYS)).date()
    events = await asyncio.to_thread(mtgscribe.fetch_events, start_date)
    emojis = {emoji.name: emoji for emoji in await _bot.fetch_application_emojis()}

    for pin in SCHEDULE_PINS:
        channel = _resolve_channel(guild, pin)
        if channel is None:
            continue
        if pin.maintain_pin:
            in_progress, upcoming, scope = select_pin(events, pin)
            await _refresh_pin(channel, scope, in_progress, upcoming, emojis, create_if_missing=pin.auto_pin)
        if pin.announce != ANNOUNCE_NONE:
            scheduled = announce_groups(events, pin)
            fresh = newly_opened(scheduled, since, now)
            await _announce(channel, pin, fresh, scheduled, emojis)


def select_pin(events: list, pin: SchedulePin) -> tuple[list, list, str]:
    """The pinned schedule's groups and its title scope: a format-filtered view, or the whole active
    set when the pin carries no format filter (the set channel). Untrimmed, to match what
    /event-scribe renders for an explicit filter or set."""
    if pin.pin_filters:
        in_progress, upcoming = select_groups(events, list(pin.pin_filters), apply_horizon=False)
        return in_progress, upcoming, pin.scope_label
    set_name = newest_set().name
    in_progress, upcoming = select_groups(events, None, set_name, apply_horizon=False)
    return in_progress, upcoming, set_name


def announce_groups(events: list, pin: SchedulePin) -> list:
    in_progress, upcoming = select_groups(events, list(pin.announce_filters), apply_horizon=False)
    return in_progress + upcoming


def _resolve_channel(guild: discord.Guild, pin: SchedulePin) -> discord.TextChannel | None:
    if pin.category is not None:
        channel = latest_channel_in_category(guild.text_channels, pin.category)
        if channel is None:
            log.info(f"format-schedule: no channel in category '{pin.category}' for {pin.key}")
        return channel
    for channel in guild.text_channels:
        if pin.channel_name in channel.name:
            return channel
    log.info(f"format-schedule: no channel matching '{pin.channel_name}' for {pin.key}")
    return None


async def _refresh_pin(channel: discord.TextChannel, scope: str, in_progress: list,
                       upcoming: list, emojis: dict, *, create_if_missing: bool = False) -> None:
    """Edit the pin in place, matching on the title so the right pin is edited when a channel holds
    several. Pins are human-seeded (the owner pins a filtered /event-scribe post) and a channel without
    a matching pin is left alone. ``create_if_missing`` would post and pin the schedule itself instead;
    no pin enables it today, reserved for when the bot should seed a channel's pin."""
    view = build_schedule_view(in_progress, upcoming, emojis, scope)
    message = await _pinned_schedule(channel, schedule_title_marker(scope))
    if message is None:
        if create_if_missing:
            await _create_pinned_schedule(channel, scope, view)
        return
    try:
        await message.edit(view=view)
    except discord.HTTPException:
        log.warning(f"format-schedule: could not edit the '{scope}' pin in #{channel.name}", exc_info=True)


async def _create_pinned_schedule(channel: discord.TextChannel, scope: str,
                                  view: discord.ui.LayoutView) -> None:
    """Post and pin a fresh schedule. ``_pinned_schedule`` only finds pinned posts, so an unpinned one
    would be re-created every tick — if the pin fails, the post is removed so creation stays atomic."""
    try:
        message = await channel.send(view=view)
    except discord.HTTPException:
        log.warning(f"format-schedule: could not post the '{scope}' pin in #{channel.name}", exc_info=True)
        return
    try:
        await message.pin()
    except discord.HTTPException:
        log.warning(f"format-schedule: could not pin the '{scope}' schedule in #{channel.name}; "
                    "removing the unpinned post", exc_info=True)
        await _delete_quietly(message)


async def _delete_quietly(message: discord.Message) -> None:
    try:
        await message.delete()
    except discord.HTTPException:
        log.warning("format-schedule: could not remove the unpinned schedule post", exc_info=True)


async def _pinned_schedule(channel: discord.TextChannel, marker: str) -> discord.Message | None:
    try:
        async for message in channel.pins():
            if _bot.user is not None and message.author.id == _bot.user.id and marker in _message_text(message):
                return message
    except discord.HTTPException:
        log.warning(f"format-schedule: could not read pins in #{channel.name}", exc_info=True)
    return None


def _message_text(message: discord.Message) -> str:
    """Flatten everything a bot message might carry its text in. A schedule pin is a Components V2
    message (title in a TextDisplay), an announcement is an embed (text in the description), and plain
    posts use ``content`` — so pin-matching and announcement dedup both read from one place."""
    parts = [message.content] if message.content else []
    for embed in message.embeds:
        if embed.title:
            parts.append(embed.title)
        if embed.description:
            parts.append(embed.description)
    parts.append(_component_text(message.components))
    return "\n".join(part for part in parts if part)


def _component_text(components) -> str:
    parts = []
    for component in components:
        content = getattr(component, "content", None)
        if isinstance(content, str):
            parts.append(content)
        children = getattr(component, "children", None)
        if children:
            parts.append(_component_text(children))
    return "\n".join(parts)


async def _announce(channel: discord.TextChannel, pin: SchedulePin, fresh: list,
                    scheduled: list, emojis: dict) -> None:
    """Announce each freshly-opened group. ``scheduled`` is the full filtered schedule (in-progress +
    upcoming), so the Next Up preview can look past ``fresh`` to the rotation that follows."""
    if not fresh:
        return
    recent = await _recent_bot_messages(channel)
    for group in fresh:
        embed, marker = announcement_for(pin, group, scheduled, emojis)
        if already_announced(recent, marker, group.label):
            continue
        try:
            await channel.send(embed=embed)
            recent.append(embed.description or "")
        except discord.HTTPException:
            log.warning(f"format-schedule: could not announce '{group.label}' in #{channel.name}", exc_info=True)


def announcement_for(pin: SchedulePin, group: mtgscribe.EventGroup, groups: list, emojis: dict):
    """Build the announcement embed and its dedup marker for a freshly-opened event. The single place
    both the tick and `!test formatschedule` route through, so they can't drift. Competitive pins get
    the reminder builder; the rest get the rotation "is live!" callout with a Next Up preview."""
    if pin.announce == ANNOUNCE_COMPETITIVE:
        return build_competitive_reminder(group, emojis), group.label
    word = announcement_format(group)
    embed = build_announcement(group, emojis, format_word=word, next_group=next_rotation(groups, group))
    return embed, word or "is live"


async def _recent_bot_messages(channel: discord.TextChannel) -> list[str]:
    since = datetime.now(timezone.utc) - DEDUP_LOOKBACK
    texts: list[str] = []
    try:
        async for message in channel.history(after=since, limit=HISTORY_SCAN_LIMIT):
            if _bot.user is None or message.author.id != _bot.user.id:
                continue
            text = _message_text(message)
            if text:
                texts.append(text)
    except discord.HTTPException:
        log.warning(f"format-schedule: could not scan #{channel.name} history", exc_info=True)
    return texts
