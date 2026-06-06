"""Monday schedule post + owner /create DMs, fired by an APScheduler cron job.

Normal Mondays post the week's flavor blurb + slot embed in the coordination channel, then DM
the owner one pre-filled Sesh /create per slot. Release-week Mondays swap to a "react 👍" opt-in
message and championship-week Mondays to a Set Championship promo; neither sends /create DMs.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time

import discord
from discord.ext import commands
from sqlalchemy import func, select

from bot.config import settings
from bot.database import SessionLocal
from bot.models import PodDraftEvent
from bot.services.pod_schedule import (
    MONDAY_KIND_CHAMPIONSHIP_WEEK,
    MONDAY_KIND_RELEASE_WEEK,
    MSG_CHAMPIONSHIP_WEEK,
    MSG_CREATE_DM_HEADER,
    MSG_RELEASE_WEEK,
    MSG_SCHEDULE_EMBED_TITLE,
    SCHEDULE_TZ,
    UpcomingRelease,
    build_create_command,
    monday_blurb,
    monday_kind,
    slots_for_week,
    week_index_for,
)
from bot.sets import ACTIVE_SET_CODE


WEEKLY_POST_HOUR_ET = 12

log = logging.getLogger(__name__)

_bot: commands.Bot | None = None


def init_schedule_post(bot: commands.Bot) -> None:
    """Wire the bot reference and arm the Monday cron job on bot.pod_scheduler."""
    global _bot
    _bot = bot
    if not settings.pod_schedule_enabled:
        log.info("POD_SCHEDULE_ENABLED=false; weekly schedule post disabled")
        return
    bot.pod_scheduler.add_job(
        fire_weekly_post,
        "cron",
        day_of_week="mon",
        hour=WEEKLY_POST_HOUR_ET,
        minute=0,
        timezone=SCHEDULE_TZ,
        id="pod-weekly-schedule",
        replace_existing=True,
    )
    log.info(f"weekly schedule post armed for Mondays {WEEKLY_POST_HOUR_ET}:00 {SCHEDULE_TZ.key}")


async def fire_weekly_post() -> None:
    if _bot is None:
        log.error("fire_weekly_post: bot reference is not initialised")
        return
    channel = await _fetch_coordination_channel()
    if channel is None:
        return

    monday = datetime.now(SCHEDULE_TZ).date()
    kind, release = monday_kind(monday)

    if kind == MONDAY_KIND_RELEASE_WEEK:
        await _post_release_week(channel, release)
        return
    if kind == MONDAY_KIND_CHAMPIONSHIP_WEEK:
        await _post_championship_week(channel, release)
        return

    slots = slots_for_week(monday)
    blurb = monday_blurb(ACTIVE_SET_CODE, week_index_for(ACTIVE_SET_CODE, monday))
    embed = _build_schedule_embed(slots)
    await channel.send(content=blurb, embed=embed)
    log.info(f"posted weekly schedule for {monday.isoformat()}")
    await _dm_create_commands(slots)


async def _post_release_week(channel: discord.abc.Messageable, release: UpcomingRelease) -> None:
    body = MSG_RELEASE_WEEK.format(set_name=release.name, unix=_release_unix(release))
    message = await channel.send(body)
    try:
        await message.add_reaction("👍")
    except discord.HTTPException:
        log.warning("could not add 👍 reaction to release-week post", exc_info=True)
    log.info(f"posted release-week opt-in message ({release.code})")


async def _post_championship_week(channel: discord.abc.Messageable, release: UpcomingRelease) -> None:
    body = MSG_CHAMPIONSHIP_WEEK.format(
        set_code=ACTIVE_SET_CODE, next_name=release.name, unix=_release_unix(release),
    )
    await channel.send(body)
    log.info(f"posted championship-week promo ({ACTIVE_SET_CODE} → {release.code})")


def _build_schedule_embed(slots: list[datetime]) -> discord.Embed:
    lines = []
    for slot in slots:
        unix = int(slot.timestamp())
        lines.append(f"• <t:{unix}:F> (<t:{unix}:R>)")
    return discord.Embed(
        title=MSG_SCHEDULE_EMBED_TITLE.format(set_code=ACTIVE_SET_CODE),
        description="\n".join(lines),
        color=discord.Color.blurple(),
    )


async def _dm_create_commands(slots: list[datetime]) -> None:
    owner = await _fetch_owner()
    if owner is None:
        return
    event_count = await asyncio.to_thread(_count_set_events)
    blocks = []
    for i, slot in enumerate(slots):
        command = build_create_command(ACTIVE_SET_CODE, event_count + 1 + i, slot)
        blocks.append(f"```\n{command}\n```")
    body = MSG_CREATE_DM_HEADER + "\n" + "\n".join(blocks)
    try:
        await owner.send(body)
        log.info(f"DM'd {len(blocks)} /create command(s) to owner")
    except discord.HTTPException:
        log.warning("could not DM /create commands to owner", exc_info=True)


async def _fetch_coordination_channel() -> discord.abc.Messageable | None:
    channel = _bot.get_channel(settings.pod_draft_channel_id)
    if channel is not None:
        return channel
    try:
        return await _bot.fetch_channel(settings.pod_draft_channel_id)
    except discord.HTTPException as e:
        log.warning(f"could not fetch coordination channel {settings.pod_draft_channel_id}: {e}")
        return None


async def _fetch_owner() -> discord.User | None:
    if _bot.owner_id is None:
        log.warning("owner_id not set; skipping /create DMs")
        return None
    try:
        return _bot.get_user(_bot.owner_id) or await _bot.fetch_user(_bot.owner_id)
    except discord.HTTPException as e:
        log.warning(f"could not fetch owner {_bot.owner_id}: {e}")
        return None


def _count_set_events() -> int:
    with SessionLocal() as session:
        count = session.execute(
            select(func.count()).select_from(PodDraftEvent).where(PodDraftEvent.set_code == ACTIVE_SET_CODE)
        ).scalar()
        return count or 0


def _release_unix(release: UpcomingRelease) -> int:
    release_moment = datetime.combine(release.release_date, time(12, 0), tzinfo=SCHEDULE_TZ)
    return int(release_moment.timestamp())
