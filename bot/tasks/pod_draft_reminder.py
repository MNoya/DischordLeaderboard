"""T-5 minute pod-draft reminder fired by APScheduler.

Re-fetches the sesh embed for the latest attendee list, resolves Discord member mentions on a
best-effort basis, and posts the Draftmancer link in the event thread
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands
from sqlalchemy import select

from bot import emojis
from bot.config import settings
from bot.database import SessionLocal
from bot.models import PodDraftEvent
from bot.services.pod_draft_manager import start_manager
from bot.services.pod_drafts import draftmancer_url_for
from bot.services.sesh_parser import parse_sesh_embed


REMINDER_LEAD_MIN = 10
ROSTER_REMINDER_LEAD_MIN = 60
ROSTER_EMBED_TITLE = "🔔 Pod Draft starting soon"
ROSTER_SEARCH_LIMIT = 50


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
        draftmancer_session = event.draftmancer_session
        draftmancer_url = draftmancer_url_for(draftmancer_session)
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
        f"**Join the Draftmancer session:** <{draftmancer_url}>\n"
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


def schedule_roster_reminder(scheduler, event_id: str, event_time: datetime) -> None:
    """Arm the early roster reminder. A past lead time is skipped, not caught up — a heads-up that lands
    minutes before start is noise, and the T-10 lobby reminder already covers the imminent case."""
    now = datetime.now(timezone.utc)
    run_at = event_time - timedelta(minutes=ROSTER_REMINDER_LEAD_MIN)
    job_id = f"pod-roster-{event_id}"
    if run_at <= now:
        with contextlib.suppress(Exception):
            scheduler.remove_job(job_id)
        return
    scheduler.add_job(
        fire_roster_reminder,
        "date",
        run_date=run_at,
        args=[event_id],
        id=job_id,
        replace_existing=True,
    )
    log.info(f"scheduled roster reminder for event {event_id} at {run_at.isoformat()}")


async def fire_roster_reminder(event_id: str) -> None:
    """Early courtesy reminder posted in the event thread with the confirmed and maybe rosters.

    Leaves socket_status untouched so the authoritative T-10 lobby reminder still fires and the startup
    sweep still re-arms both on a restart.
    """
    if _bot is None:
        log.error(f"fire_roster_reminder for {event_id}: bot reference is not initialised")
        return

    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is None:
            log.warning(f"fire_roster_reminder: pod_draft_event {event_id} not found")
            return
        if event.socket_status != "pending":
            log.info(f"fire_roster_reminder: event {event_id} is {event.socket_status}; skipping")
            return
        thread_id = int(event.discord_thread_id)
        sesh_message_id = int(event.sesh_message_id)
        event_time = event.event_time
        event_name = event.name

    if event_time <= datetime.now(timezone.utc):
        log.info(f"fire_roster_reminder: event {event_id} already started; skipping")
        return

    thread = await _fetch_thread(thread_id)
    if thread is None:
        log.warning(f"fire_roster_reminder: could not fetch thread {thread_id}")
        return

    yes, maybe = await _refetch_attendees(sesh_message_id)
    embed = build_roster_embed(event_name, event_time, yes, maybe)
    try:
        await thread.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    except discord.HTTPException:
        log.warning(f"fire_roster_reminder: could not post in thread {thread_id}", exc_info=True)


async def refresh_roster_reminder(bot: commands.Bot, sesh_message_id: str) -> None:
    """Re-render the posted roster reminder in place when RSVPs change.

    No-op until fire_roster_reminder has posted the reminder — this only ever edits an existing
    message, never creates one — and once the lobby reminder fires and flips the event past 'pending'.
    """
    loaded = await asyncio.to_thread(_load_event_for_roster, str(sesh_message_id))
    if loaded is None:
        return
    thread_id, event_time, event_name, status = loaded
    if status != "pending":
        return

    thread = await _fetch_thread(thread_id)
    if thread is None:
        return
    reminder = await _find_roster_reminder(thread)
    if reminder is None:
        return

    yes, maybe = await _refetch_attendees(int(sesh_message_id))
    embed = build_roster_embed(event_name, event_time, yes, maybe)
    try:
        await reminder.edit(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    except discord.HTTPException:
        log.warning(f"refresh_roster_reminder: could not edit reminder {reminder.id}", exc_info=True)


def _load_event_for_roster(sesh_message_id: str) -> tuple[int, datetime, str, str] | None:
    with SessionLocal() as session:
        event = session.execute(
            select(PodDraftEvent).where(PodDraftEvent.sesh_message_id == sesh_message_id)
        ).scalar_one_or_none()
        if event is None:
            return None
        return int(event.discord_thread_id), event.event_time, event.name, event.socket_status


async def _find_roster_reminder(thread: discord.Thread) -> discord.Message | None:
    """The bot's own roster reminder in a thread, located by its embed title."""
    try:
        async for message in thread.history(limit=ROSTER_SEARCH_LIMIT):
            if message.author.id != _bot.user.id:
                continue
            for embed in message.embeds:
                if embed.title == ROSTER_EMBED_TITLE:
                    return message
    except discord.HTTPException:
        log.warning(f"could not scan thread {thread.id} for the roster reminder", exc_info=True)
    return None


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


async def fetch_sesh_rsvps(bot: commands.Bot, sesh_message_id: int | str) -> tuple[list[str], list[str]] | None:
    """Fetch the parent sesh message and parse its Yes / Maybe attendee lists from the embed.
    Returns None when the message can't be fetched; ([], []) when it has no parseable sesh embed."""
    message = await fetch_sesh_message(bot, sesh_message_id)
    if message is None:
        return None
    for embed in message.embeds:
        parsed = parse_sesh_embed(embed)
        if parsed is not None:
            yes = await _resolve_attendee_names(message.guild, parsed.attendees)
            maybe = await _resolve_attendee_names(message.guild, parsed.maybe_attendees)
            return yes, maybe
    return [], []


async def _refetch_attendees(sesh_message_id: int) -> tuple[list[str], list[str]]:
    """Re-fetch the sesh embed for the latest Yes / Maybe RSVPs. Returns (yes, maybe)."""
    return await fetch_sesh_rsvps(_bot, sesh_message_id) or ([], [])


MENTION_RE = re.compile(r"^<@!?(\d+)>$")


async def _resolve_attendee_names(guild: discord.Guild | None, attendees: Sequence[str]) -> list[str]:
    """Turn raw <@id> sesh attendee tokens into member display names so they rank and dedup like
    plain-name RSVPs; non-mention entries and unresolvable ids pass through untouched."""
    resolved: list[str] = []
    for name in attendees:
        member = await _member_from_mention(guild, name)
        resolved.append(member.display_name if member else name)
    return resolved


async def _member_from_mention(guild: discord.Guild | None, token: str) -> discord.Member | None:
    if guild is None:
        return None
    match = MENTION_RE.match(token)
    if match is None:
        return None
    user_id = int(match.group(1))
    member = guild.get_member(user_id)
    if member is not None:
        return member
    try:
        return await guild.fetch_member(user_id)
    except discord.HTTPException:
        return None


def build_roster_embed(
    event_name: str, event_time: datetime, yes: list[str], maybe: list[str],
) -> discord.Embed:
    unix = int(event_time.timestamp())
    embed = discord.Embed(
        title=ROSTER_EMBED_TITLE,
        description=f"**{event_name}** begins <t:{unix}:R>",
        color=discord.Color.green(),
    )
    embed.add_field(
        name=f"✅ Yes ({len(yes)})",
        value="\n".join(yes) if yes else "None yet",
        inline=True,
    )
    if maybe:
        embed.add_field(name=f"🤷 Maybe ({len(maybe)})", value="\n".join(maybe), inline=True)
    return embed


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
