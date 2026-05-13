"""Detect sesh.fyi RSVP embeds in #pod-draft-coordination → persist event + schedule T-5 reminder.

Pipeline: on_message (SESH_BOT_ID + POD_DRAFT_CHANNEL_ID filter) → parse_sesh_embed → poll for sesh's
thread (5s × 2min) → record_event → APScheduler date job → quiet confirmation in the thread.
reschedule_pending_events() re-arms reminders on startup so the in-memory scheduler survives restarts.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands
from sqlalchemy import select

from bot.config import settings
from bot.models import PodDraftEvent
from bot.services.pod_drafts import ParsedSeshEvent, record_event
from bot.services.sesh_parser import ParsedSeshFields, parse_sesh_embed
from bot.sets import ACTIVE_SET_CODE
from bot.tasks.pod_draft_reminder import fire_reminder


log = logging.getLogger(__name__)

THREAD_POLL_INTERVAL_S = 5
THREAD_POLL_TIMEOUT_S = 120
REMINDER_LEAD_MIN = 5


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
                log.exception("pod draft detection failed for message %s", message.id)
            return

    def _is_target_message(self, message: discord.Message) -> bool:
        if settings.sesh_bot_id is None or settings.pod_draft_channel_id is None:
            return False
        if message.author.id != settings.sesh_bot_id:
            return False
        if message.channel.id != settings.pod_draft_channel_id:
            return False
        return bool(message.embeds)

    async def _handle_pod_draft(self, message: discord.Message, fields: ParsedSeshFields) -> None:
        log.info("sesh pod-draft embed detected: %s", fields.name)
        thread = await self._wait_for_thread(message)
        if thread is None:
            log.warning("sesh embed %s never spawned a thread within %ss; skipping registration",
                        message.id, THREAD_POLL_TIMEOUT_S)
            return

        parsed_event = ParsedSeshEvent(
            event_number=fields.event_number,
            event_date=fields.event_date,
            event_time=fields.event_time,
            set_code=fields.set_code or ACTIVE_SET_CODE,
            format_label=fields.format_label,
            name=fields.name,
            attendees=fields.attendees,
            sesh_message_id=str(message.id),
            discord_thread_id=str(thread.id),
        )
        event_row = await asyncio.to_thread(_persist_event, parsed_event)

        try:
            await thread.join()
        except discord.HTTPException:
            log.warning("could not join thread %s", thread.id, exc_info=True)

        self._schedule_reminder(event_row.id, event_row.event_time)

        try:
            await thread.send(
                f"🤖 Pod Draft #{event_row.event_number} registered. "
                f"Draftmancer link goes up {REMINDER_LEAD_MIN} minutes before the event starts."
            )
        except discord.HTTPException:
            log.warning("could not post confirmation in pod draft thread %s", thread.id, exc_info=True)

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
                log.warning("fetch_channel(%s) failed: %s", message.id, e)
                ch = None
            if isinstance(ch, discord.Thread):
                return ch
            if loop.time() >= deadline:
                return None
            await asyncio.sleep(THREAD_POLL_INTERVAL_S)

    def _schedule_reminder(self, event_id: str, event_time: datetime) -> None:
        scheduler = getattr(self.bot, "pod_scheduler", None)
        if scheduler is None:
            log.error("pod_scheduler not attached to bot; reminder for %s lost", event_id)
            return
        run_at = event_time - timedelta(minutes=REMINDER_LEAD_MIN)
        now = datetime.now(timezone.utc)
        if run_at < now:
            log.warning("reminder for %s is in the past (run_at=%s now=%s); firing in 2s",
                        event_id, run_at, now)
            run_at = now + timedelta(seconds=2)
        scheduler.add_job(
            fire_reminder,
            "date",
            run_date=run_at,
            args=[event_id],
            id=f"pod-reminder-{event_id}",
            replace_existing=True,
        )
        log.info("scheduled pod-draft reminder for event %s at %s", event_id, run_at.isoformat())


def _persist_event(parsed_event: ParsedSeshEvent) -> PodDraftEvent:
    """record_event in a worker thread — sync SQLAlchemy off the gateway loop."""
    from bot.database import SessionLocal
    with SessionLocal() as session:
        event = record_event(session, parsed_event)
        session.commit()
        session.refresh(event)
        session.expunge(event)
        return event


def reschedule_pending_events(bot: commands.Bot) -> None:
    """Startup sweep: re-arm T-5 reminders for pending events so a restart doesn't lose work."""
    scheduler = getattr(bot, "pod_scheduler", None)
    if scheduler is None:
        return

    from bot.database import SessionLocal
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
        log.info("startup sweep re-armed %d pending pod-draft reminder(s)", rearmed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SeshListener(bot))
