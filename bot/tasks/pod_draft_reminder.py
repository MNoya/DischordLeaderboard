"""T-5 minute pod-draft reminder fired by APScheduler.

Re-fetches the sesh embed for the latest attendee list, resolves Discord member mentions on a
best-effort basis, and posts the Draftmancer link in the event thread
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from bot import emojis
from bot.config import settings
from bot.database import SessionLocal
from bot.models import PodDraftEvent
from bot.services.pod_draft_manager import start_manager
from bot.services.sesh_parser import parse_sesh_embed


REMINDER_LEAD_MIN = 5


log = logging.getLogger(__name__)

_bot: commands.Bot | None = None


def init_reminder(bot: commands.Bot) -> None:
    """Wire the bot reference so the APScheduler callback can dispatch Discord work."""
    global _bot
    _bot = bot


async def fire_reminder(event_id: str) -> None:
    """T-5 callback. Re-fetches sesh attendees, pings them with the Draftmancer link."""
    if _bot is None:
        log.error("fire_reminder for %s: bot reference is not initialised", event_id)
        return

    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is None:
            log.warning("fire_reminder: pod_draft_event %s not found", event_id)
            return
        thread_id = int(event.discord_thread_id)
        sesh_message_id = int(event.sesh_message_id)
        draftmancer_url = event.draftmancer_url
        draftmancer_session = event.draftmancer_session
        set_code = event.set_code
        event_name = event.name

    thread = await _fetch_thread(thread_id)
    if thread is None:
        log.warning("fire_reminder: could not fetch thread %s", thread_id)
        return

    attendees, maybe_attendees = await _refetch_attendees(sesh_message_id)
    mention_block = await _resolve_mentions(thread.guild, attendees) if attendees else ""
    expected_attendee_count = len(attendees)

    body = (
        f"{emojis.get('draftmancer')} Pod Draft starts in {REMINDER_LEAD_MIN} minutes!\n"
        + f"**Join the Draftmancer session:** {draftmancer_url}\n"
        + "Set your user name to your Arena handle (e.g. `ArenaID#1234`) so pairings work smoothly."
        + (f"\n\n{mention_block}" if mention_block else "")
    )
    log.info("fire_reminder body repr for %s: %r", event_id, body)
    try:
        await thread.send(body, allowed_mentions=discord.AllowedMentions(users=True))
    except discord.HTTPException:
        log.warning("fire_reminder: could not post in thread %s", thread_id, exc_info=True)
        return

    # Transition out of 'pending' so the startup sweep doesn't re-fire on a restart
    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is not None and event.socket_status == "pending":
            event.socket_status = "reminded"
            session.commit()

    await start_manager(
        _bot, event_id, draftmancer_session, thread_id, set_code, expected_attendee_count,
        event_name=event_name,
        draftmancer_url=draftmancer_url,
        rsvps_yes=list(attendees),
        rsvps_maybe=list(maybe_attendees),
    )


async def _fetch_thread(thread_id: int) -> discord.Thread | None:
    try:
        channel = await _bot.fetch_channel(thread_id)
    except discord.HTTPException as e:
        log.warning("fetch_channel(%s) failed: %s", thread_id, e)
        return None
    return channel if isinstance(channel, discord.Thread) else None


async def _refetch_attendees(sesh_message_id: int) -> tuple[list[str], list[str]]:
    """Re-fetch the sesh embed for the latest Yes / Maybe RSVPs. Returns (yes, maybe)."""
    try:
        channel = await _bot.fetch_channel(settings.pod_draft_channel_id)
        message = await channel.fetch_message(sesh_message_id)
    except discord.HTTPException as e:
        log.warning("could not re-fetch sesh message %s: %s", sesh_message_id, e)
        return [], []
    for embed in message.embeds:
        parsed = parse_sesh_embed(embed)
        if parsed is not None:
            return list(parsed.attendees), list(parsed.maybe_attendees)
    return [], []


async def _resolve_mentions(guild: discord.Guild | None, attendees: list[str]) -> str:
    """Map sesh display names to guild member mentions (best-effort, case-insensitive)."""
    if guild is None:
        return " ".join(attendees)
    by_name: dict[str, discord.Member] = {}
    for member in guild.members:
        by_name.setdefault(member.display_name.lower(), member)
        by_name.setdefault(member.name.lower(), member)
    pieces: list[str] = []
    for name in attendees:
        member = by_name.get(name.lower())
        pieces.append(member.mention if member else name)
    return " ".join(pieces)
