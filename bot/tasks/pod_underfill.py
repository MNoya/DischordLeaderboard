"""T-24h / T-3h underfill checks fired by APScheduler date jobs.

Re-fetches the sesh embed's Yes list at fire time; events at or above the target stay silent,
short events get a role-ping reminder in the coordination channel with a jump link to the RSVP
message. Jobs are armed alongside the T-10min reminder (sesh_listener) and skipped — never
back-fired — when the check window has already passed.
"""
from __future__ import annotations

import contextlib
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from bot.config import settings
from bot.database import SessionLocal
from bot.models import PodDraftEvent
from bot.tasks.pod_draft_reminder import fetch_sesh_rsvps


UNDERFILL_CHECK_HOURS = (24, 3)

log = logging.getLogger(__name__)

_bot: commands.Bot | None = None


def init_underfill(bot: commands.Bot) -> None:
    """Wire the bot reference so the APScheduler callbacks can dispatch Discord work."""
    global _bot
    _bot = bot


def schedule_underfill_checks(scheduler, event_id: str, event_time: datetime) -> None:
    now = datetime.now(timezone.utc)
    for hours in UNDERFILL_CHECK_HOURS:
        run_at = event_time - timedelta(hours=hours)
        job_id = f"pod-underfill{hours}-{event_id}"
        if run_at <= now:
            with contextlib.suppress(Exception):
                scheduler.remove_job(job_id)
            continue
        scheduler.add_job(
            fire_underfill,
            "date",
            run_date=run_at,
            args=[event_id, hours],
            id=job_id,
            replace_existing=True,
        )
        log.info(f"scheduled T-{hours}h underfill check for event {event_id} at {run_at.isoformat()}")


async def fire_underfill(event_id: str, hours_before: int) -> None:
    if _bot is None:
        log.error(f"fire_underfill for {event_id}: bot reference is not initialised")
        return

    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is None:
            log.warning(f"fire_underfill: pod_draft_event {event_id} not found")
            return
        if event.socket_status != "pending":
            log.info(f"fire_underfill: event {event_id} is {event.socket_status}; skipping")
            return
        sesh_message_id = event.sesh_message_id
        event_time = event.event_time

    if event_time <= datetime.now(timezone.utc):
        log.info(f"fire_underfill: event {event_id} already started; skipping")
        return

    rsvps = await fetch_sesh_rsvps(_bot, sesh_message_id)
    if rsvps is None:
        log.info(f"fire_underfill: sesh message {sesh_message_id} gone for event {event_id}; skipping")
        return
    yes_attendees, _ = rsvps

    target = settings.pod_draft_target_players
    if len(yes_attendees) >= target:
        log.info(f"T-{hours_before}h check for {event_id}: {len(yes_attendees)}/{target} Yes; staying silent")
        return

    channel = _bot.get_channel(settings.pod_draft_channel_id)
    if channel is None:
        log.warning(f"fire_underfill: coordination channel {settings.pod_draft_channel_id} unavailable")
        return

    jump_url = _sesh_jump_url(sesh_message_id)
    body = build_underfill_message(settings.pod_drafters_role_id, len(yes_attendees), target, event_time, jump_url)
    try:
        await channel.send(body, allowed_mentions=discord.AllowedMentions(roles=True))
        log.info(f"T-{hours_before}h underfill reminder posted for {event_id}: {len(yes_attendees)}/{target} Yes")
    except discord.HTTPException:
        log.warning(f"fire_underfill: could not post reminder for {event_id}", exc_info=True)


def build_underfill_message(
    role_id: int | None,
    yes_count: int,
    target: int,
    event_time: datetime,
    jump_url: str,
) -> str:
    needed = target - yes_count
    plural = "s" if needed != 1 else ""
    unix = int(event_time.timestamp())
    role_mention = f"<@&{role_id}> " if role_id else ""
    return (
        f"{role_mention}{needed} more player{plural} needed for the pod draft on <t:{unix}:F> (<t:{unix}:R>) — "
        f"{yes_count}/{target} in so far. RSVP: {jump_url}"
    )


def _sesh_jump_url(sesh_message_id: str) -> str:
    return (
        f"https://discord.com/channels/{settings.discord_guild_id}"
        f"/{settings.pod_draft_channel_id}/{sesh_message_id}"
    )
