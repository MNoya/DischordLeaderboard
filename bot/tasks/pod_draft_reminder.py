"""T-5 minute pod-draft reminder fired by APScheduler, plus the shared roster reads.

Re-fetches the latest attendee list — the sesh embed for sesh-born pods, the signal members for
card-born pods — resolves Discord member mentions on a best-effort basis, and posts the Draftmancer
link in the event thread
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
from bot.discord_helpers import BLANK_LINE
from bot.models import PodDraftEvent, PodSignal, PodSignalMember
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_reminder_copy import (
    LOBBY_OPEN,
    LOBBY_OPEN_HEADLINE,
    ROSTER_REMINDER_LINE,
    ROSTER_REMINDER_TITLE,
)
from bot.services.pod_signals import RSVP_MAYBE, RSVP_YES
from bot.services.pod_draft_manager import start_manager
from bot.services import pod_format_interest as fi
from bot.services.pod_drafts import (
    draftmancer_url_for,
    event_member_interests_sync,
    load_event_pairing_mode_sync,
)
from bot.services.pod_join_button import build_join_view
from bot.services.pod_link_dm import send_lobby_link_dms
from bot.services.pod_team_vote import (
    build_team_vote_offer_embed,
    build_team_vote_view,
    find_team_vote_card,
)
from bot.services.sesh_parser import parse_sesh_embed


REMINDER_LEAD_MIN = 10
ROSTER_REMINDER_LEAD_MIN = 60
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

    manager = await start_manager(
        _bot, event_id, draftmancer_session, thread_id, set_code, expected_attendee_count,
        event_name=event_name,
        draftmancer_url=draftmancer_url,
        rsvps_yes=list(attendees),
        rsvps_maybe=list(maybe_attendees),
    )
    if manager is not None:
        await manager.await_ownership()
        interests = await asyncio.to_thread(event_member_interests_sync, event_id)
        if fi.should_offer_format_poll(fi.composition(interests)):
            await manager.offer_format_poll()

    body = build_lobby_open_body(draftmancer_url, mention_block)
    log.info(f"fire_reminder body repr for {event_id} (early={early}): {body!r}")
    try:
        await thread.send(
            body, view=build_join_view(draftmancer_session),
            allowed_mentions=discord.AllowedMentions(users=True),
        )
    except discord.HTTPException:
        log.warning(f"fire_reminder: could not post in thread {thread_id}", exc_info=True)
        return

    # Transition out of 'pending' so the startup sweep doesn't re-fire on a restart
    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is not None and event.socket_status == "pending":
            event.socket_status = "reminded"
            session.commit()

    recipients = await _link_dm_recipients(thread.guild, attendees, maybe_attendees)
    await send_lobby_link_dms(
        _bot, session_id=draftmancer_session, thread=thread, recipients=recipients,
    )

    if early:
        scheduler = getattr(_bot, "pod_scheduler", None)
        if scheduler is not None:
            try:
                scheduler.remove_job(f"pod-reminder-{event_id}")
                log.info(f"early-open cancelled pending reminder job for {event_id}")
            except Exception:
                log.info(f"no pending reminder job to cancel for {event_id}", exc_info=True)


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
        sesh_message_id = event.sesh_message_id
        event_time = event.event_time
        event_name = event.name

    if event_time <= datetime.now(timezone.utc):
        log.info(f"fire_roster_reminder: event {event_id} already started; skipping")
        return

    thread = await _fetch_thread(thread_id)
    if thread is None:
        log.warning(f"fire_roster_reminder: could not fetch thread {thread_id}")
        return

    yes, maybe = await event_rsvps(event_id, sesh_message_id)
    embed = build_roster_embed(event_name, event_time, yes, maybe)
    try:
        await thread.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    except discord.HTTPException:
        log.warning(f"fire_roster_reminder: could not post in thread {thread_id}", exc_info=True)
    await maybe_offer_prelobby_team_vote(thread, event_id, len(yes))


def _prelobby_team_vote_size(yes_count: int) -> int | None:
    """The Team-Draft vote size when the Yes roster is auto-offer eligible at the T-60 reminder — exactly
    six, a clean 3v3. A full pod plays a bracket; anything else is left alone."""
    return 6 if yes_count == 6 else None


async def maybe_offer_prelobby_team_vote(thread: discord.Thread, event_id: str, yes_count: int) -> None:
    """At the T-60 roster reminder, offer Team Draft when the Yes roster settled small and even, so the pod
    decides the pairing before the lobby opens. A separate call-to-action card whose tally lives on the
    message, so it needs no live manager; the T-10 lobby adopts the same card."""
    size = _prelobby_team_vote_size(yes_count)
    if size is None:
        return
    pairing = await asyncio.to_thread(load_event_pairing_mode_sync, event_id)
    if pairing == "team":
        return
    if await find_team_vote_card(thread, event_id) is not None:
        return
    try:
        await thread.send(embed=build_team_vote_offer_embed([], [], size), view=build_team_vote_view(event_id))
    except discord.HTTPException:
        log.warning(f"fire_roster_reminder: could not post team offer in thread {thread.id}", exc_info=True)


def schedule_team_vote_offer(scheduler, event_id: str, event_time: datetime) -> None:
    """Arm the at-start Team-Draft offer check. A past start time is skipped — the offer only makes sense
    while the lobby is still gathering at o'clock."""
    now = datetime.now(timezone.utc)
    job_id = f"pod-teamvote-{event_id}"
    if event_time <= now:
        with contextlib.suppress(Exception):
            scheduler.remove_job(job_id)
        return
    scheduler.add_job(
        fire_team_vote_offer, "date", run_date=event_time,
        args=[event_id], id=job_id, replace_existing=True,
    )
    log.info(f"scheduled team-vote offer for event {event_id} at {event_time.isoformat()}")


async def fire_team_vote_offer(event_id: str) -> None:
    """At the scheduled start time, offer Team Draft when the lobby settled small and even (four to six
    players). The manager is already live from the T-10 lobby reminder; a full, odd, or empty lobby is
    left alone until a later join makes it eligible, and offer_team_vote no-ops if the pod already
    started or is already a team draft."""
    manager = ACTIVE_POD_MANAGERS.get(event_id)
    if manager is None:
        log.info(f"fire_team_vote_offer: no live manager for {event_id}; skipping")
        return
    await manager.offer_team_vote_if_eligible()


async def refresh_roster_reminder(bot: commands.Bot, sesh_message_id: str) -> None:
    """Re-render the posted roster reminder in place when sesh RSVPs change.

    No-op until fire_roster_reminder has posted the reminder — this only ever edits an existing
    message, never creates one — and once the lobby reminder fires and flips the event past 'pending'.
    """
    loaded = await asyncio.to_thread(_load_event_for_roster, str(sesh_message_id))
    if loaded is None:
        return
    thread_id, event_time, event_name, status = loaded
    if status != "pending":
        return
    yes, maybe = await _refetch_attendees(int(sesh_message_id))
    await _edit_roster_reminder(thread_id, event_name, event_time, yes, maybe)


async def refresh_roster_reminder_for_event(
    bot: commands.Bot, event_id: str, yes: list[str], maybe: list[str],
) -> None:
    """Signal-keyed twin of refresh_roster_reminder, fed the rosters by the RSVP card handler."""
    loaded = await asyncio.to_thread(_load_event_for_roster_by_id, event_id)
    if loaded is None:
        return
    thread_id, event_time, event_name, status = loaded
    if status != "pending":
        return
    await _edit_roster_reminder(thread_id, event_name, event_time, yes, maybe)


async def _edit_roster_reminder(
    thread_id: int, event_name: str, event_time: datetime, yes: list[str], maybe: list[str],
) -> None:
    thread = await _fetch_thread(thread_id)
    if thread is None:
        return
    reminder = await _find_roster_reminder(thread)
    if reminder is None:
        return
    embed = build_roster_embed(event_name, event_time, yes, maybe)
    try:
        await reminder.edit(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    except discord.HTTPException:
        log.warning(f"could not edit roster reminder {reminder.id}", exc_info=True)


def _load_event_for_roster(sesh_message_id: str) -> tuple[int, datetime, str, str] | None:
    with SessionLocal() as session:
        event = session.execute(
            select(PodDraftEvent).where(PodDraftEvent.sesh_message_id == sesh_message_id)
        ).scalar_one_or_none()
        if event is None:
            return None
        return int(event.discord_thread_id), event.event_time, event.name, event.socket_status


def _load_event_for_roster_by_id(event_id: str) -> tuple[int, datetime, str, str] | None:
    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
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
                if embed.title == ROSTER_REMINDER_TITLE:
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


async def fetch_sesh_rsvp_ids(bot: commands.Bot, sesh_message_id: int | str) -> list[tuple[str, str]] | None:
    """(discord_id, display_name) for the sesh Yes-then-Maybe attendees carrying a resolvable mention,
    Yes first — the second-table candidate pool for a sesh pod. None when the message is gone; name-only
    attendees are skipped since they can't be matched or pinged by id."""
    message = await fetch_sesh_message(bot, sesh_message_id)
    if message is None:
        return None
    for embed in message.embeds:
        parsed = parse_sesh_embed(embed)
        if parsed is None:
            continue
        roster: list[tuple[str, str]] = []
        seen: set[str] = set()
        for token in list(parsed.attendees) + list(parsed.maybe_attendees):
            match = MENTION_RE.match(token)
            if match is None or match.group(1) in seen:
                continue
            discord_id = match.group(1)
            seen.add(discord_id)
            member = await _member_from_mention(message.guild, token)
            roster.append((discord_id, member.display_name if member else discord_id))
        return roster
    return []


async def _refetch_attendees(sesh_message_id: int) -> tuple[list[str], list[str]]:
    """Re-fetch the sesh embed for the latest Yes / Maybe RSVPs. Returns (yes, maybe)."""
    return await fetch_sesh_rsvps(_bot, sesh_message_id) or ([], [])


async def event_rsvps(event_id: str, sesh_message_id: str | None) -> tuple[list[str], list[str]]:
    """Latest Yes / Maybe rosters for an event: the sesh embed for sesh-born pods, the signal
    members for card-born pods."""
    if sesh_message_id is not None:
        return await _refetch_attendees(int(sesh_message_id))
    rsvps = await asyncio.to_thread(signal_rsvps_sync, event_id)
    return rsvps or ([], [])


def signal_rsvps_sync(event_id: str) -> tuple[list[str], list[str]] | None:
    """Yes / Maybe display names off the signal that created this pod, in join order; None when the
    pod has no signal. Poll and queue members are implicit Yes."""
    with SessionLocal() as session:
        signal = session.execute(
            select(PodSignal).where(PodSignal.event_id == event_id)
        ).scalar_one_or_none()
        if signal is None:
            return None
        rows = session.execute(
            select(PodSignalMember.rsvp, PodSignalMember.display_name)
            .where(PodSignalMember.signal_id == signal.id)
            .order_by(PodSignalMember.created_at)
        ).all()
    yes = [name for state, name in rows if state == RSVP_YES]
    maybe = [name for state, name in rows if state == RSVP_MAYBE]
    return yes, maybe


MENTION_RE = re.compile(r"^<@!?(\d+)>$")


async def _resolve_attendee_names(guild: discord.Guild | None, attendees: Sequence[str]) -> list[str]:
    """Turn raw <@id> sesh attendee tokens into member display names so they rank and dedup like
    plain-name RSVPs; non-mention entries and unresolvable ids pass through untouched."""
    resolved: list[str] = []
    for name in attendees:
        member = await _member_from_mention(guild, name)
        resolved.append(member.display_name if member else name)
    return resolved


async def _link_dm_recipients(
    guild: discord.Guild | None, yes_tokens: Sequence[str], maybe_tokens: Sequence[str],
) -> list[tuple[str, str, str]]:
    """(discord_id, display_name, rsvp) for the sesh attendees the link DM can reach. Sesh tokens that
    aren't `<@id>` mentions carry no id, so they drop out — the DM can't find them anyway."""
    recipients: list[tuple[str, str, str]] = []
    for rsvp, tokens in (("yes", yes_tokens), ("maybe", maybe_tokens)):
        for token in tokens:
            member = await _member_from_mention(guild, token)
            if member is not None:
                recipients.append((str(member.id), member.display_name, rsvp))
    return recipients


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


def build_lobby_open_body(draftmancer_url: str, mention_block: str) -> str:
    """The lobby-open post shared by sesh reminders (fire_reminder) and bot-native opens
    (open_ondemand_lobby). The lobby is joinable the moment the link posts and the start is gated on the
    ready-check, so the headline is 'Lobby opened' in every path, with no countdown."""
    mentions = f"\n\n{mention_block}" if mention_block else ""
    body = LOBBY_OPEN.format(
        draftmancer=emojis.get("draftmancer"), headline=LOBBY_OPEN_HEADLINE, url=draftmancer_url,
        mentions=mentions,
    )
    return f"{body}\n{BLANK_LINE}"


def build_roster_embed(
    event_name: str, event_time: datetime, yes: list[str], maybe: list[str],
) -> discord.Embed:
    unix = int(event_time.timestamp())
    embed = discord.Embed(
        title=ROSTER_REMINDER_TITLE,
        description=ROSTER_REMINDER_LINE.format(name=event_name, unix=unix),
        color=discord.Color.green(),
    )
    embed.add_field(
        name=f"✅ Yes ({len(yes)})",
        value="\n".join(f"> {name}" for name in yes) if yes else "None yet",
        inline=True,
    )
    if maybe:
        maybe_list = "\n".join(f"> {name}" for name in maybe)
        embed.add_field(name=f"🤷 Maybe ({len(maybe)})", value=maybe_list, inline=True)
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
