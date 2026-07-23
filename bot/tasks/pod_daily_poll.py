"""Daily Pod Launcher — the day-of "who's playing today" signup surface.

Posts every day at 11:00 ET with the same two slots (Early 14:00, Late 20:00). Each lazy slot
fires a bot-native pod once it reaches the threshold, graduating into a scheduled RSVP card.

A slot whose time already carries a locked scheduled pod is reflected, not reopened: it renders a
Yes/No toggle that writes to that pod's scheduled card and creates no signal of its own, so the launcher
and the card are two live windows on one roster and never a duplicate. The launcher message is the
single RSVP surface for its lazy slots — buttons carry static custom_ids and PodPollView re-attaches on
restart.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

import discord
from discord.ext import commands

from bot import emojis
from bot.commands.messages import (
    MSG_DRAFT_STARTS,
    MSG_FORMAT_PREFERENCE_BUTTON,
    MSG_PREFERENCE_LINE,
    MSG_YOUR_CUBES_LINE,
    MSG_YOUR_SETS_LINE,
)
from bot.commands.pod_queue import queue_role_mention
from bot.commands.pod_rsvp import (
    ReminderRsvpButton,
    apply_card_rsvp,
    post_scheduled_card,
    refresh_event_rsvp_surfaces,
    register_launcher_refresh,
)
from bot.config import settings
from bot.discord_helpers import NBSP, ZWSP
from bot.services import pod_format
from bot.services import pod_format_interest as fi
from bot.services import pod_format_poll
from bot.services import pod_launch
from bot.services.ping_roles import (
    announce_pod_grant,
    register_format_preference_opener,
    send_join_confirmation_card,
    slot_grant_ping,
    spec_named,
)
from bot.services.pod_reminder_copy import SLOT_FIRE_PING
from bot.services.pod_roles import find_role, grant_pod_drafters, grant_role
from bot.services.pod_signals import (
    ALL_BUCKETS,
    RSVP_NO,
    RSVP_YES,
    SCHEDULE_TZ,
    STATUS_EXPIRED,
    STATUS_FIRED,
    POST_HOUR_ET,
    bucket_by_key,
    bucket_role_name,
    slot_role_name_for_event_time,
)
from bot.sets import active_set_code, set_name_for
from bot.tasks.pod_draft_reminder import register_reminder_view_builder
from bot.tasks.pod_underfill import clear_slot_nudge, refresh_slot_nudge, schedule_slot_underfill_checks


log = logging.getLogger(__name__)

_bot: commands.Bot | None = None

POLL_TITLE = "Daily Pod Launcher"
POLL_INTRO = (
    "### Sign up for any time below\n"
    "• Event thread will be created as soon as each Pod reaches **{threshold} players**\n"
    "• Draftmancer lobby opens **{lead} minutes before** the scheduled time\n"
    "• Use **Format Preference** to show your Latest Set or Flashback pick"
)
POLL_CLOSED_LABEL = "🔒 Signups Closed - Opens Daily 11AM ET"
MARKER_CLOSED = "Closed"
MSG_POLL_INACTIVE = "This poll is no longer active."
MSG_SLOT_CLOSED = "This slot is closed."
LAUNCHER_CLOSE_LOOKBACK_DAYS = 3

CHAMPIONSHIP_SLOT_LABEL = "Set Championship"
CHAMPIONSHIP_CROWN = "👑"
CHAMPIONSHIP_POINTER_TOP = 8


def init_daily_poll(bot: commands.Bot) -> None:
    global _bot
    _bot = bot
    register_launcher_refresh(refresh_launcher_for_date)
    bot.pod_scheduler.add_job(
        fire_daily_poll, "cron", hour=POST_HOUR_ET, minute=0,
        timezone=SCHEDULE_TZ, id="pod-daily-poll", replace_existing=True,
    )
    log.info(f"scheduled daily pod launcher at {POST_HOUR_ET:02d}:00 ET")


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
    """Render and post the day's launcher, then create a lazy signal per open slot and arm its expiry
    and underfill beats. Shared by the daily cron and `!test poll` so both drive the identical surface."""
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
    posted_at = datetime.now(timezone.utc)
    for signal_id, slot_time in created:
        pod_launch.arm_slot_expiry(bot, signal_id, slot_time)
        schedule_slot_underfill_checks(bot.pod_scheduler, signal_id, slot_time, posted_at)
    return message


def poll_ping_line(guild: discord.Guild | None) -> str | None:
    return queue_role_mention(guild)


def build_poll_embed(
    slots: list[pod_launch.LauncherSlot], guild: discord.Guild | None = None, closed: bool = False,
) -> discord.Embed:
    """`closed` renders the day's terminal state: signups shut, buttons gone (the caller drops the view),
    greyed. A committed slot links to its coordination card by name through `_committed_card_link`, which
    survives the thread archiving, so the link stays live in both the open and the closed render."""
    slot_times = [slot.slot_time for slot in slots if slot.slot_time is not None]
    day = slot_times[0].astimezone(SCHEDULE_TZ) if slot_times else None
    title = f"{POLL_TITLE} - {day:%b %-d}" if day else POLL_TITLE
    description = f"## {NBSP * 2}🚀 {title}"
    if not closed:
        intro = POLL_INTRO.format(
            threshold=settings.pod_signal_fire_threshold, lead=pod_launch.REMINDER_LEAD_MIN,
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
        when = f"<t:{int(slot.slot_time.timestamp())}:t>" if slot.slot_time else ""
        count_part = f"**({slot.count})**" if slot.count else ""
        check = "✅" if slot.committed or slot.status == STATUS_FIRED else ""
        if slot.championship:
            symbol = emojis.get(slot.set_code.lower()) if slot.set_code else ""
            label = f"**{CHAMPIONSHIP_SLOT_LABEL}**"
            header = " ".join(part for part in (CHAMPIONSHIP_CROWN, symbol, label, when) if part)
            body = _championship_body(slot, guild)
        else:
            slot_emoji = emojis.resolve(bucket.emoji)
            role = find_role(guild, bucket_role_name(slot.bucket_key) or "")
            label = role.mention if role else bucket.name
            header = " ".join(part for part in (slot_emoji, label, when, count_part, check) if part)
            link = _committed_card_link(guild, slot) if slot.committed else None
            roster = _roster_lines(slot.names, slot.interests, link, _slot_pod_format(slot), guild)
            if slot.committed:
                body = roster or "-"
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


def _championship_body(slot: pod_launch.LauncherSlot, guild: discord.Guild | None) -> str:
    """The championship lane on the launcher: a link into the thread and the current top Yes RSVPs,
    read-only. Signup happens in the thread, so this lane carries no join toggle."""
    lines: list[str] = []
    link = _committed_card_link(guild, slot)
    if link:
        lines.append(link)
    for index, name in enumerate(slot.names[:CHAMPIONSHIP_POINTER_TOP], 1):
        lines.append(f"> {index}. {name}")
    return "\n".join(lines) if lines else "-"


def _roster_lines(
    names: list[str], interests: tuple[tuple[str, ...], ...],
    thread_link: str | None = None, pod_format: str = fi.LATEST, guild: discord.Guild | None = None,
) -> str:
    """The slot's roster sorted into format teams, each under an emoji-and-count header. Dedicated picks
    anchor their team, Any players fill whichever team is closer to a table, no-preference rides with
    Latest — so an all-latest slot shows one Latest Set block. Names and interests share the created-at
    order, so the pairs line up. A committed pod's thread link sits directly above the team block playing
    its format."""
    if not names:
        return thread_link or ""
    paired = []
    for index, name in enumerate(names):
        codes = interests[index] if index < len(interests) else ()
        display = f"{fi.FLEXIBLE_MARKER} {name}" if fi.is_flexible(codes) else name
        paired.append((display, codes))
    latest_team, flashback_team = fi.format_teams(paired)
    latest_label = _format_role_label(guild, fi.LATEST_SET_ROLE_NAME)
    flashback_label = _format_role_label(guild, fi.FLASHBACK_ROLE_NAME)
    latest_block = _team_block(fi.latest_emoji(), latest_label, latest_team) if latest_team else None
    flashback_block = _team_block(fi.flashback_emoji(), flashback_label, flashback_team) if flashback_team else None
    if thread_link:
        if flashback_block is not None and (pod_format == fi.FLASHBACK or latest_block is None):
            flashback_block = f"{thread_link}\n{flashback_block}"
        else:
            latest_block = f"{thread_link}\n{latest_block}"
    blocks = [block for block in (latest_block, flashback_block) if block]
    return f"\n> {NBSP}\n".join(blocks)


def _slot_pod_format(slot: pod_launch.LauncherSlot) -> str:
    if slot.set_code and slot.set_code != active_set_code():
        return fi.FLASHBACK
    return fi.LATEST


def _format_role_label(guild: discord.Guild | None, role_name: str) -> str:
    role = find_role(guild, role_name)
    return role.mention if role else role_name


def _team_block(icon: object, label: str, team: list[str]) -> str:
    header = f"> {icon}{label} **({len(team)})**"
    return "\n".join([header] + [f"> {name}" for name in team])


def _jump_url(guild: discord.Guild | None, channel_id: str, message_id: str | None = None) -> str:
    scope = guild.id if guild is not None else "@me"
    base = f"https://discord.com/channels/{scope}/{channel_id}"
    return f"{base}/{message_id}" if message_id else base


def _committed_card_link(guild: discord.Guild | None, slot: pod_launch.LauncherSlot) -> str | None:
    """A committed pod's named link to its coordination card. A markdown link, not a `<#thread>` mention:
    the mention renders as #unknown once the thread archives, while a card jump link survives. Falls back
    to the thread when no card is tracked, as on the championship lane whose signup lives in the thread."""
    if not slot.thread_name:
        return None
    if slot.card_channel_id and slot.card_message_id:
        url = _jump_url(guild, slot.card_channel_id, slot.card_message_id)
    elif slot.thread_id:
        url = _jump_url(guild, slot.thread_id, slot.thread_message_id)
    else:
        return None
    return f"[__**{slot.thread_name}**__]({url})"


class PodPollView(discord.ui.View):
    """Persistent. With no slots (the startup registration) it carries every bucket's lazy-toggle and
    committed-RSVP button so a restart re-attaches the handler for whichever slots a live message shows.
    Built from a snapshot it carries the day's surface: a lazy slot renders its join toggle, a committed
    slot renders a Yes/No toggle that writes to its scheduled card. Format Preference always rides along
    while the board is live. Bucket emoji are application emoji that can't render in label text, so each
    button gets its glyph in the emoji slot."""

    def __init__(
        self, slots: list[pod_launch.LauncherSlot] | None = None, guild: discord.Guild | None = None,
    ) -> None:
        super().__init__(timeout=None)
        if slots is None:
            for bucket in ALL_BUCKETS:
                self.add_item(_slot_toggle_button(bucket.key))
                self.add_item(_slot_rsvp_button(bucket.key))
            self.add_item(_interest_button())
            return
        for slot in slots:
            bucket = bucket_by_key(slot.bucket_key)
            if bucket is None:
                continue
            if slot.committed and slot.championship and slot.thread_id:
                self.add_item(discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    url=_jump_url(guild, slot.thread_id, slot.thread_message_id),
                    label=CHAMPIONSHIP_SLOT_LABEL, emoji=CHAMPIONSHIP_CROWN,
                ))
            elif slot.committed and slot.card_message_id:
                self.add_item(_slot_rsvp_button(slot.bucket_key))
            elif slot.committed and slot.thread_id:
                self.add_item(discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    url=_jump_url(guild, slot.thread_id, slot.thread_message_id),
                    label=bucket.name, emoji=emojis.resolve(bucket.emoji),
                ))
            elif not slot.committed:
                self.add_item(_slot_toggle_button(slot.bucket_key, closed=slot.status == STATUS_EXPIRED))
        self.add_item(_interest_button())


INTEREST_BUTTON_ID = "pod_poll_interest"
INTEREST_PLACEHOLDER = "Select your Format Preference"
INTEREST_DESC_FLASHBACK = "Any Past Set, Rank Your Favorites"
INTEREST_DESC_CUBE = "Choose from the server's cubes"
MSG_INTEREST_PROMPT = (
    "### Choose what you would prefer to draft\n"
    "**Save** your preference, or **Confirm** to also join that time slot today"
)
MSG_INTEREST_SAVED = f"### ✨ Saved\n{MSG_PREFERENCE_LINE}"
MSG_SLOT_ADDED = "✅ Added to {name}"
MSG_SLOT_REMOVED = "❌ Removed from {name}"
SAVE_BUTTON_LABEL = "Save"
SAVE_BUTTON_EMOJI = "💾"
CONFIRM_SLOT_LABEL = "Confirm {name}"
RANK_BUTTON_LABEL = "Rank Sets"
RANK_BUTTON_EMOJI = "📊"
RANK_MODAL_TITLE = "Rank Flashback Sets"
RANK_MODAL_FIELD = "Set Codes"
RANK_MODAL_PLACEHOLDER = "e.g. XXX YYY NEO"
RANK_MODAL_EXPLAINER = (
    f"Set your Flashback preference, best first, **up to {fi.FLASHBACK_RANKING_MAX} sets**\n\nWhen a pod opens a "
    "**Format Vote**, your sets are added to the poll options"
)
MSG_RANK_EMPTY = "No sets ranked"
CUBE_SELECT_PLACEHOLDER = "Select Cubes"


def _interest_button() -> discord.ui.Button:
    button = discord.ui.Button(
        label=MSG_FORMAT_PREFERENCE_BUTTON, style=discord.ButtonStyle.primary,
        custom_id=INTEREST_BUTTON_ID, emoji=fi.FLEXIBLE_EMOJI, row=4,
    )

    async def callback(interaction: discord.Interaction) -> None:
        await _open_interest_prompt(interaction)

    button.callback = callback
    return button


async def _launcher_signal_date(message: discord.Message) -> date:
    stored = await asyncio.to_thread(pod_launch.launcher_date_for_message_sync, str(message.id))
    return stored or message.created_at.astimezone(SCHEDULE_TZ).date()


async def _open_interest_prompt(interaction: discord.Interaction) -> None:
    """Open a per-user ephemeral picker seeded with the player's standing preference. The launcher board
    only changes once they confirm, so a mis-tap costs nothing."""
    await interaction.response.defer(ephemeral=True, thinking=True)
    launcher_message_id = str(interaction.message.id)
    signal_date = await _launcher_signal_date(interaction.message)
    await _send_interest_prompt(interaction, launcher_message_id, signal_date)


async def open_interest_prompt_from_card(interaction: discord.Interaction) -> None:
    """The picker opened from a grant card's Format Preference button, resolving the newest launcher so
    Confirm buttons target its slots. With no launcher on record the picker still saves the standing
    preference; its Confirm buttons refuse through the normal inactive-poll path."""
    await interaction.response.defer(ephemeral=True, thinking=True)
    launcher = await asyncio.to_thread(pod_launch.latest_launcher_sync)
    if launcher is not None:
        launcher_message_id, signal_date = launcher
    else:
        launcher_message_id, signal_date = "", datetime.now(SCHEDULE_TZ).date()
    await _send_interest_prompt(interaction, launcher_message_id, signal_date)


async def _send_interest_prompt(
    interaction: discord.Interaction, launcher_message_id: str, signal_date: date,
    event_id: str | None = None,
) -> None:
    """A picker opened from a committed pod (`event_id` set) carries no per-slot Confirm buttons — the
    player is already in that pod, so it saves the preference only and re-renders that pod's surfaces."""
    user_id = str(interaction.user.id)
    current = await asyncio.to_thread(pod_launch.player_interest_sync, user_id)
    ranking = await asyncio.to_thread(pod_launch.player_flashback_ranking_sync, user_id)
    cubes = await asyncio.to_thread(pod_launch.player_cube_choices_sync, user_id)
    if event_id is None:
        slots = await asyncio.to_thread(pod_launch.launcher_snapshot_sync, launcher_message_id, signal_date)
        slot_states = [
            (slot.bucket_key, slot.status != STATUS_EXPIRED, slot.committed)
            for slot in slots if bucket_by_key(slot.bucket_key) is not None
        ]
    else:
        slot_states = []
    view = InterestPromptView(
        launcher_message_id, signal_date, current, ranking, cubes, slot_states, event_id,
    )
    await interaction.followup.send(view=view, ephemeral=True)


REMINDER_FORMAT_PREFIX = "podremindfmt"


class ReminderFormatPreferenceButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=rf"{REMINDER_FORMAT_PREFIX}:(?P<event_id>.+)",
):
    """Format Preference on the T-60 roster reminder. Opens the same picker as the launcher, minus the
    per-slot Confirm buttons, so there is only Save. The event id rides in the custom_id so Save can
    re-render this pod's card and reminder, and so it keeps working after a restart."""

    def __init__(self, event_id: str) -> None:
        super().__init__(discord.ui.Button(
            label=MSG_FORMAT_PREFERENCE_BUTTON, style=discord.ButtonStyle.primary,
            emoji=fi.FLEXIBLE_EMOJI, custom_id=f"{REMINDER_FORMAT_PREFIX}:{event_id}",
        ))
        self.event_id = event_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["event_id"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await open_interest_prompt_from_reminder(interaction, self.event_id)


async def open_interest_prompt_from_reminder(interaction: discord.Interaction, event_id: str) -> None:
    """The picker opened from a pod's roster reminder: Save only, no per-slot Confirm. Resolves the day's
    launcher so Save still updates the launcher board and the player's standing preference, and carries
    the event id so Save re-renders this pod's card and reminder."""
    await interaction.response.defer(ephemeral=True, thinking=True)
    launcher = await asyncio.to_thread(pod_launch.latest_launcher_sync)
    if launcher is not None:
        launcher_message_id, signal_date = launcher
    else:
        launcher_message_id, signal_date = "", datetime.now(SCHEDULE_TZ).date()
    await _send_interest_prompt(interaction, launcher_message_id, signal_date, event_id=event_id)


def build_reminder_view(event_id: str) -> discord.ui.View:
    """The roster reminder's controls: Sign Up / Can't recording against the pod, and Format Preference
    opening the Save-only picker. All three carry the event id so they resolve the pod after a restart."""
    view = discord.ui.View(timeout=None)
    view.add_item(ReminderRsvpButton(RSVP_YES, event_id))
    view.add_item(ReminderRsvpButton(RSVP_NO, event_id))
    view.add_item(ReminderFormatPreferenceButton(event_id))
    return view


register_format_preference_opener(open_interest_prompt_from_card)
register_reminder_view_builder(build_reminder_view)


def _slot_short_name(bucket_key: str) -> str:
    bucket = bucket_by_key(bucket_key)
    return bucket.name.replace(" Pod", "") if bucket else bucket_key


class InterestPromptView(discord.ui.LayoutView):
    """Ephemeral preference picker opened from the launcher's Format Preference button. A Components V2
    layout: prompt, the interest select, and the Save / Confirm row. A Flashback pick inserts the ranking
    line above a Rank Sets button; a Cube pick inserts the chosen-cubes line above a Choose Cubes button
    that reveals the server cube list. Short-lived and per-user, so it carries no persistent custom_ids."""

    def __init__(
        self, launcher_message_id: str, signal_date: date, current: list[str], ranking: list[str],
        cubes: list[str], slot_states: list[tuple[str, bool, bool]], event_id: str | None = None,
    ) -> None:
        super().__init__(timeout=300)
        self.launcher_message_id = launcher_message_id
        self.signal_date = signal_date
        self.values = fi.normalize(current)
        self.ranking = list(ranking)
        self.cubes = list(cubes)
        self.slot_states = slot_states
        self.event_id = event_id
        self._rebuild()

    def _rebuild(self) -> None:
        self.clear_items()
        container = discord.ui.Container(accent_colour=discord.Color.green())
        container.add_item(discord.ui.TextDisplay(MSG_INTEREST_PROMPT))
        self.select = _interest_menu(self.values)
        self.select.callback = self._on_select
        select_row = discord.ui.ActionRow()
        select_row.add_item(self.select)
        container.add_item(select_row)
        if fi.FLASHBACK in self.values:
            if self.ranking:
                ranking_text = MSG_YOUR_SETS_LINE.format(ranking=fi.ranking_display(self.ranking))
            else:
                ranking_text = MSG_RANK_EMPTY
            container.add_item(discord.ui.TextDisplay(ranking_text))
            rank = discord.ui.Button(label=RANK_BUTTON_LABEL, style=discord.ButtonStyle.primary,
                                     emoji=RANK_BUTTON_EMOJI)
            rank.callback = self._on_rank
            rank_row = discord.ui.ActionRow()
            rank_row.add_item(rank)
            container.add_item(rank_row)
            container.add_item(discord.ui.Separator())
        if fi.CUBE in self.values:
            self._add_cube_section(container)
        button_row = discord.ui.ActionRow()
        save = discord.ui.Button(label=SAVE_BUTTON_LABEL, style=discord.ButtonStyle.success,
                                 emoji=SAVE_BUTTON_EMOJI)
        save.callback = self._on_save
        button_row.add_item(save)
        for bucket_key, is_open, committed in self.slot_states:
            bucket = bucket_by_key(bucket_key)
            if bucket is None:
                continue
            button = discord.ui.Button(
                label=CONFIRM_SLOT_LABEL.format(name=_slot_short_name(bucket_key)),
                style=discord.ButtonStyle.success if is_open else discord.ButtonStyle.secondary,
                emoji=emojis.resolve(bucket.emoji), disabled=not is_open,
            )
            if is_open:
                button.callback = self._make_confirm_slot(bucket_key, committed)
            button_row.add_item(button)
        container.add_item(button_row)
        self.add_item(container)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        self.values = fi.normalize(self.select.values)
        self._rebuild()
        await interaction.response.edit_message(view=self)

    async def _on_rank(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(_RankModal(self))

    def _add_cube_section(self, container: discord.ui.Container) -> None:
        self.cube_select = _cube_menu(self.cubes)
        self.cube_select.callback = self._on_cube_select
        cube_row = discord.ui.ActionRow()
        cube_row.add_item(self.cube_select)
        container.add_item(cube_row)
        if self.cubes:
            container.add_item(discord.ui.TextDisplay(
                MSG_YOUR_CUBES_LINE.format(cubes=_cube_display(self.cubes))))
        container.add_item(discord.ui.Separator())

    async def _on_cube_select(self, interaction: discord.Interaction) -> None:
        picked = set(self.cube_select.values)
        self.cubes = [fmt.code for fmt in pod_format.custom_formats() if fmt.code in picked]
        self._rebuild()
        await interaction.response.edit_message(view=self)

    async def _persist(self, user: "discord.User | discord.Member") -> None:
        await asyncio.to_thread(
            pod_launch.set_launcher_interest_sync,
            self.launcher_message_id, str(user.id), getattr(user, "name", user.display_name),
            user.display_name, None, self.values, self.signal_date,
        )
        await asyncio.to_thread(pod_launch.set_flashback_ranking_sync, str(user.id), self.ranking)
        await asyncio.to_thread(pod_launch.set_cube_choices_sync, str(user.id), self.cubes)

    async def _finish(self, interaction: discord.Interaction, text: str) -> None:
        done = discord.ui.LayoutView(timeout=None)
        done.add_item(discord.ui.Container(
            discord.ui.TextDisplay(text), accent_colour=discord.Color.green(),
        ))
        await interaction.edit_original_response(view=done)
        self.stop()

    async def _dismiss(self, interaction: discord.Interaction) -> None:
        """Drop the picker without a closing message — for a Confirm whose grant card already carries
        the join confirmation and the saved preference, so the click ends with one message, not two."""
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            log.warning("could not delete the preference picker", exc_info=True)
        self.stop()

    async def _on_save(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await self._persist(interaction.user)
        if self.event_id is not None:
            await self._finish(interaction, self._saved_text())
            await self._resync_committed_pod(interaction.client)
            return
        await _rerender_poll(
            interaction.client, self.launcher_message_id, self.signal_date, interaction.channel)
        await self._finish(interaction, self._saved_text())

    def _saved_text(self) -> str:
        saved = MSG_INTEREST_SAVED.format(choice=fi.preference_display(self.values))
        if fi.FLASHBACK in self.values and self.ranking:
            saved = f"{saved}\n{MSG_YOUR_SETS_LINE.format(ranking=fi.ranking_display(self.ranking))}"
        if fi.CUBE in self.values and self.cubes:
            saved = f"{saved}\n{MSG_YOUR_CUBES_LINE.format(cubes=_cube_display(self.cubes))}"
        return saved

    async def _resync_committed_pod(self, bot: commands.Bot) -> None:
        """Run after the Saved ack so the click never waits on the edits: re-render the launcher board and
        this pod's card and reminder off the fresh roster. Called only from the reminder's Save."""
        await asyncio.gather(
            _rerender_poll(bot, self.launcher_message_id, self.signal_date),
            refresh_event_rsvp_surfaces(bot, self.event_id),
        )

    def _make_confirm_slot(self, bucket_key: str, committed: bool):
        async def callback(interaction: discord.Interaction) -> None:
            if committed:
                await self._on_confirm_committed(interaction, bucket_key)
            else:
                await self._on_confirm_slot(interaction, bucket_key)
        return callback

    async def _on_confirm_slot(self, interaction: discord.Interaction, bucket_key: str) -> None:
        """Save the preference and join the slot. The join feedback is the grant card or the full
        confirmation card out of `_apply_slot_join`, both of which carry the saved preference, so the
        picker itself closes silently instead of adding a second message."""
        await interaction.response.defer()
        await self._persist(interaction.user)
        launcher_message = await _fetch_launcher_message(interaction.channel, self.launcher_message_id)
        err = MSG_POLL_INACTIVE
        if launcher_message is not None:
            err, _ = await _apply_slot_join(
                interaction, launcher_message=launcher_message, signal_date=self.signal_date,
                bucket_key=bucket_key, action="join", notify_effect=True,
            )
        if err:
            await self._finish(interaction, err)
            return
        await self._dismiss(interaction)

    async def _on_confirm_committed(self, interaction: discord.Interaction, bucket_key: str) -> None:
        """A slot whose pod already committed joins through the pod's scheduled card, not the launcher
        poll signal, so the row lands on the live roster and the card, thread, and launcher re-render in
        step. Confirm always sets Yes; already-Yes stays Yes. `apply_card_rsvp` posts the join card and
        refreshes the board, so the picker deletes itself once done."""
        await self._persist(interaction.user)
        ref = await asyncio.to_thread(
            pod_launch.committed_slot_rsvp_ref_sync, self.signal_date, bucket_key, str(interaction.user.id),
        )
        if ref is None:
            await interaction.response.defer()
            await self._finish(interaction, MSG_SLOT_CLOSED)
            return
        card_message_id, _current = ref
        await apply_card_rsvp(interaction, card_message_id, RSVP_YES)
        await self._dismiss(interaction)


class _RankModal(discord.ui.Modal, title=RANK_MODAL_TITLE):
    codes = discord.ui.TextInput(
        label=RANK_MODAL_FIELD, placeholder=RANK_MODAL_PLACEHOLDER, required=False, max_length=100,
    )

    def __init__(self, view: "InterestPromptView") -> None:
        super().__init__()
        self.prompt = view
        self.codes.default = " ".join(view.ranking)
        self.remove_item(self.codes)
        self.add_item(discord.ui.TextDisplay(RANK_MODAL_EXPLAINER))
        self.add_item(self.codes)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        codes = pod_format_poll.normalize_write_ins(str(self.codes.value))
        self.prompt.ranking = codes[: fi.FLASHBACK_RANKING_MAX]
        self.prompt._rebuild()
        await interaction.response.edit_message(view=self.prompt)




def _interest_menu(selected: list[str]) -> discord.ui.Select:
    """A multi-select over the three interests, each an independent choice defaulted to the player's saved
    values. Picking several means "up for any of these"; picking latest and flashback both is the flexible
    crowd that fills either table."""
    chosen = set(fi.normalize(selected))
    options = [
        discord.SelectOption(
            label=fi.INTEREST_LABEL[fi.LATEST], value=fi.LATEST, emoji=fi.latest_emoji(),
            description=set_name_for(active_set_code()), default=fi.LATEST in chosen),
        discord.SelectOption(
            label=fi.INTEREST_LABEL[fi.FLASHBACK], value=fi.FLASHBACK, emoji=fi.flashback_emoji(),
            description=INTEREST_DESC_FLASHBACK, default=fi.FLASHBACK in chosen),
        discord.SelectOption(
            label=fi.INTEREST_LABEL[fi.CUBE], value=fi.CUBE, emoji=fi.interest_emoji(fi.CUBE),
            description=INTEREST_DESC_CUBE, default=fi.CUBE in chosen),
    ]
    return discord.ui.Select(
        placeholder=INTEREST_PLACEHOLDER, min_values=0, max_values=len(options), options=options,
    )


def _cube_menu(selected: list[str]) -> discord.ui.Select:
    """A multi-select over the server's registered cubes, defaulted to the player's saved choices."""
    chosen = set(selected)
    options = [
        discord.SelectOption(label=fmt.pick_label, value=fmt.code, emoji=fi.cube_emoji(), default=fmt.code in chosen)
        for fmt in pod_format.custom_formats()
    ]
    return discord.ui.Select(
        placeholder=CUBE_SELECT_PLACEHOLDER, min_values=0, max_values=len(options), options=options,
    )


def _cube_display(codes: list[str]) -> str:
    """The chosen cubes as bold underlined links to their CubeCobra pages, the cube glyph ahead of each,
    in registry order and spaced apart."""
    picked = set(codes)
    links = [
        f"{fi.cube_emoji()} [__**{fmt.link_text}**__]({fmt.url})"
        for fmt in pod_format.custom_formats() if fmt.code in picked
    ]
    return (NBSP * 3).join(links)


def _slot_toggle_button(bucket_key: str, closed: bool = False) -> discord.ui.Button:
    bucket = bucket_by_key(bucket_key)
    style = discord.ButtonStyle.secondary if closed else discord.ButtonStyle.success
    button = discord.ui.Button(
        label=bucket.name, style=style, disabled=closed,
        custom_id=f"pod_poll:{bucket_key}", emoji=emojis.resolve(bucket.emoji),
    )

    async def callback(interaction: discord.Interaction) -> None:
        await _handle_poll_click(interaction, bucket_key)

    button.callback = callback
    return button


def _slot_rsvp_button(bucket_key: str) -> discord.ui.Button:
    bucket = bucket_by_key(bucket_key)
    button = discord.ui.Button(
        label=bucket.name, style=discord.ButtonStyle.success,
        custom_id=f"pod_slot_rsvp:{bucket_key}", emoji=emojis.resolve(bucket.emoji),
    )

    async def callback(interaction: discord.Interaction) -> None:
        await _handle_slot_rsvp_click(interaction, bucket_key)

    button.callback = callback
    return button


async def _fetch_launcher_message(
    channel: "discord.abc.Messageable | None", message_id: str,
) -> "discord.Message | None":
    if channel is None:
        return None
    try:
        return await channel.fetch_message(int(message_id))
    except (discord.HTTPException, AttributeError):
        return None


async def _apply_slot_join(
    interaction: discord.Interaction, *, launcher_message: discord.Message, signal_date: date,
    bucket_key: str, action: str, notify_effect: bool = False,
) -> tuple[str | None, str | None]:
    """Join or toggle a launcher slot for the clicker, then run the shared fire, launcher re-render, role
    grant, announce, and nudge-refresh steps. Returns (error, notice): an error string when the slot is
    gone or closed, and the grant/welcome notice that was posted, so a caller with its own confirmation
    can skip it instead of doubling up. Shared by the launcher slot buttons (toggle) and the Format
    Preference Confirm buttons (join). `notify_effect` confirms the add or removal ephemerally when no
    grant notice already did."""
    message_id = str(launcher_message.id)
    result = await asyncio.to_thread(
        pod_launch.toggle_member_sync,
        message_id, bucket_key, str(interaction.user.id), interaction.user.display_name, action,
    )
    if result is None:
        return MSG_POLL_INACTIVE, None
    if result.closed:
        return MSG_SLOT_CLOSED, None
    fired = (
        result.joined
        and result.composition is not None
        and fi.slot_fires_latest(result.composition, settings.pod_signal_fire_threshold)
        and await asyncio.to_thread(pod_launch.claim_fire_sync, result.state.signal_id)
    )
    guild = getattr(launcher_message.channel, "guild", None) or interaction.guild
    slots = await asyncio.to_thread(pod_launch.launcher_snapshot_sync, message_id, signal_date)
    try:
        await launcher_message.edit(embed=build_poll_embed(slots, guild), view=PodPollView(slots, guild))
    except discord.HTTPException:
        log.warning(f"could not re-render launcher message {message_id}", exc_info=True)
    granted_role = None
    spec = None
    first_pod = False
    if result.joined and isinstance(interaction.user, discord.Member):
        first_pod = await grant_pod_drafters(interaction.user)
        granted_role = await _grant_slot_role(interaction.user, bucket_key)
        if granted_role is not None:
            spec = spec_named(granted_role.name)
    ping = slot_grant_ping(spec) if spec is not None else None
    card_lead = _slot_effect_lead(bucket_key, result.state.slot_time) if result.joined else None
    notice = await announce_pod_grant(
        interaction, first_pod=first_pod, granted_role=granted_role,
        welcome_role=granted_role, spec=spec, ping=ping, card_lead=card_lead,
    )
    if notify_effect and not notice:
        if result.joined and (result.changed or action == "join"):
            await send_join_confirmation_card(
                interaction, lead=_slot_effect_lead(bucket_key, result.state.slot_time),
                accent=discord.Color.green(),
            )
        elif result.changed:
            await interaction.followup.send(embed=_slot_removed_embed(bucket_key), ephemeral=True)
    if fired:
        asyncio.create_task(_launch_slot(interaction.client, result.state, message_id))
    elif result.changed:
        await refresh_slot_nudge(interaction.client, result.state.signal_id)
    return None, notice


async def _handle_poll_click(interaction: discord.Interaction, bucket_key: str) -> None:
    await interaction.response.defer()
    signal_date = await _launcher_signal_date(interaction.message)
    err, _ = await _apply_slot_join(
        interaction, launcher_message=interaction.message, signal_date=signal_date,
        bucket_key=bucket_key, action="toggle", notify_effect=True,
    )
    if err:
        await interaction.followup.send(err, ephemeral=True)


async def _handle_slot_rsvp_click(interaction: discord.Interaction, bucket_key: str) -> None:
    """A committed slot's button toggles the clicker on its scheduled card: Yes when they were out or
    Maybe, No when they already held Yes. The write and every follow-on run through the card's shared
    apply_card_rsvp, so the card, the launcher, and the native event re-render in step."""
    signal_date = await _launcher_signal_date(interaction.message)
    ref = await asyncio.to_thread(
        pod_launch.committed_slot_rsvp_ref_sync, signal_date, bucket_key, str(interaction.user.id),
    )
    if ref is None:
        await interaction.response.send_message(MSG_SLOT_CLOSED, ephemeral=True)
        return
    card_message_id, current = ref
    target = RSVP_NO if current == RSVP_YES else RSVP_YES
    launcher_message = interaction.message
    await apply_card_rsvp(interaction, card_message_id, target, refresh_launcher=False)
    guild = getattr(launcher_message.channel, "guild", None) or interaction.guild
    slots = await asyncio.to_thread(pod_launch.launcher_snapshot_sync, str(launcher_message.id), signal_date)
    try:
        await launcher_message.edit(embed=build_poll_embed(slots, guild), view=PodPollView(slots, guild))
    except discord.HTTPException:
        log.warning(f"could not re-render launcher message {launcher_message.id}", exc_info=True)


def _slot_effect_lead(bucket_key: str, slot_time: datetime | None) -> str:
    """The join confirmation as card text: folded into the grant card when a fresh role grant rides
    the same click, else the lead of the plain confirmation card."""
    bucket = bucket_by_key(bucket_key)
    name = bucket.name if bucket else bucket_key
    lead = f"### {MSG_SLOT_ADDED.format(name=name)}"
    if slot_time is not None:
        lead = f"{lead}\n{MSG_DRAFT_STARTS.format(unix=int(slot_time.timestamp()))}"
    return lead


def _slot_removed_embed(bucket_key: str) -> discord.Embed:
    """The bare red removal note, mirroring the scheduled card's No acknowledgement — the start time
    and the pod controls are moot once you're out. An add answers with the full confirmation card."""
    bucket = bucket_by_key(bucket_key)
    name = bucket.name if bucket else bucket_key
    return discord.Embed(title=MSG_SLOT_REMOVED.format(name=name), color=discord.Color.red())


def _fire_announcement(guild: discord.Guild | None, slot_time: datetime) -> str | None:
    """The @slot creation announcement carried on a fired slot's card, or None to post the card
    silently. Numberless, so it never goes stale as players join — the card's roster carries the count.
    Gated to a fire close to the draft time: an earlier fire posts silently and the underfill checks
    recruit the last seats near game time."""
    window = timedelta(hours=max(settings.pod_underfill_check_hours_tuple))
    if slot_time - datetime.now(timezone.utc) > window:
        return None
    role = find_role(guild, slot_role_name_for_event_time(slot_time) or "")
    if role is None:
        return None
    return SLOT_FIRE_PING.format(unix=int(slot_time.timestamp()), mention=role.mention)


async def _launch_slot(bot: commands.Bot, state, message_id: str) -> None:
    """A fired lazy slot graduates into a scheduled RSVP card: the signups carry over as Yes, and the
    card gathers any late signups right up to the lobby open. The slot then reflects the card as a
    jump-link on the next render and its own nudge is cleared — the card's underfill checks recruit
    from here. Falls back to reopening the slot if the card can't be posted."""
    set_code = active_set_code()
    slot_time = state.slot_time
    name = await asyncio.to_thread(pod_launch.ondemand_event_name_sync, set_code, slot_time)
    signups = await asyncio.to_thread(pod_launch.poll_yes_members_sync, state.signal_id)
    channel = _poll_channel(bot)
    event_id = None
    if isinstance(channel, discord.TextChannel):
        announcement = _fire_announcement(channel.guild, slot_time)
        event_id = await post_scheduled_card(
            bot, channel, set_code=set_code, event_time=slot_time, name=name, preseed_yes=signups,
            ping_role=False, content_override=announcement,
        )
    if event_id is None:
        await asyncio.to_thread(pod_launch.release_fire_sync, state.signal_id)
        log.warning(f"slot fire for {state.signal_id} failed to launch; reverted to open")
    else:
        await clear_slot_nudge(bot, state.signal_id)
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


async def _rerender_poll(
    bot: commands.Bot, message_id: str, signal_date: date,
    channel: "discord.abc.Messageable | None" = None,
) -> None:
    channel = channel or _poll_channel(bot)
    if channel is None:
        return
    guild = getattr(channel, "guild", None)
    slots = await asyncio.to_thread(pod_launch.launcher_snapshot_sync, message_id, signal_date)
    try:
        message = await channel.fetch_message(int(message_id))
        await message.edit(embed=build_poll_embed(slots, guild), view=PodPollView(slots, guild))
    except discord.HTTPException:
        log.warning(f"could not re-render launcher message {message_id}", exc_info=True)
