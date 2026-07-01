"""Monday schedule DM, owner buttons, and the fallback post — two APScheduler cron jobs.

The owner posts the weekly schedule personally; the bot ghostwrites it. At MONDAY_DM_HOUR_ET the
owner gets one DM: the paste-ready message in a code block, the week's Sesh /create blocks, and
Post-it-for-me / I've-got-it / Skip buttons. At FALLBACK_POST_HOUR_ET a second cron posts the
default version unless the week was handled — guarded by a channel scan for an already-posted
schedule, so a manual post without a button press never double-posts.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import date, datetime, time, timedelta, timezone

import discord
from discord.ext import commands
from sqlalchemy import select

from bot.config import settings
from bot.database import SessionLocal
from bot.models import PodDraftEvent
from bot.services.pod_schedule import (
    BTN_EMOJI_GOT_IT,
    BTN_EMOJI_POST,
    BTN_EMOJI_SKIP,
    BTN_GOT_IT,
    BTN_POST,
    BTN_SKIP,
    CREATE_LEAD_HOURS,
    MONDAY_KIND_NORMAL,
    MONDAY_KIND_RELEASE_WEEK,
    MSG_BTN_ALREADY_POSTED,
    MSG_BTN_GOT_IT,
    MSG_BTN_POSTED,
    MSG_BTN_SKIPPED,
    MSG_CREATE_COMMAND_LEAD,
    MSG_MONDAY_DRAFT_INTRO,
    NA_CREATE_SEND_HOUR_ET,
    SCHEDULE_TZ,
    WEEKLY_SLOTS,
    build_create_command,
    compose_schedule_message,
    create_command_send_time,
    highest_event_number,
    monday_kind,
    monday_of,
    next_unscheduled_slots,
    slot_by_weekday,
    slot_instant,
    upcoming_slots,
)
from bot.sets import active_set_code


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
    arm_create_command_jobs(_current_week_monday())
    arm_create_command_jobs(upcoming_monday())
    log.info(
        f"weekly schedule flow armed: DM Mondays {MONDAY_DM_HOUR_ET}:00, "
        f"fallback {FALLBACK_POST_HOUR_ET}:00 {SCHEDULE_TZ.key}, "
        f"/create sends: NA Mondays {NA_CREATE_SEND_HOUR_ET}:00, EU/Sat T-{CREATE_LEAD_HOURS}h"
    )


async def fire_monday_dm() -> None:
    if _bot is None:
        log.error("fire_monday_dm: bot reference is not initialised")
        return
    owner = await _fetch_owner()
    if owner is None:
        return

    monday = upcoming_monday()
    reference = datetime.now(SCHEDULE_TZ)
    body, view, _ = await build_monday_package(reference, monday)
    try:
        await owner.send(body, view=view)
        log.info(f"monday schedule DM sent for {monday.isoformat()}")
    except discord.HTTPException:
        log.warning("could not DM the monday schedule draft to owner", exc_info=True)
    arm_create_command_jobs(monday)


async def build_monday_package(
    reference: datetime, week_monday: date
) -> tuple[str, "PodMondayView", list[str]]:
    """Render the draft the Monday DM and /pod-schedule share.

    `reference` drives the content — the next upcoming slots from that moment, so a mid-week /pod-schedule
    rolls into next week instead of assuming a Monday start. `week_monday` is the week the buttons act on
    (the next automated post, or the previewed week). The paste-ready message and its buttons come first;
    the Sesh /create blocks are returned separately as one copy-whole code block per event, empty on
    boundary weeks. The automated Monday DM no longer batches them — each fires on its own T-47h job — but
    /pod-schedule still previews the full set on demand.
    """
    message = compose_schedule_message(reference, active_set_code())
    body = f"{MSG_MONDAY_DRAFT_INTRO}\n```\n{message}\n```"
    create_blocks = await _create_command_blocks(reference)
    return body, PodMondayView(week_monday, reference), create_blocks


async def fire_fallback_post() -> None:
    if _bot is None:
        log.error("fire_fallback_post: bot reference is not initialised")
        return
    monday = upcoming_monday()
    status = _week_status.get(monday.isoformat())
    if status is not None:
        log.info(f"fallback post for {monday.isoformat()}: week already {status}; standing down")
        return
    await _post_default_if_needed()


class PodMondayView(discord.ui.View):
    """Persistent (timeout=None) so buttons survive restarts; the restored copy falls back to the current week."""

    def __init__(self, monday: date | None = None, reference: datetime | None = None) -> None:
        super().__init__(timeout=None)
        self._monday = monday
        self._reference = reference

    def _week(self) -> date:
        return self._monday or upcoming_monday()

    def _ref(self) -> datetime:
        return self._reference or datetime.now(SCHEDULE_TZ)

    @discord.ui.button(
        label=BTN_POST, emoji=BTN_EMOJI_POST, style=discord.ButtonStyle.primary, custom_id="pod-monday-post"
    )
    async def post_for_me(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        _week_status[self._week().isoformat()] = STATUS_HANDLED
        posted = await _post_default_if_needed(self._ref())
        await _respond(interaction, MSG_BTN_POSTED if posted else MSG_BTN_ALREADY_POSTED)

    @discord.ui.button(
        label=BTN_GOT_IT, emoji=BTN_EMOJI_GOT_IT, style=discord.ButtonStyle.success, custom_id="pod-monday-got-it"
    )
    async def got_it(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        _week_status[self._week().isoformat()] = STATUS_HANDLED
        await _respond(interaction, MSG_BTN_GOT_IT)

    @discord.ui.button(
        label=BTN_SKIP, emoji=BTN_EMOJI_SKIP, style=discord.ButtonStyle.secondary, custom_id="pod-monday-skip"
    )
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        _week_status[self._week().isoformat()] = STATUS_SKIPPED
        await _respond(interaction, MSG_BTN_SKIPPED)


async def _respond(interaction: discord.Interaction, message: str) -> None:
    await interaction.response.send_message(message, ephemeral=(interaction.guild is not None))


async def _post_default_if_needed(reference: datetime | None = None) -> bool:
    channel = await _fetch_coordination_channel()
    if channel is None:
        return False
    if await _schedule_already_posted(channel):
        log.info("schedule already posted in the coordination channel; standing down")
        return False

    reference = reference or datetime.now(SCHEDULE_TZ)
    body = compose_schedule_message(reference, active_set_code())
    message = await channel.send(body)
    await _pin_schedule(channel, message)
    schedule_monday = monday_of(upcoming_slots(reference, 1)[0])
    kind, _ = monday_kind(schedule_monday)
    if kind == MONDAY_KIND_RELEASE_WEEK:
        try:
            await message.add_reaction("👍")
        except discord.HTTPException:
            log.warning("could not add 👍 reaction to release-week post", exc_info=True)
    log.info(f"posted the default weekly schedule for {schedule_monday.isoformat()} ({kind})")
    return True


async def _pin_schedule(channel: discord.abc.Messageable, message: discord.Message) -> None:
    """Pin the freshly-posted weekly schedule, unpinning the bot/owner's prior schedule pins first."""
    poster_ids = {_bot.owner_id, _bot.user.id if _bot.user else None}
    try:
        pins = await channel.pins()
    except (discord.HTTPException, AttributeError):
        log.warning("could not read pins while pinning the weekly schedule", exc_info=True)
        pins = []
    for pinned in pins:
        if pinned.id == message.id or pinned.author.id not in poster_ids or "<t:" not in pinned.content:
            continue
        try:
            await pinned.unpin()
        except discord.HTTPException:
            log.warning(f"could not unpin previous schedule {pinned.id}", exc_info=True)
    try:
        await message.pin()
    except discord.HTTPException:
        log.warning("could not pin the weekly schedule post", exc_info=True)


async def _schedule_already_posted(channel: discord.abc.Messageable) -> bool:
    since = datetime.combine(upcoming_monday(), time(MONDAY_DM_HOUR_ET, 0), tzinfo=SCHEDULE_TZ)
    poster_ids = {_bot.owner_id, _bot.user.id if _bot.user else None}
    try:
        async for message in channel.history(after=since, limit=50):
            if message.author.id in poster_ids and "<t:" in message.content:
                return True
    except discord.HTTPException:
        log.warning("could not scan the coordination channel for an existing post", exc_info=True)
    return False


async def _create_command_blocks(reference: datetime) -> list[str]:
    last_number, scheduled = await asyncio.to_thread(_event_number_and_scheduled_starts)
    blocks = []
    for offset, start in enumerate(next_unscheduled_slots(reference, scheduled), start=1):
        slot = slot_by_weekday(start.weekday())
        command = build_create_command(
            active_set_code(), last_number + offset, start, slot.description, slot.mentions
        )
        blocks.append(f"```\n{command}\n```")
    return blocks


def arm_create_command_jobs(monday: date) -> None:
    """Schedule one DM per weekly slot at event_time − 47h carrying that slot's standalone /create command.

    No-op on boundary weeks (release/championship/season) and for slots whose lead time has passed;
    deterministic job ids keep a restart re-arm from double-firing.
    """
    scheduler = getattr(_bot, "pod_scheduler", None)
    if scheduler is None:
        return
    if monday_kind(monday)[0] != MONDAY_KIND_NORMAL:
        return
    now = datetime.now(timezone.utc)
    for slot in WEEKLY_SLOTS:
        run_at = create_command_send_time(slot, monday)
        job_id = f"pod-create-cmd-{monday.isoformat()}-{slot.weekday}"
        if run_at <= now:
            with contextlib.suppress(Exception):
                scheduler.remove_job(job_id)
            continue
        scheduler.add_job(
            fire_create_command,
            "date",
            run_date=run_at,
            args=[monday.isoformat(), slot.weekday],
            id=job_id,
            replace_existing=True,
        )
        log.info(f"armed /create DM for {monday.isoformat()} weekday={slot.weekday} at {run_at.isoformat()}")


async def fire_create_command(monday_iso: str, weekday: int) -> None:
    if _bot is None:
        log.error("fire_create_command: bot reference is not initialised")
        return
    monday = date.fromisoformat(monday_iso)
    if monday_kind(monday)[0] != MONDAY_KIND_NORMAL:
        return
    slot = None
    for candidate in WEEKLY_SLOTS:
        if candidate.weekday == weekday:
            slot = candidate
            break
    if slot is None:
        return
    owner = await _fetch_owner()
    if owner is None:
        return

    slot_start = datetime.combine(monday + timedelta(days=slot.weekday), slot.start, tzinfo=SCHEDULE_TZ)
    last_number = await asyncio.to_thread(_latest_event_number)
    command = build_create_command(
        active_set_code(), last_number + 1, slot_start, slot.description, slot.mentions
    )
    lead = MSG_CREATE_COMMAND_LEAD.format(emoji=slot.emoji, day=f"{slot_start:%A} {slot_start.day}")
    try:
        await owner.send(lead)
        await owner.send(f"```\n{command}\n```")
        log.info(f"sent /create DM for {monday_iso} weekday={weekday}")
    except discord.HTTPException:
        log.warning("could not DM the per-event /create command to owner", exc_info=True)


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


def _latest_event_number() -> int:
    with SessionLocal() as session:
        names = session.execute(
            select(PodDraftEvent.name).where(PodDraftEvent.set_code == active_set_code())
        ).scalars()
        return highest_event_number(names)


def _event_number_and_scheduled_starts() -> tuple[int, set[datetime]]:
    """Highest recorded event number and the instants that already have a pod, so the preview never
    re-offers a /create for a slot that is already scheduled."""
    with SessionLocal() as session:
        rows = session.execute(
            select(PodDraftEvent.name, PodDraftEvent.event_time).where(
                PodDraftEvent.set_code == active_set_code()
            )
        ).all()
    highest = highest_event_number(name for name, _ in rows)
    scheduled = {slot_instant(event_time) for _, event_time in rows if event_time is not None}
    return highest, scheduled


def upcoming_monday() -> date:
    today = datetime.now(SCHEDULE_TZ).date()
    return today + timedelta(days=(7 - today.weekday()) % 7)


def _current_week_monday() -> date:
    today = datetime.now(SCHEDULE_TZ).date()
    return today - timedelta(days=today.weekday())
