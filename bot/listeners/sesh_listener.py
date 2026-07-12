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
from bot.services.pod_registration_embed import RegisteredSettingsView, build_registered_embed
from bot.services.pod_draft_manager import cancel_pod_event, notify_seeding_change
from bot.services.pod_drafts import (
    FINALIZED_STATUSES,
    ParsedSeshEvent,
    event_for_sesh_message_sync,
    is_championship,
    record_event,
    update_event_time_if_changed,
)
from bot.services.ping_roles import auto_grant_spec_for_event, build_grant_embed
from bot.services.pod_roles import find_role, grant_role, resolve_member
from bot.services.sesh_parser import ParsedSeshFields, parse_sesh_embed
from bot.sets import active_set_code
from bot.tasks.pod_draft_reminder import (
    REMINDER_LEAD_MIN,
    fire_reminder,
    refresh_roster_reminder,
    schedule_roster_reminder,
    schedule_team_vote_offer,
)
from bot.tasks.pod_underfill import refresh_underfill_nudge, schedule_underfill_checks


log = logging.getLogger(__name__)

THREAD_POLL_INTERVAL_S = 5
THREAD_POLL_TIMEOUT_S = 120



class SeshListener(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._announced_grants: set[tuple[int, int]] = set()

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

        try:
            await refresh_underfill_nudge(self.bot, str(message.id), len(fields.attendees))
        except Exception:
            log.exception(f"underfill nudge refresh failed for message {message.id}")

        try:
            await refresh_roster_reminder(self.bot, str(message.id))
        except Exception:
            log.exception(f"roster reminder refresh failed for message {message.id}")

        try:
            thread = await self._resolve_thread(message.guild, str(message.id))
            await self._grant_subscription_roles(message.guild, thread, fields.event_time, fields.attendees)
        except Exception:
            log.exception(f"subscription role auto-grant failed for message {message.id}")

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Sesh deletes its RSVP message when an event is cancelled — tear down the matching pod draft.
        Finalized pods are kept: deleting an old sesh message must never wipe played-pod history."""
        if payload.channel_id != settings.pod_draft_channel_id:
            return
        found = await asyncio.to_thread(event_for_sesh_message_sync, str(payload.message_id))
        if found is None:
            return
        event_id, socket_status = found
        if socket_status in FINALIZED_STATUSES:
            log.info(
                f"sesh message {payload.message_id} deleted but pod {event_id} is {socket_status}; "
                "keeping finalized event"
            )
            return
        log.warning(f"sesh message {payload.message_id} deleted; cancelling pod draft {event_id}")
        try:
            await cancel_pod_event(event_id, actor="sesh cancellation")
        except Exception:
            log.exception(f"sesh-cancel teardown failed for event {event_id}")

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
            log.warning(
                f"sesh embed {message.id} never spawned a thread within {THREAD_POLL_TIMEOUT_S}s; "
                "skipping registration"
            )
            return

        parsed_event = ParsedSeshEvent(
            event_date=fields.event_date,
            event_time=fields.event_time,
            set_code=fields.set_code or active_set_code(),
            event_number=fields.event_number,
            name=fields.name,
            attendees=fields.attendees,
            sesh_message_id=str(message.id),
            discord_thread_id=str(thread.id),
        )
        event_row = await asyncio.to_thread(_persist_event, parsed_event)

        try:
            await thread.join()
        except discord.HTTPException:
            log.warning(f"could not join thread {thread.id}", exc_info=True)

        self._schedule_reminder(event_row.id, event_row.event_time)
        self._schedule_underfill(event_row.id, event_row.event_time, event_row.created_at)
        await self._grant_subscription_roles(message.guild, thread, event_row.event_time, fields.attendees)

        championship = is_championship(event_row.name)
        try:
            await thread.send(
                embed=build_registered_embed(
                    event_row.set_code, event_row.pairing_mode, event_row.seating_mode,
                    championship=championship,
                ),
                view=RegisteredSettingsView(),
            )
        except discord.HTTPException:
            log.warning(f"could not post confirmation in pod draft thread {thread.id}", exc_info=True)

        if championship:
            notify_seeding_change(self.bot, event_row.id)

    async def _handle_pod_draft_edit(self, message: discord.Message, fields: ParsedSeshFields) -> None:
        result = await asyncio.to_thread(
            _apply_event_time_update, str(message.id), fields.event_time, fields.event_date
        )
        if result is None:
            return
        event, needs_reschedule, was_active = result
        notify_seeding_change(self.bot, event.id)
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
        self._schedule_underfill(event.id, event.event_time, event.created_at)

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
        schedule_roster_reminder(scheduler, event_id, event_time)
        schedule_team_vote_offer(scheduler, event_id, event_time)

    def _schedule_underfill(self, event_id: str, event_time: datetime, created_at: datetime) -> None:
        scheduler = getattr(self.bot, "pod_scheduler", None)
        if scheduler is None:
            return
        schedule_underfill_checks(scheduler, event_id, event_time, created_at)

    async def _grant_subscription_roles(
        self, guild: discord.Guild | None, thread: discord.Thread | None, event_time: datetime, attendees,
    ) -> None:
        """Sticky-grant a slot's subscription role to everyone RSVP'd Yes to a time-specific pod.

        Sesh hands the full attendee list on every RSVP edit with no delta, so the loop re-runs over
        everyone and relies on `grant_role` to no-op those already subscribed. The announcement is
        deduped per (thread, member) rather than on `grant_role` alone: back-to-back edits can both
        re-add before the member-role cache reflects the first add, which would double-announce.
        """
        spec = auto_grant_spec_for_event(event_time)
        if guild is None or spec is None:
            return
        role = find_role(guild, spec.name)
        if role is None:
            log.info(f"{spec.name!r} role missing in {guild.name}; skipping auto-grant")
            return
        for token in attendees:
            member = await resolve_member(guild, token)
            if member is None:
                continue
            granted = await grant_role(member, role)
            if not granted or thread is None:
                continue
            key = (thread.id, member.id)
            if key in self._announced_grants:
                continue
            self._announced_grants.add(key)
            await self._announce_grant(thread, member, role, spec.emoji)

    async def _announce_grant(
        self, thread: discord.Thread, member: discord.Member, role: discord.Role, emoji: str,
    ) -> None:
        try:
            await thread.send(
                embed=build_grant_embed(member.mention, role, emoji),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            log.warning(f"could not announce role grant in thread {thread.id}", exc_info=True)


async def _fire_after_delay(event_id: str, delay_s: float) -> None:
    await asyncio.sleep(delay_s)
    await fire_reminder(event_id)


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
            schedule_underfill_checks(scheduler, event.id, event.event_time, event.created_at)
            schedule_roster_reminder(scheduler, event.id, event.event_time)
            schedule_team_vote_offer(scheduler, event.id, event.event_time)
            rearmed += 1
    if rearmed:
        log.info(f"startup sweep re-armed {rearmed} pending pod-draft reminder(s)")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SeshListener(bot))
