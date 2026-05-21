"""Detect sesh.fyi RSVP embeds in #pod-draft-coordination → persist event + schedule T-5 reminder.

Pipeline: on_message (SESH_BOT_ID + POD_DRAFT_CHANNEL_ID filter) → parse_sesh_embed → poll for sesh's
thread (5s × 2min) → record_event → APScheduler date job → quiet confirmation in the thread.
on_raw_message_edit re-parses the embed and re-arms the reminder when sesh edits the event time.
reschedule_pending_events() re-arms reminders on startup so the in-memory scheduler survives restarts.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

import discord
from discord.ext import commands
from sqlalchemy import select

from bot.config import settings
from bot.database import SessionLocal
from bot.models import PodDraftEvent
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_drafts import ParsedSeshEvent, record_event, update_event_time_if_changed
from bot.services.sesh_parser import ParsedSeshFields, parse_sesh_embed
from bot.sets import ACTIVE_SET_CODE
from bot.tasks.pod_draft_reminder import REMINDER_LEAD_MIN, fire_reminder


log = logging.getLogger(__name__)

THREAD_POLL_INTERVAL_S = 5
THREAD_POLL_TIMEOUT_S = 120

SCHEDULED_EVENT_MATCH_WINDOW_S = 120


class SeshListener(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not self._is_target_message(message):
            return
        for embed in message.embeds:
            fields = parse_sesh_embed(embed)
            if fields is None:
                continue
            try:
                await self._handle_pod_draft(message, fields)
            except Exception:
                log.exception(f"pod draft detection failed for message {message.id}")
            return

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent) -> None:
        if payload.channel_id != settings.pod_draft_channel_id:
            return
        author = (payload.data or {}).get("author") or {}
        try:
            author_id = int(author.get("id") or 0)
        except (TypeError, ValueError):
            return
        if author_id != settings.sesh_bot_id:
            return

        message = await self._fetch_edited_message(payload.channel_id, payload.message_id)
        if message is None:
            return

        fields = None
        for embed in message.embeds:
            fields = parse_sesh_embed(embed)
            if fields is not None:
                break
        if fields is None:
            return

        try:
            await self._handle_pod_draft_edit(message, fields)
        except Exception:
            log.exception(f"pod draft edit handling failed for message {message.id}")

    def _is_target_message(self, message: discord.Message) -> bool:
        if message.author.id != settings.sesh_bot_id:
            return False
        if message.channel.id != settings.pod_draft_channel_id:
            return False
        return bool(message.embeds)

    async def _fetch_edited_message(self, channel_id: int, message_id: int) -> discord.Message | None:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.HTTPException as e:
                log.warning(f"fetch_channel({channel_id}) failed: {e}")
                return None
        try:
            return await channel.fetch_message(message_id)
        except discord.HTTPException as e:
            log.warning(f"fetch_message({message_id}) failed: {e}")
            return None

    async def _handle_pod_draft(self, message: discord.Message, fields: ParsedSeshFields) -> None:
        log.info(f"sesh pod-draft embed detected: {fields.name}")
        thread = await self._wait_for_thread(message)
        if thread is None:
            log.warning(f"sesh embed {message.id} never spawned a thread within {THREAD_POLL_TIMEOUT_S}s; skipping registration")
            return

        discord_event_id = await _resolve_discord_event_id(message.guild, fields.event_time)

        parsed_event = ParsedSeshEvent(
            event_date=fields.event_date,
            event_time=fields.event_time,
            set_code=fields.set_code or ACTIVE_SET_CODE,
            event_number=fields.event_number,
            format_label=fields.format_label,
            name=fields.name,
            attendees=fields.attendees,
            sesh_message_id=str(message.id),
            discord_thread_id=str(thread.id),
            discord_event_id=discord_event_id,
        )
        event_row = await asyncio.to_thread(_persist_event, parsed_event)

        try:
            await thread.join()
        except discord.HTTPException:
            log.warning(f"could not join thread {thread.id}", exc_info=True)

        self._schedule_reminder(event_row.id, event_row.event_time)

        try:
            await thread.send(embed=discord.Embed(
                title="🤖 Pod Draft registered!",
                description=f"Draftmancer link will be posted {REMINDER_LEAD_MIN} minutes before the event starts.",
                color=discord.Color.green(),
            ))
        except discord.HTTPException:
            log.warning(f"could not post confirmation in pod draft thread {thread.id}", exc_info=True)

    async def _handle_pod_draft_edit(self, message: discord.Message, fields: ParsedSeshFields) -> None:
        result = await asyncio.to_thread(
            _apply_event_time_update, str(message.id), fields.event_time, fields.event_date
        )
        if result is None:
            return
        event, needs_reschedule, was_active = result
        if not needs_reschedule:
            return

        if was_active:
            manager = ACTIVE_POD_MANAGERS.get(event.id)
            if manager is not None:
                log.info(f"reschedule: tearing down live manager for {event.id} before re-arming reminder")
                await manager.disconnect_safely()

        log.info(
            f"sesh embed {message.id} rescheduled pod-draft {event.id} to {event.event_time.isoformat()}"
        )
        self._schedule_reminder(event.id, event.event_time)

        thread = await self._resolve_thread(message.guild, event.discord_thread_id)
        if thread is None:
            return
        try:
            unix = int(event.event_time.timestamp())
            await thread.send(embed=discord.Embed(
                title="🕐 Pod Draft rescheduled",
                description=(
                    f"New time: <t:{unix}:F> (<t:{unix}:R>).\n"
                    f"Draftmancer link will be posted {REMINDER_LEAD_MIN} minutes before the event starts."
                ),
                color=discord.Color.blue(),
            ))
        except discord.HTTPException:
            log.warning(f"could not post reschedule notice in thread {thread.id}", exc_info=True)

    async def _resolve_thread(
        self, guild: discord.Guild | None, thread_id: str | None,
    ) -> discord.Thread | None:
        if guild is None or thread_id is None:
            return None
        try:
            tid = int(thread_id)
        except (TypeError, ValueError):
            return None
        thread = guild.get_thread(tid)
        if thread is not None:
            return thread
        try:
            ch = await self.bot.fetch_channel(tid)
        except discord.HTTPException:
            return None
        return ch if isinstance(ch, discord.Thread) else None

    async def _wait_for_thread(self, message: discord.Message) -> discord.Thread | None:
        """Poll for the sesh-created thread (Discord assigns thread_id = message_id); None on timeout."""
        loop = asyncio.get_event_loop()
        deadline = loop.time() + THREAD_POLL_TIMEOUT_S
        while True:
            if message.thread is not None:
                return message.thread
            try:
                ch = await self.bot.fetch_channel(message.id)
            except discord.NotFound:
                ch = None
            except discord.HTTPException as e:
                log.warning(f"fetch_channel({message.id}) failed: {e}")
                ch = None
            if isinstance(ch, discord.Thread):
                return ch
            if loop.time() >= deadline:
                return None
            await asyncio.sleep(THREAD_POLL_INTERVAL_S)

    def _schedule_reminder(self, event_id: str, event_time: datetime) -> None:
        if settings.pod_draft_skip_reminder_wait:
            log.info(f"POD_DRAFT_SKIP_REMINDER_WAIT=true; firing reminder for {event_id} in 10s")
            asyncio.create_task(_fire_after_delay(event_id, 10))
            return
        scheduler = getattr(self.bot, "pod_scheduler", None)
        if scheduler is None:
            log.error(f"pod_scheduler not attached to bot; reminder for {event_id} lost")
            return
        run_at = event_time - timedelta(minutes=REMINDER_LEAD_MIN)
        now = datetime.now(timezone.utc)
        if run_at < now:
            log.warning(f"reminder for {event_id} is in the past (run_at={run_at} now={now}); firing in 2s")
            run_at = now + timedelta(seconds=2)
        scheduler.add_job(
            fire_reminder,
            "date",
            run_date=run_at,
            args=[event_id],
            id=f"pod-reminder-{event_id}",
            replace_existing=True,
        )
        log.info(f"scheduled pod-draft reminder for event {event_id} at {run_at.isoformat()}")


async def _fire_after_delay(event_id: str, delay_s: float) -> None:
    await asyncio.sleep(delay_s)
    await fire_reminder(event_id)


async def _resolve_discord_event_id(
    guild: discord.Guild | None,
    event_time: datetime,
) -> str | None:
    """Match a guild scheduled event whose start_time is within 2 minutes of the sesh event time."""
    if guild is None:
        return None
    try:
        scheduled = await guild.fetch_scheduled_events()
    except discord.HTTPException as e:
        log.warning(f"fetch_scheduled_events failed for guild {guild.id}: {e}")
        return None
    best: tuple[float, discord.ScheduledEvent] | None = None
    for ev in scheduled:
        if ev.start_time is None:
            continue
        delta = abs((ev.start_time - event_time).total_seconds())
        if delta > SCHEDULED_EVENT_MATCH_WINDOW_S:
            continue
        if best is None or delta < best[0]:
            best = (delta, ev)
    if best is None:
        log.info(f"no scheduled event within {SCHEDULED_EVENT_MATCH_WINDOW_S}s of {event_time.isoformat()}")
        return None
    log.info(f"matched scheduled event {best[1].id} (Δ={best[0]:.0f}s) for pod-draft at {event_time.isoformat()}")
    return str(best[1].id)


def _persist_event(parsed_event: ParsedSeshEvent) -> PodDraftEvent:
    """record_event in a worker thread — sync SQLAlchemy off the gateway loop."""
    with SessionLocal() as session:
        event = record_event(session, parsed_event)
        session.commit()
        session.refresh(event)
        session.expunge(event)
        return event


def _apply_event_time_update(
    sesh_message_id: str,
    new_event_time: datetime,
    new_event_date: date,
) -> tuple[PodDraftEvent, bool, bool] | None:
    """Worker-thread wrapper around update_event_time_if_changed; returns a detached row."""
    with SessionLocal() as session:
        result = update_event_time_if_changed(
            session, sesh_message_id, new_event_time, new_event_date,
        )
        if result is None:
            return None
        event, needs_reschedule, was_active = result
        if needs_reschedule:
            session.commit()
            session.refresh(event)
        session.expunge(event)
        return event, needs_reschedule, was_active


def reschedule_pending_events(bot: commands.Bot) -> None:
    """Startup sweep: re-arm T-5 reminders for pending events so a restart doesn't lose work."""
    scheduler = getattr(bot, "pod_scheduler", None)
    if scheduler is None:
        return

    now = datetime.now(timezone.utc)
    rearmed = 0
    with SessionLocal() as session:
        pending = session.execute(
            select(PodDraftEvent).where(PodDraftEvent.socket_status == "pending")
        ).scalars().all()
        for event in pending:
            run_at = event.event_time - timedelta(minutes=REMINDER_LEAD_MIN)
            if event.event_time < now - timedelta(minutes=30):
                continue
            if run_at < now:
                run_at = now + timedelta(seconds=2)
            scheduler.add_job(
                fire_reminder,
                "date",
                run_date=run_at,
                args=[event.id],
                id=f"pod-reminder-{event.id}",
                replace_existing=True,
            )
            rearmed += 1
    if rearmed:
        log.info(f"startup sweep re-armed {rearmed} pending pod-draft reminder(s)")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SeshListener(bot))
