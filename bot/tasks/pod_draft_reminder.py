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


REMINDER_LEAD_MIN = 10


log = logging.getLogger(__name__)

_bot: commands.Bot | None = None


def init_reminder(bot: commands.Bot) -> None:
    """Wire the bot reference so the APScheduler callback can dispatch Discord work."""
    global _bot
    _bot = bot


async def fire_reminder(event_id: str, *, early: bool = False) -> None:
    """T-5 callback. Re-fetches sesh attendees, pings them with the Draftmancer link.

    `early=True` is the owner-triggered "open the lobby now" path: swaps the body copy and
    cancels the still-pending APScheduler job so we don't double-post at T-5.
    """
    if _bot is None:
        log.error(f"fire_reminder for {event_id}: bot reference is not initialised")
        return

    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is None:
            log.warning(f"fire_reminder: pod_draft_event {event_id} not found")
            return
        thread_id = int(event.discord_thread_id)
        sesh_message_id = int(event.sesh_message_id)
        draftmancer_url = event.draftmancer_url
        draftmancer_session = event.draftmancer_session
        set_code = event.set_code
        event_name = event.name

    thread = await _fetch_thread(thread_id)
    if thread is None:
        log.warning(f"fire_reminder: could not fetch thread {thread_id}")
        return

    attendees, maybe_attendees = await _refetch_attendees(sesh_message_id)
    mention_block = await _resolve_mentions(thread.guild, attendees) if attendees else ""
    expected_attendee_count = len(attendees)

    headline = (
        "Lobby opening now!"
        if early
        else f"Pod Draft starts in {REMINDER_LEAD_MIN} minutes!"
    )
    body = (
        f"{emojis.get('draftmancer')} {headline}\n"
        f"**Join the Draftmancer session:** {draftmancer_url}\n"
        "Set your Arena Name (e.g., `ArenaID#12345`) as your name in Draftmancer so pairings work smoothly."
        + (f"\n\n{mention_block}" if mention_block else "")
    )
    log.info(f"fire_reminder body repr for {event_id} (early={early}): {body!r}")
    try:
        await thread.send(body, allowed_mentions=discord.AllowedMentions(users=True))
    except discord.HTTPException:
        log.warning(f"fire_reminder: could not post in thread {thread_id}", exc_info=True)
        return

    # Transition out of 'pending' so the startup sweep doesn't re-fire on a restart
    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is not None and event.socket_status == "pending":
            event.socket_status = "reminded"
            session.commit()

    if early:
        scheduler = getattr(_bot, "pod_scheduler", None)
        if scheduler is not None:
            try:
                scheduler.remove_job(f"pod-reminder-{event_id}")
                log.info(f"early-open cancelled pending reminder job for {event_id}")
            except Exception:
                log.info(f"no pending reminder job to cancel for {event_id}", exc_info=True)

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
        log.warning(f"fetch_channel({thread_id}) failed: {e}")
        return None
    return channel if isinstance(channel, discord.Thread) else None


async def fetch_sesh_message(bot: commands.Bot, sesh_message_id: int | str) -> discord.Message | None:
    """Fetch the parent sesh RSVP message from the pod-draft coordination channel — the message
    that carries both the ✅/🤷 reactions and the attendee embed. The thread's starter copy does
    not hold the reactions, so always read from this channel."""
    try:
        channel = await bot.fetch_channel(settings.pod_draft_channel_id)
        return await channel.fetch_message(int(sesh_message_id))
    except (discord.HTTPException, ValueError) as e:
        log.warning(f"could not fetch sesh message {sesh_message_id}: {e}")
        return None


async def _refetch_attendees(sesh_message_id: int) -> tuple[list[str], list[str]]:
    """Re-fetch the sesh embed for the latest Yes / Maybe RSVPs. Returns (yes, maybe)."""
    message = await fetch_sesh_message(_bot, sesh_message_id)
    if message is None:
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
