"""Daily Pod Launcher — the day-of "who's playing today" signup surface.

Posts every day: weekdays at 11:00 ET with two slots (Early 14:00, Late 20:00), weekends at 08:00 ET
with three (Morning 10:00, Afternoon 15:00, Evening 20:00) so the earliest slot has runway. Each lazy
slot fires a bot-native pod once it reaches the threshold, graduating into a scheduled RSVP card.

A slot whose time already carries a locked scheduled pod is reflected, not reopened: it renders as a
jump-link into that pod's thread and creates no signal of its own, so the launcher and the scheduled
card are two live windows on one roster and never a duplicate. The launcher message is the single RSVP
surface for its lazy slots — buttons carry static custom_ids and PodPollView re-attaches on restart.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta

import discord
from discord.ext import commands

from bot import emojis
from bot.commands.pod_queue import queue_role_mention
from bot.commands.pod_rsvp import post_scheduled_card, register_launcher_refresh
from bot.config import settings
from bot.discord_helpers import NBSP, ZWSP, resolve_pod_chat_channel
from bot.services import pod_launch
from bot.services.ping_roles import announce_pod_grant, slot_grant_ping, spec_named
from bot.services.pod_roles import find_role, grant_pod_drafters, grant_role
from bot.services.pod_signals import (
    ALL_BUCKETS,
    SCHEDULE_TZ,
    STATUS_EXPIRED,
    STATUS_FIRED,
    WEEKDAY_POST_HOUR_ET,
    WEEKEND_POST_HOUR_ET,
    bucket_by_key,
    bucket_role_name,
    is_weekend_bucket,
    should_fire,
)
from bot.sets import active_set_code


log = logging.getLogger(__name__)

_bot: commands.Bot | None = None

POLL_TITLE = "Daily Pod Launcher"
POLL_INTRO = (
    "### Sign up for any time below\n"
    "• Event thread will be created as soon as each pod reaches {threshold} players.\n"
    "• Draftmancer lobby opens {lead} minutes before the scheduled time."
)
POLL_CLOSED_LABEL = "🔒 Signups Closed"
MARKER_CLOSED = "Closed"
MSG_POLL_INACTIVE = "This poll is no longer active."
MSG_SLOT_CLOSED = "This slot is closed."
POLL_NUDGE = "{hello}**{name}** looking for **{needed} more player{plural}** <t:{unix}:R> {link}{manat} {mention}"
POLL_NUDGE_QUIET_MINUTES = 30
LAUNCHER_CLOSE_LOOKBACK_DAYS = 3


def init_daily_poll(bot: commands.Bot) -> None:
    global _bot
    _bot = bot
    register_launcher_refresh(refresh_launcher_for_date)
    bot.pod_scheduler.add_job(
        fire_daily_poll, "cron", day_of_week="mon-fri", hour=WEEKDAY_POST_HOUR_ET, minute=0,
        timezone=SCHEDULE_TZ, id="pod-daily-poll-weekday", replace_existing=True,
    )
    bot.pod_scheduler.add_job(
        fire_daily_poll, "cron", day_of_week="sat,sun", hour=WEEKEND_POST_HOUR_ET, minute=0,
        timezone=SCHEDULE_TZ, id="pod-daily-poll-weekend", replace_existing=True,
    )
    log.info(
        f"scheduled daily pod launcher: weekdays {WEEKDAY_POST_HOUR_ET:02d}:00 ET, "
        f"weekends {WEEKEND_POST_HOUR_ET:02d}:00 ET"
    )


def _poll_channel(bot: commands.Bot) -> "discord.abc.Messageable | None":
    """The launcher lives in the coordination channel, not pod-draft-chat, so a busy chat can't bury
    it. Both the post and every re-render resolve through here so they never drift apart."""
    return bot.get_channel(settings.pod_draft_channel_id)


async def fire_daily_poll() -> None:
    if _bot is None:
        return
    today = datetime.now(SCHEDULE_TZ).date()
    if await asyncio.to_thread(pod_launch.poll_exists_for_date_sync, today):
        log.info(f"daily launcher already posted for {today}; skipping")
        return
    channel = _poll_channel(_bot)
    if channel is None:
        log.warning("fire_daily_poll: coordination channel unresolved")
        return
    message = await post_launcher(_bot, channel, today)
    if message is not None:
        log.info(f"posted daily pod launcher for {today} as message {message.id}")
    await close_recent_launchers(_bot, today)
    await pod_launch.close_past_pod_cards()


async def post_launcher(
    bot: commands.Bot, channel: "discord.abc.Messageable", signal_date: date,
) -> discord.Message | None:
    """Render and post the day's launcher, then create a lazy signal per open slot and arm its expiry.
    Shared by the daily cron and `!test poll` so both drive the identical surface."""
    guild = getattr(channel, "guild", None)
    guild_id = str(guild.id) if guild else ""
    slots = await asyncio.to_thread(pod_launch.launcher_snapshot_sync, "", signal_date)
    message = await channel.send(
        content=poll_ping_line(guild), embed=build_poll_embed(slots, guild),
        view=PodPollView(slots, guild), allowed_mentions=discord.AllowedMentions(roles=True),
    )
    created = await asyncio.to_thread(
        pod_launch.create_poll_signals_sync,
        guild_id=guild_id, channel_id=str(channel.id), message_id=str(message.id), signal_date=signal_date,
    )
    for signal_id, slot_time in created:
        pod_launch.arm_slot_expiry(bot, signal_id, slot_time)
    return message


def poll_ping_line(guild: discord.Guild | None) -> str | None:
    return queue_role_mention(guild)


def build_poll_embed(
    slots: list[pod_launch.LauncherSlot], guild: discord.Guild | None = None, closed: bool = False,
) -> discord.Embed:
    """`closed` renders the day's terminal state: signups shut, buttons gone (the caller drops the view),
    greyed, and committed slots show their fired roster without a thread link — the thread is archived by
    then and the link renders as #unknown."""
    slot_times = [slot.slot_time for slot in slots if slot.slot_time is not None]
    day = slot_times[0].astimezone(SCHEDULE_TZ) if slot_times else None
    title = f"{POLL_TITLE} - {day:%b %-d}" if day else POLL_TITLE
    description = f"## {NBSP * 2}🚀 {title}"
    if not closed:
        intro = POLL_INTRO.format(
            threshold=emojis.mana_number(settings.pod_signal_fire_threshold), lead=pod_launch.REMINDER_LEAD_MIN,
        )
        description = f"{description}\n{intro}"
    embed = discord.Embed(
        description=description,
        color=discord.Color.dark_grey() if closed else discord.Color.green(),
    )
    for slot in slots:
        bucket = bucket_by_key(slot.bucket_key)
        if bucket is None:
            continue
        slot_emoji = emojis.resolve(bucket.emoji)
        when = f"<t:{int(slot.slot_time.timestamp())}:t>" if slot.slot_time else ""
        count_part = f"**({slot.count})**" if slot.count else ""
        if is_weekend_bucket(slot.bucket_key):
            label = ""
        else:
            role = find_role(guild, bucket_role_name(slot.bucket_key) or "")
            label = role.mention if role else bucket.name
        check = "✅" if slot.committed or slot.status == STATUS_FIRED else ""
        header = " ".join(part for part in (slot_emoji, label, when, count_part, check) if part)
        roster = "\n".join(f"> {member}" for member in slot.names)
        if slot.committed:
            if closed:
                body = roster or "-"
            else:
                link = f"<#{slot.thread_id}>" if slot.thread_id else "-"
                body = f"{link}\n{roster}" if roster else link
        elif slot.status == STATUS_EXPIRED:
            body = MARKER_CLOSED
        elif slot.names:
            body = roster
        else:
            body = "-"
        embed.add_field(name=ZWSP, value=f"{header}\n{body}", inline=True)
    if closed:
        embed.set_footer(text=POLL_CLOSED_LABEL)
    return embed


def _thread_url(guild: discord.Guild | None, thread_id: str, message_id: str | None = None) -> str:
    scope = guild.id if guild is not None else "@me"
    base = f"https://discord.com/channels/{scope}/{thread_id}"
    return f"{base}/{message_id}" if message_id else base


class PodPollView(discord.ui.View):
    """Persistent. With no slots (the startup registration) it carries every bucket's toggle button so
    a restart re-attaches the handler for whichever slots a live message shows. Built from a snapshot it
    carries the day's surface: a toggle button per lazy slot, a link button into the thread per reflected
    scheduled pod. Bucket emoji are application emoji that can't render in label text, so each button
    gets its glyph in the emoji slot."""

    def __init__(
        self, slots: list[pod_launch.LauncherSlot] | None = None, guild: discord.Guild | None = None,
    ) -> None:
        super().__init__(timeout=None)
        if slots is None:
            for bucket in ALL_BUCKETS:
                self.add_item(_slot_toggle_button(bucket.key))
            return
        for slot in slots:
            bucket = bucket_by_key(slot.bucket_key)
            if bucket is None:
                continue
            if slot.committed:
                if slot.thread_id:
                    self.add_item(discord.ui.Button(
                        style=discord.ButtonStyle.link,
                        url=_thread_url(guild, slot.thread_id, slot.thread_message_id),
                        label=bucket.name, emoji=emojis.resolve(bucket.emoji),
                    ))
            else:
                self.add_item(_slot_toggle_button(slot.bucket_key, closed=slot.status == STATUS_EXPIRED))


def _slot_toggle_button(bucket_key: str, closed: bool = False) -> discord.ui.Button:
    bucket = bucket_by_key(bucket_key)
    button = discord.ui.Button(
        label=bucket.name, style=discord.ButtonStyle.secondary, disabled=closed,
        custom_id=f"pod_poll:{bucket_key}", emoji=emojis.resolve(bucket.emoji),
    )

    async def callback(interaction: discord.Interaction) -> None:
        await _handle_poll_click(interaction, bucket_key)

    button.callback = callback
    return button


async def _handle_poll_click(interaction: discord.Interaction, bucket_key: str) -> None:
    message_id = str(interaction.message.id)
    result = await asyncio.to_thread(
        pod_launch.toggle_member_sync,
        message_id, bucket_key, str(interaction.user.id), interaction.user.display_name,
    )
    if result is None:
        await interaction.response.send_message(MSG_POLL_INACTIVE, ephemeral=True)
        return
    if result.closed:
        await interaction.response.send_message(MSG_SLOT_CLOSED, ephemeral=True)
        return

    fired = (
        result.joined
        and should_fire(result.state.count, settings.pod_signal_fire_threshold)
        and await asyncio.to_thread(pod_launch.claim_fire_sync, result.state.signal_id)
    )

    signal_date = interaction.message.created_at.astimezone(SCHEDULE_TZ).date()
    slots = await asyncio.to_thread(pod_launch.launcher_snapshot_sync, message_id, signal_date)
    await interaction.response.edit_message(
        embed=build_poll_embed(slots, interaction.guild), view=PodPollView(slots, interaction.guild),
    )

    granted_role = None
    spec = None
    first_pod = False
    if result.joined and isinstance(interaction.user, discord.Member):
        first_pod = await grant_pod_drafters(interaction.user)
        granted_role = await _grant_slot_role(interaction.user, bucket_key)
        if granted_role is not None:
            spec = spec_named(granted_role.name)
    ping = slot_grant_ping(spec) if spec is not None else None
    await announce_pod_grant(
        interaction, first_pod=first_pod, granted_role=granted_role,
        welcome_role=granted_role, spec=spec, ping=ping,
    )
    if fired:
        asyncio.create_task(_launch_slot(interaction.client, result.state, message_id))
    elif result.joined:
        await _maybe_nudge_slot(interaction, result.state, bucket_key)


def build_poll_nudge(name: str, needed: int, slot_time: datetime, link: str, mention: str) -> str:
    """Launcher-slot underfill nudge, shaped to match the scheduled-pod nudge (build_underfill_message).

    `name` is the pod's prospective thread name (ondemand_event_name_sync), not the slot role, so the
    headline reads as the event and never doubles the role mention.
    """
    return POLL_NUDGE.format(
        hello=emojis.prefix("chordoHello"),
        name=name,
        needed=needed,
        plural="s" if needed != 1 else "",
        unix=int(slot_time.timestamp()),
        link=link,
        manat=emojis.get("manat"),
        mention=mention,
    )


async def _maybe_nudge_slot(interaction: discord.Interaction, state, bucket_key: str) -> None:
    """One ping to the slot role when a lazy slot reaches one short of firing, mirroring the queue's
    nudge: once per slot and only after the quiet window. Lazy slots never carry a scheduled event, so
    the scheduled-pod underfill nudge owns the reflected slots and the two never double-ping. Lands in
    pod-draft-chat with a jump link back to the launcher when POD_NUDGE_IN_CHAT is set, otherwise posts
    in place under the launcher."""
    if state.count != settings.pod_signal_fire_threshold - 1:
        return
    claimed = await asyncio.to_thread(
        pod_launch.claim_nudge_sync, state.signal_id, POLL_NUDGE_QUIET_MINUTES,
    )
    if not claimed:
        return
    role = find_role(interaction.guild, bucket_role_name(bucket_key) or "")
    if role is None:
        return
    if settings.pod_nudge_in_chat:
        channel = resolve_pod_chat_channel(interaction.client)
        link = f"- [**Sign up here**]({interaction.message.jump_url}) "
    else:
        channel = interaction.channel
        link = ""
    if channel is None:
        return
    needed = settings.pod_signal_fire_threshold - state.count
    name = pod_launch.ondemand_event_name_sync(active_set_code(), state.slot_time)
    body = build_poll_nudge(name, needed, state.slot_time, link, role.mention)
    try:
        await channel.send(body, allowed_mentions=discord.AllowedMentions(roles=True))
    except discord.HTTPException:
        log.warning("poll slot nudge send failed", exc_info=True)


async def _launch_slot(bot: commands.Bot, state, message_id: str) -> None:
    """A fired lazy slot graduates into a scheduled RSVP card: the signups carry over as Yes, and the
    card gathers any late signups right up to the lobby open. The slot then reflects the card as a
    jump-link on the next render. Falls back to reopening the slot if the card can't be posted."""
    set_code = active_set_code()
    slot_time = state.slot_time
    name = await asyncio.to_thread(pod_launch.ondemand_event_name_sync, set_code, slot_time)
    signups = await asyncio.to_thread(pod_launch.poll_yes_members_sync, state.signal_id)
    channel = _poll_channel(bot)
    event_id = None
    if isinstance(channel, discord.TextChannel):
        event_id = await post_scheduled_card(
            bot, channel, set_code=set_code, event_time=slot_time, name=name, preseed_yes=signups,
        )
    if event_id is None:
        await asyncio.to_thread(pod_launch.release_fire_sync, state.signal_id)
        log.warning(f"slot fire for {state.signal_id} failed to launch; reverted to open")
    await _rerender_poll(bot, message_id, slot_time.astimezone(SCHEDULE_TZ).date())


async def _grant_slot_role(member: discord.Member, bucket_key: str) -> discord.Role | None:
    """Returns the role only on a fresh grant, so the ephemeral confirmation fires once per member."""
    role_name = bucket_role_name(bucket_key)
    if role_name is None:
        return None
    role = find_role(member.guild, role_name)
    if role is None:
        return None
    granted = await grant_role(member, role)
    return role if granted else None


async def refresh_launcher_for_date(bot: commands.Bot, signal_date: date) -> None:
    """Re-render the day's launcher so a committed slot tracks late Yes/No churn on its scheduled card.
    A past day renders closed instead, so late churn can never reopen a retired board. No-op when no
    launcher was posted that day."""
    if signal_date < datetime.now(SCHEDULE_TZ).date():
        await close_launcher_for_date(bot, signal_date)
        return
    message_id = await asyncio.to_thread(pod_launch.launcher_message_id_for_date_sync, signal_date)
    if message_id is None:
        return
    await _rerender_poll(bot, message_id, signal_date)


async def close_recent_launchers(bot: commands.Bot, today: date) -> None:
    """Retire the last few days' launchers so a stale board can no longer be signed up on. Bounded to a
    short window and idempotent, so each daily post re-touches only a handful and an already-closed one
    is left untouched."""
    since = today - timedelta(days=LAUNCHER_CLOSE_LOOKBACK_DAYS)
    dates = await asyncio.to_thread(pod_launch.past_launcher_dates_sync, today, since)
    for signal_date in dates:
        await close_launcher_for_date(bot, signal_date)


async def close_launcher_for_date(bot: commands.Bot, signal_date: date) -> None:
    """Edit the day's launcher into its terminal state: signups closed, no buttons, no role ping (which
    also clears the gold mention tint), greyed. No-op when no launcher was posted or it is already
    closed."""
    ref = await asyncio.to_thread(pod_launch.launcher_ref_for_date_sync, signal_date)
    if ref is None:
        return
    channel_id, message_id = ref
    channel = bot.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await bot.fetch_channel(int(channel_id))
        except discord.HTTPException:
            return
    guild = getattr(channel, "guild", None)
    slots = await asyncio.to_thread(pod_launch.launcher_snapshot_sync, message_id, signal_date)
    try:
        message = await channel.fetch_message(int(message_id))
        if not message.components and not message.content:
            return
        await message.edit(content=None, embed=build_poll_embed(slots, guild, closed=True), view=None)
    except discord.HTTPException:
        log.warning(f"could not close launcher message {message_id}", exc_info=True)


async def _rerender_poll(bot: commands.Bot, message_id: str, signal_date: date) -> None:
    channel = _poll_channel(bot)
    if channel is None:
        return
    guild = getattr(channel, "guild", None)
    slots = await asyncio.to_thread(pod_launch.launcher_snapshot_sync, message_id, signal_date)
    try:
        message = await channel.fetch_message(int(message_id))
        await message.edit(embed=build_poll_embed(slots, guild), view=PodPollView(slots, guild))
    except discord.HTTPException:
        log.warning(f"could not re-render launcher message {message_id}", exc_info=True)
