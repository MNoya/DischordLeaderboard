"""Monday schedule DM, owner buttons, and the fallback post — two APScheduler cron jobs.

The owner posts the weekly schedule personally; the bot ghostwrites it. At MONDAY_DM_HOUR_ET the
owner gets one DM: the paste-ready message in a code block, the week's Sesh /create blocks, and
Post-it-for-me / I've-got-it / Skip buttons. At FALLBACK_POST_HOUR_ET a second cron posts the
default version unless the week was handled — guarded by a channel scan for an already-posted
schedule, so a manual post without a button press never double-posts.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timedelta

import discord
from discord.ext import commands
from sqlalchemy import func, select

from bot.config import settings
from bot.database import SessionLocal
from bot.models import PodDraftEvent
from bot.services.pod_schedule import (
    BTN_GOT_IT,
    BTN_POST_FOR_ME,
    BTN_SKIP,
    MONDAY_KIND_NORMAL,
    MONDAY_KIND_RELEASE_WEEK,
    MSG_BTN_ALREADY_POSTED,
    MSG_BTN_GOT_IT,
    MSG_BTN_POSTED,
    MSG_BTN_SKIPPED,
    MSG_CREATE_DM_HEADER,
    MSG_MONDAY_DM_INTRO,
    SCHEDULE_TZ,
    build_create_command,
    compose_monday_message,
    monday_kind,
    slots_for_week,
)
from bot.sets import ACTIVE_SET_CODE


MONDAY_DM_HOUR_ET = 9
FALLBACK_POST_HOUR_ET = 12

STATUS_HANDLED = "handled"
STATUS_SKIPPED = "skipped"

log = logging.getLogger(__name__)

_bot: commands.Bot | None = None
_week_status: dict[str, str] = {}


def init_schedule_post(bot: commands.Bot) -> None:
    """Wire the bot reference, register the persistent DM buttons, and arm both Monday cron jobs."""
    global _bot
    _bot = bot
    bot.add_view(PodMondayView())
    if not settings.pod_schedule_enabled:
        log.info("POD_SCHEDULE_ENABLED=false; weekly schedule flow disabled")
        return
    bot.pod_scheduler.add_job(
        fire_monday_dm,
        "cron",
        day_of_week="mon",
        hour=MONDAY_DM_HOUR_ET,
        minute=0,
        timezone=SCHEDULE_TZ,
        id="pod-monday-dm",
        replace_existing=True,
    )
    bot.pod_scheduler.add_job(
        fire_fallback_post,
        "cron",
        day_of_week="mon",
        hour=FALLBACK_POST_HOUR_ET,
        minute=0,
        timezone=SCHEDULE_TZ,
        id="pod-monday-fallback",
        replace_existing=True,
    )
    log.info(
        f"weekly schedule flow armed: DM Mondays {MONDAY_DM_HOUR_ET}:00, "
        f"fallback {FALLBACK_POST_HOUR_ET}:00 {SCHEDULE_TZ.key}"
    )


async def fire_monday_dm(monday: date | None = None) -> None:
    if _bot is None:
        log.error("fire_monday_dm: bot reference is not initialised")
        return
    owner = await _fetch_owner()
    if owner is None:
        return

    monday = monday or _upcoming_monday()
    message = compose_monday_message(monday, ACTIVE_SET_CODE)
    parts = [MSG_MONDAY_DM_INTRO, f"```\n{message}\n```"]

    kind, _ = monday_kind(monday)
    if kind == MONDAY_KIND_NORMAL:
        parts.append(MSG_CREATE_DM_HEADER)
        parts.extend(await _create_command_blocks(monday))

    try:
        await owner.send("\n".join(parts), view=PodMondayView(monday))
        log.info(f"monday schedule DM sent for {monday.isoformat()} ({kind})")
    except discord.HTTPException:
        log.warning("could not DM the monday schedule draft to owner", exc_info=True)


async def fire_fallback_post() -> None:
    if _bot is None:
        log.error("fire_fallback_post: bot reference is not initialised")
        return
    monday = _upcoming_monday()
    status = _week_status.get(monday.isoformat())
    if status is not None:
        log.info(f"fallback post for {monday.isoformat()}: week already {status}; standing down")
        return
    await _post_default_if_needed()


class PodMondayView(discord.ui.View):
    """Persistent (timeout=None) so buttons survive restarts; the restored copy falls back to the current week."""

    def __init__(self, monday: date | None = None) -> None:
        super().__init__(timeout=None)
        self._monday = monday

    def _week(self) -> date:
        return self._monday or _upcoming_monday()

    @discord.ui.button(label=BTN_POST_FOR_ME, style=discord.ButtonStyle.primary, custom_id="pod-monday-post")
    async def post_for_me(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        _week_status[self._week().isoformat()] = STATUS_HANDLED
        posted = await _post_default_if_needed(self._week())
        await _respond(interaction, MSG_BTN_POSTED if posted else MSG_BTN_ALREADY_POSTED)

    @discord.ui.button(label=BTN_GOT_IT, style=discord.ButtonStyle.secondary, custom_id="pod-monday-got-it")
    async def got_it(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        _week_status[self._week().isoformat()] = STATUS_HANDLED
        await _respond(interaction, MSG_BTN_GOT_IT)

    @discord.ui.button(label=BTN_SKIP, style=discord.ButtonStyle.secondary, custom_id="pod-monday-skip")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        _week_status[self._week().isoformat()] = STATUS_SKIPPED
        await _respond(interaction, MSG_BTN_SKIPPED)


async def _respond(interaction: discord.Interaction, message: str) -> None:
    await interaction.response.send_message(message, ephemeral=(interaction.guild is not None))


async def _post_default_if_needed(monday: date | None = None) -> bool:
    channel = await _fetch_coordination_channel()
    if channel is None:
        return False
    if await _schedule_already_posted(channel):
        log.info("schedule already posted in the coordination channel; standing down")
        return False

    monday = monday or _upcoming_monday()
    body = compose_monday_message(monday, ACTIVE_SET_CODE)
    message = await channel.send(body)
    kind, _ = monday_kind(monday)
    if kind == MONDAY_KIND_RELEASE_WEEK:
        try:
            await message.add_reaction("👍")
        except discord.HTTPException:
            log.warning("could not add 👍 reaction to release-week post", exc_info=True)
    log.info(f"posted the default weekly schedule for {monday.isoformat()} ({kind})")
    return True


async def _schedule_already_posted(channel: discord.abc.Messageable) -> bool:
    since = datetime.combine(_upcoming_monday(), time(MONDAY_DM_HOUR_ET, 0), tzinfo=SCHEDULE_TZ)
    poster_ids = {_bot.owner_id, _bot.user.id if _bot.user else None}
    try:
        async for message in channel.history(after=since, limit=50):
            if message.author.id in poster_ids and "<t:" in message.content:
                return True
    except discord.HTTPException:
        log.warning("could not scan the coordination channel for an existing post", exc_info=True)
    return False


async def _create_command_blocks(monday) -> list[str]:
    event_count = await asyncio.to_thread(_count_set_events)
    blocks = []
    for i, slot in enumerate(slots_for_week(monday)):
        command = build_create_command(ACTIVE_SET_CODE, event_count + 1 + i, slot)
        blocks.append(f"```\n{command}\n```")
    return blocks


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
        log.warning("owner_id not set; skipping the monday schedule DM")
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


def _upcoming_monday() -> date:
    today = datetime.now(SCHEDULE_TZ).date()
    return today + timedelta(days=(7 - today.weekday()) % 7)
