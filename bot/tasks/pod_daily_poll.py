"""Daily pod poll — the fixed-slot signup surface (Feature A).

11:00 ET on Mon/Tue/Fri/Sun the bot posts one poll offering two fixed slots (14:00 ET early,
20:00 ET late). Each slot fires a bot-native pod once it reaches the fire threshold, opening
its Draftmancer lobby via the existing reminder machinery ten minutes before the slot. Slots fire
independently, so a hot day can produce both an EU and an NA pod.

The poll message is the single RSVP surface: buttons carry static custom_ids and the persistent
PodPollView re-attaches on restart. Closure is enforced in the DB (a late click on a closed slot
gets an ephemeral notice), never by a dead duplicate card.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime

import discord
from discord.ext import commands

from bot import emojis
from bot.commands.messages import MSG_FIRST_POD_TIP_POLL
from bot.commands.pod_queue import queue_role_mention
from bot.config import settings
from bot.discord_helpers import NBSP, ZWSP, resolve_pod_chat_channel
from bot.services import pod_launch
from bot.services.ping_roles import display_emoji, spec_named
from bot.services.pod_roles import find_role, grant_pod_drafters, grant_role
from bot.services.pod_schedule import EARLY_POD_ROLE_NAME, LATE_POD_ROLE_NAME
from bot.services.pod_signals import (
    POLL_BUCKETS,
    POLL_POST_HOUR_ET,
    SCHEDULE_TZ,
    STATUS_EXPIRED,
    STATUS_FIRED,
    STATUS_OPEN,
    bucket_by_key,
    is_poll_day,
    should_fire,
    slot_event_time,
)
from bot.sets import active_set_code


log = logging.getLogger(__name__)

_bot: commands.Bot | None = None

POLL_TITLE = "Pod Launcher"
POLL_INTRO = (
    "- Event thread will be created as soon as each pod reaches {threshold} players.\n"
    "- Draftmancer lobby opens {lead} minutes before the scheduled time."
)
MARKER_CLOSED = "Closed"
POLL_PING = "{mention} `/draft` to start a pod anytime, or join one below"
MSG_POLL_INACTIVE = "This poll is no longer active."
MSG_SLOT_CLOSED = "That slot's time already passed. Catch the next poll."
SLOT_ROLE_BY_BUCKET = {"EARLY": EARLY_POD_ROLE_NAME, "LATE": LATE_POD_ROLE_NAME}
POLL_ROLE_GRANTED = (
    "{emoji} You're now on {role} and will be pinged for drafts {when}. "
    "Run `/roles` to manage your notifications."
)


def init_daily_poll(bot: commands.Bot) -> None:
    global _bot
    _bot = bot
    bot.pod_scheduler.add_job(
        fire_daily_poll, "cron", day_of_week="mon,tue,fri,sun", hour=POLL_POST_HOUR_ET, minute=0,
        timezone=SCHEDULE_TZ, id="pod-daily-poll", replace_existing=True,
    )
    log.info(f"scheduled daily pod poll at {POLL_POST_HOUR_ET:02d}:00 ET on Mon/Tue/Fri/Sun")


async def fire_daily_poll() -> None:
    if _bot is None:
        return
    today = datetime.now(SCHEDULE_TZ).date()
    if not is_poll_day(today):
        return
    if await asyncio.to_thread(pod_launch.poll_exists_for_date_sync, today):
        log.info(f"daily poll already posted for {today}; skipping")
        return

    channel = resolve_pod_chat_channel(_bot)
    if channel is None:
        log.warning("fire_daily_poll: no pod-draft-chat channel resolved")
        return

    guild = getattr(channel, "guild", None)
    embed = initial_poll_embed(today, guild)
    message = await channel.send(
        content=poll_ping_line(guild), embed=embed, view=PodPollView(),
        allowed_mentions=discord.AllowedMentions(roles=True),
    )
    guild_id = str(getattr(channel, "guild", None).id) if getattr(channel, "guild", None) else ""
    created = await asyncio.to_thread(
        pod_launch.create_poll_signals_sync,
        guild_id=guild_id, channel_id=str(channel.id), message_id=str(message.id), signal_date=today,
    )
    for signal_id, slot_time in created:
        pod_launch.arm_slot_expiry(_bot, signal_id, slot_time)
    log.info(f"posted daily pod poll for {today} as message {message.id}")


def poll_ping_line(guild: discord.Guild | None) -> str | None:
    mention = queue_role_mention(guild)
    return POLL_PING.format(mention=mention) if mention else None


def initial_poll_embed(signal_date: date, guild: discord.Guild | None = None) -> discord.Embed:
    rows = [
        (bucket.key, STATUS_OPEN, 0, slot_event_time(signal_date, bucket.key), [])
        for bucket in POLL_BUCKETS
    ]
    return build_poll_embed(rows, guild)


def build_poll_embed(
    rows: list[tuple[str, str, int, datetime | None, list[str]]], guild: discord.Guild | None = None,
) -> discord.Embed:
    intro = POLL_INTRO.format(
        threshold=emojis.mana_number(settings.pod_signal_fire_threshold), lead=pod_launch.REMINDER_LEAD_MIN,
    )
    slot_times = [slot_time for _, _, _, slot_time, _ in rows if slot_time is not None]
    day = slot_times[0].astimezone(SCHEDULE_TZ) if slot_times else None
    title = f"{POLL_TITLE} - {day:%b %-d}" if day else POLL_TITLE
    embed = discord.Embed(
        description=f"## {NBSP * 2}🚀 {title}\n{intro}",
        color=discord.Color.green(),
    )
    for bucket_key, status, count, slot_time, names in rows:
        bucket = bucket_by_key(bucket_key)
        if bucket is None:
            continue
        slot_emoji = emojis.resolve(bucket.emoji)
        slot_role = find_role(guild, SLOT_ROLE_BY_BUCKET.get(bucket_key, ""))
        slot_label = slot_role.mention if slot_role else bucket.name
        when = f"<t:{int(slot_time.timestamp())}:t>" if slot_time else ""
        count_part = f"({count})" if count else ""
        check = "✅" if status == STATUS_FIRED else ""
        header = " ".join(part for part in (slot_emoji, slot_label, when, count_part, check) if part)
        if status == STATUS_EXPIRED:
            body = MARKER_CLOSED
        elif names:
            body = "\n".join(f"> {name}" for name in names)
        else:
            body = "-"
        embed.add_field(name=ZWSP, value=f"{header}\n{body}", inline=True)
    return embed


class PodPollView(discord.ui.View):
    """Persistent — registered once at startup; the two slot buttons carry static custom_ids.
    Bucket emoji are application emojis, which can't render in label text, so each button gets its
    resolved glyph in the emoji slot at construction time."""

    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.early.emoji = emojis.resolve(bucket_by_key("EARLY").emoji)
        self.late.emoji = emojis.resolve(bucket_by_key("LATE").emoji)

    @discord.ui.button(label="Early Pod", style=discord.ButtonStyle.secondary, custom_id="pod_poll:EARLY")
    async def early(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._handle(interaction, "EARLY")

    @discord.ui.button(label="Late Pod", style=discord.ButtonStyle.secondary, custom_id="pod_poll:LATE")
    async def late(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._handle(interaction, "LATE")

    async def _handle(self, interaction: discord.Interaction, bucket_key: str) -> None:
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

        fired = False
        if (
            result.joined
            and should_fire(result.state.count, settings.pod_signal_fire_threshold)
            and await asyncio.to_thread(pod_launch.claim_fire_sync, result.state.signal_id)
        ):
            fired = True

        rows = await asyncio.to_thread(pod_launch.poll_snapshot_sync, message_id)
        embed = build_poll_embed(rows, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

        if result.first_contact:
            tip = MSG_FIRST_POD_TIP_POLL.format(threshold=settings.pod_signal_fire_threshold)
            await interaction.followup.send(tip, ephemeral=True)
        if result.joined and isinstance(interaction.user, discord.Member):
            await grant_pod_drafters(interaction.user)
            granted_role = await _grant_slot_role(interaction.user, bucket_key)
            if granted_role is not None:
                spec = spec_named(granted_role.name)
                note = POLL_ROLE_GRANTED.format(
                    emoji=display_emoji(spec) or "", role=granted_role.mention, when=spec.grant_when,
                )
                await interaction.followup.send(
                    note, ephemeral=True, allowed_mentions=discord.AllowedMentions.none(),
                )
        if fired:
            asyncio.create_task(self._launch_slot(interaction.client, result.state, message_id))

    async def _launch_slot(self, bot: commands.Bot, state, message_id: str) -> None:
        set_code = active_set_code()
        slot_time = state.slot_time
        name = await asyncio.to_thread(pod_launch.ondemand_event_name_sync, set_code, slot_time)
        event_id = await pod_launch.launch_from_signal(
            bot, state.signal_id, set_code=set_code, event_time=slot_time, name=name, open_now=False,
        )
        if event_id is not None:
            return
        await asyncio.to_thread(pod_launch.release_fire_sync, state.signal_id)
        log.warning(f"slot fire for {state.signal_id} failed to launch; reverted to open")
        rows = await asyncio.to_thread(pod_launch.poll_snapshot_sync, message_id)
        await _rerender_poll(bot, message_id, rows)


async def _grant_slot_role(member: discord.Member, bucket_key: str) -> discord.Role | None:
    """Returns the role only on a fresh grant, so the ephemeral confirmation fires once per member."""
    role_name = SLOT_ROLE_BY_BUCKET.get(bucket_key)
    if role_name is None:
        return None
    role = find_role(member.guild, role_name)
    if role is None:
        return None
    granted = await grant_role(member, role)
    return role if granted else None


async def _rerender_poll(bot: commands.Bot, message_id: str, rows: list) -> None:
    channel = resolve_pod_chat_channel(bot)
    if channel is None:
        return
    embed = build_poll_embed(rows, getattr(channel, "guild", None))
    try:
        message = await channel.fetch_message(int(message_id))
        await message.edit(embed=embed, view=PodPollView())
    except discord.HTTPException:
        log.warning(f"could not re-render poll message {message_id}", exc_info=True)
