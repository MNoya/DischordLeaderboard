"""Dynamic pod queue (Feature B) — the present-tense counterpart to the daily poll.

`/pod-queue` posts a live "who's around right now" queue. The instant the fire threshold is reached
the bot creates the thread + Draftmancer lobby immediately (open_now). Staleness follows Amelas/
DraftBot: no per-entry expiry, one inactivity window that resets on each join.

The queue message is one Components V2 card and the single interactive surface: V2 text mentions
notify (unlike embeds), so the role ping lives inside the card instead of a bare content line above
it. The persistent view re-attaches on restart, and closure is enforced in the DB, so a stale
button goes inert on click and never becomes a dead duplicate card.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot import emojis
from bot.commands import descriptions as desc
from bot.commands.messages import MSG_FIRST_POD_TIP_QUEUE, MSG_LOBBY_GATHERING, MSG_PLAYERS_JOINED
from bot.commands.pod_rsvp import parse_new_time, post_scheduled_card
from bot.config import settings
from bot.discord_helpers import NBSP
from bot.services import pod_launch
from bot.services.pod_draft_manager import (
    set_event_pairing_mode,
    set_event_pick_timer,
    set_event_seating_mode,
)
from bot.services.pod_format import PEASANT_CODE, PEASANT_CUBE_ID, PEASANT_LABEL
from bot.services.pod_format_select import WRITE_IN_VALUE, set_select_option, write_in_option
from bot.services.pod_pairing_select import SELECT_PLACEHOLDER as PAIRING_PLACEHOLDER
from bot.services.pod_pairing_select import pairing_options
from bot.services.pod_roles import find_role, grant_pod_drafters, grant_role
from bot.services.pod_schedule import POD_QUEUE_ROLE_NAME
from bot.services.pod_seating_select import SEATING_SELECT_PLACEHOLDER, seating_mode_options
from bot.services.pod_settings_view import TIMER_MAX, TIMER_MIN
from bot.services.pod_signals import (
    KIND_QUEUE,
    QUEUE_BUCKET,
    SCHEDULE_TZ,
    STATUS_FIRED,
    bucket_by_key,
    should_fire,
    slot_event_time,
    teardown_at,
)
from bot.sets import active_set_code, recent_released_sets, set_name_for


log = logging.getLogger(__name__)

QUEUE_TITLE = "Pod Draft Queue"
QUEUE_FIRED = "Join {thread}"
QUEUE_CREATING = "Creating the lobby..."
QUEUE_CLOSED = "Queue closed after {window} of inactivity."
QUEUE_INSTRUCTIONS = (
    "- Hit **Join** if you can draft right now. **Leave** when you no longer can.\n"
    f"- {MSG_LOBBY_GATHERING}"
)
QUEUE_CLOSES = "Queue closes after {window} of inactivity."
QUEUE_OPENED = "Queue opened {when}"
QUEUE_ROLE_GRANTED = (
    "⚡ You're now on {role} and will be pinged when a queue opens or needs more players. "
    "Run `/roles` to manage your notifications."
)
QUEUE_NUDGE = "⚡ {count} players in queue! {mention}"
QUEUE_NUDGE_QUIET_MINUTES = 30
QUEUE_PLAYERS_EMPTY = "Players"

JOINABLE_WINDOW = timedelta(hours=6)
MAX_JOINABLE_LINES = 3
SET_PLACEHOLDER = "Choose the set"
WHEN_PLACEHOLDER = "When to draft"
LAUNCHER_PROMPT = "Set your options below, then open a queue now or schedule a pod for later."
LAUNCHER_JOIN_HINT = "Join an existing pod instead of starting a new one:"
LAUNCHER_QUEUE_LINE = "Open queue with {count} waiting: {url}"
LAUNCHER_SLOT_LINE = "Scheduled for {when} with {count} in: {url}"
LAUNCHER_MORE_LINE = "And {count} more."
LAUNCHER_SCHEDULED = "Scheduled for {when}. RSVP card posted: {url}"
LAUNCHER_SCHEDULE_FAILED = "The scheduled pod card could not be posted. Try again."
LAUNCHER_SCHEDULE_NO_CHANNEL = "The pod coordination channel could not be reached."
WHEN_MODAL_BAD_TIME = "Enter a future time like Today 7pm, tomorrow 8:30pm, Fri 9pm, or +3h."


class PodQueueActions(discord.ui.ActionRow):
    @discord.ui.button(label="Join", emoji="⚡", style=discord.ButtonStyle.success, custom_id="pod_queue:join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await _handle_click(interaction, "join")

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.danger, custom_id="pod_queue:leave")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await _handle_click(interaction, "leave")


class PodQueueView(discord.ui.LayoutView):
    """The whole queue message: one Components V2 container plus the Join / Leave row. Persistent —
    the buttons carry static custom_ids and the no-arg form is registered at startup."""

    def __init__(
        self, names: list[str] | None = None, role_mention: str | None = None,
        fired: bool = False, thread_mention: str | None = None, closed: bool = False,
        set_code: str | None = None, opened_at: datetime | None = None,
    ) -> None:
        super().__init__(timeout=None)
        names = names or []
        threshold = settings.pod_signal_fire_threshold
        container = discord.ui.Container(accent_colour=discord.Colour.green())
        self.add_item(container)
        container.add_item(discord.ui.TextDisplay(f"## {NBSP * 2}⚡ {_queue_title(role_mention, set_code)}"))
        if closed:
            window = inactivity_window_text(settings.pod_queue_inactivity_minutes)
            container.add_item(discord.ui.TextDisplay(QUEUE_CLOSED.format(window=window)))
            return
        roster_name = MSG_PLAYERS_JOINED.format(count=len(names)) if names else QUEUE_PLAYERS_EMPTY
        roster = "\n".join(f"> {name}" for name in names) if names else "-"
        if fired:
            body = QUEUE_FIRED.format(thread=thread_mention) if thread_mention else QUEUE_CREATING
            container.add_item(discord.ui.TextDisplay(f"**{roster_name}**\n{roster}"))
            container.add_item(discord.ui.TextDisplay(body))
            return
        instructions = QUEUE_INSTRUCTIONS.format(threshold=emojis.mana_number(threshold))
        container.add_item(discord.ui.TextDisplay(instructions))
        container.add_item(discord.ui.TextDisplay(f"**{roster_name}**\n{roster}"))
        window = inactivity_window_text(settings.pod_queue_inactivity_minutes)
        if opened_at is not None:
            opened = QUEUE_OPENED.format(when=f"<t:{int(opened_at.timestamp())}:R>")
            container.add_item(discord.ui.TextDisplay(f"-# {opened}"))
        container.add_item(discord.ui.TextDisplay(f"-# {QUEUE_CLOSES.format(window=window)}"))
        self.add_item(PodQueueActions())


def _queue_title(role_mention: str | None, set_code: str | None) -> str:
    """`SET Pod Draft Queue {emoji}` so a non-default queue is legible before anyone joins. The queue
    role is itself named "Pod Draft Queue", so its mention doubles as the label and the ping."""
    code = (set_code or active_set_code()).upper()
    emoji = emojis.set_symbol(code)
    suffix = f" {emoji}" if emoji else ""
    return f"{code} {role_mention or QUEUE_TITLE}{suffix}"


def inactivity_window_text(minutes: int) -> str:
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    return f"{minutes} minutes"


def queue_role_mention(guild: discord.Guild | None) -> str | None:
    role = find_role(guild, POD_QUEUE_ROLE_NAME)
    return role.mention if role else None


async def _handle_click(interaction: discord.Interaction, action: str) -> None:
    message_id = str(interaction.message.id)
    result = await asyncio.to_thread(
        pod_launch.toggle_member_sync,
        message_id, QUEUE_BUCKET, str(interaction.user.id), interaction.user.display_name, action,
    )
    if result is None:
        await interaction.response.send_message("This queue is no longer active.", ephemeral=True)
        return
    if result.closed:
        await interaction.response.send_message("This queue already closed.", ephemeral=True)
        return
    if not result.changed:
        note = "You're already in the queue." if action == "join" else "You're not in the queue."
        await interaction.response.send_message(note, ephemeral=True)
        return

    if action == "join":
        teardown = teardown_at(datetime.now(timezone.utc), settings.pod_queue_inactivity_minutes)
        pod_launch.arm_queue_teardown(interaction.client, result.state.signal_id, teardown)

    fired = await _claim_fire_if_ready(result)
    mention = queue_role_mention(interaction.guild)
    if not fired and result.state.status == STATUS_FIRED:
        thread_id = None
        if result.state.event_id is not None:
            thread_id = await asyncio.to_thread(pod_launch.event_thread_id_sync, result.state.event_id)
        view = PodQueueView(
            names=result.names, role_mention=mention, fired=True,
            thread_mention=f"<#{thread_id}>" if thread_id else None, set_code=result.state.set_code,
        )
    else:
        view = PodQueueView(
            names=result.names, role_mention=mention, set_code=result.state.set_code,
            opened_at=result.state.created_at,
        )
    await interaction.response.edit_message(view=view)
    await _post_join_followups(interaction, result, fired)


async def _claim_fire_if_ready(result) -> bool:
    if not (result.joined and should_fire(result.state.count, settings.pod_signal_fire_threshold)):
        return False
    return await asyncio.to_thread(pod_launch.claim_fire_sync, result.state.signal_id)


async def _post_join_followups(interaction: discord.Interaction, result, fired: bool) -> None:
    if result.first_contact:
        tip = MSG_FIRST_POD_TIP_QUEUE.format(threshold=settings.pod_signal_fire_threshold)
        await interaction.followup.send(tip, ephemeral=True)
    if result.joined:
        granted_role = await _grant_queue_role(interaction)
        if granted_role is not None:
            await interaction.followup.send(
                QUEUE_ROLE_GRANTED.format(role=granted_role.mention),
                ephemeral=True, allowed_mentions=discord.AllowedMentions.none(),
            )
        if not fired:
            await _maybe_nudge(interaction, result.state)
    if fired:
        asyncio.create_task(_launch_pod(interaction.client, result.state))


async def _launch_pod(bot: commands.Bot, state) -> None:
    presets = await asyncio.to_thread(pod_launch.queue_presets_sync, state.signal_id)
    set_code = presets.set_code or active_set_code()
    now = datetime.now(timezone.utc)
    name = await asyncio.to_thread(pod_launch.ondemand_event_name_sync, set_code, now)
    event_id = await pod_launch.launch_from_signal(
        bot, state.signal_id, set_code=set_code, event_time=now, name=name, open_now=True,
    )
    if event_id is None:
        await asyncio.to_thread(pod_launch.release_fire_sync, state.signal_id)
        log.warning(f"queue fire for {state.signal_id} failed to launch; reverted to open")
        return
    await _apply_queue_presets(event_id, presets)
    await _link_thread_on_card(bot, state.signal_id, event_id, set_code)


async def _link_thread_on_card(bot: commands.Bot, signal_id: str, event_id: str, set_code: str) -> None:
    """The fired card's only update: same roster, the thread link added, buttons gone. The card is
    left untouched between the fire and the thread existing."""
    thread_id = await asyncio.to_thread(pod_launch.event_thread_id_sync, event_id)
    ref = await asyncio.to_thread(pod_launch.signal_message_ref_sync, signal_id)
    if thread_id is None or ref is None:
        return
    channel_id, message_id = ref
    channel = bot.get_channel(int(channel_id))
    guild = getattr(channel, "guild", None)
    if channel is None or guild is None:
        return
    roster = await asyncio.to_thread(pod_launch.roster_for_event_sync, event_id)
    names = [name for _, name in roster]
    try:
        message = await channel.fetch_message(int(message_id))
        view = PodQueueView(
            names=names, role_mention=queue_role_mention(guild), fired=True,
            thread_mention=f"<#{thread_id}>", set_code=set_code,
        )
        await message.edit(view=view)
    except discord.HTTPException:
        log.warning(f"could not link pod thread on queue message {message_id}", exc_info=True)


async def _maybe_nudge(interaction: discord.Interaction, state) -> None:
    """One ping when the queue reaches one short of firing, DraftBot-style: only once per queue and
    only after the quiet window, so a queue that fills quickly never pings at all."""
    if state.count != settings.pod_signal_fire_threshold - 1:
        return
    claimed = await asyncio.to_thread(
        pod_launch.claim_nudge_sync, state.signal_id, QUEUE_NUDGE_QUIET_MINUTES,
    )
    if not claimed:
        return
    mention = queue_role_mention(interaction.guild)
    if mention is None or interaction.channel is None:
        return
    try:
        await interaction.channel.send(
            QUEUE_NUDGE.format(count=state.count, mention=mention),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
    except discord.HTTPException:
        log.warning("queue nudge send failed", exc_info=True)


async def _grant_queue_role(interaction: discord.Interaction) -> discord.Role | None:
    """Subscribe a joiner to future queue pings. Returns the role only on a fresh grant, so the
    caller's ephemeral confirmation fires once per user ever; leaving never removes the role."""
    member = interaction.user
    if not isinstance(member, discord.Member):
        return None
    await grant_pod_drafters(member)
    role = find_role(interaction.guild, POD_QUEUE_ROLE_NAME)
    if role is None:
        return None
    granted = await grant_role(member, role)
    return role if granted else None


async def _apply_queue_presets(event_id: str, presets) -> None:
    """Apply the pairing / seating / pick-timer chosen in the launcher once the pod fires. Runs after
    the lobby opens but before anyone starts the draft, so the live session picks them up. The set is
    already baked into the event at creation, so it isn't re-applied here."""
    if presets.pairing_mode is not None:
        await set_event_pairing_mode(event_id, presets.pairing_mode)
    if presets.seating_mode is not None:
        await set_event_seating_mode(event_id, presets.seating_mode)
    if presets.pick_timer is not None:
        await set_event_pick_timer(event_id, presets.pick_timer)


class DraftLauncherView(discord.ui.View):
    """Ephemeral pre-draft config for /draft: set, pairings, and seats as dropdowns plus a pick-timer
    button, all on one panel, then Start Draft. Rebuilds itself on each choice so every dropdown
    shows the current selection, like the lobby Settings panel. The chosen set rides into the pod
    name and Draftmancer session when the queue fires; the default is the active set."""

    def __init__(self, *, set_code: str | None = None, pairing_mode: str | None = None,
                 seating_mode: str | None = None, pick_timer: int | None = None,
                 scheduled_time: datetime | None = None, scheduled_ping: bool = False) -> None:
        super().__init__(timeout=300)
        self.set_code = set_code
        self.pairing_mode = pairing_mode
        self.seating_mode = seating_mode
        self.pick_timer = pick_timer
        self.scheduled_time = scheduled_time
        self.scheduled_ping = scheduled_ping
        self.add_item(_LauncherSetSelect(set_code, row=0))
        self.add_item(_LauncherWhenSelect(scheduled_time, row=1))
        self.add_item(_LauncherPairingSelect(pairing_mode, row=2))
        self.add_item(_LauncherSeatingSelect(seating_mode, row=3))
        self.add_item(_LauncherTimerButton(pick_timer, row=4))
        self.add_item(_LauncherStartButton(scheduled=scheduled_time is not None, row=4))

    async def rerender(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(view=DraftLauncherView(
            set_code=self.set_code, pairing_mode=self.pairing_mode, seating_mode=self.seating_mode,
            pick_timer=self.pick_timer, scheduled_time=self.scheduled_time, scheduled_ping=self.scheduled_ping,
        ))


def _set_options(current: str | None) -> list[discord.SelectOption]:
    """The set dropdown: the active set (default), Peasant Cube, the most recent released sets, then a
    write-in for any other code — each carrying its keyrune emoji when one is loaded. Peasant Cube is
    always offered right under the latest set. Unreleased upcoming sets are left out; they have no card
    pool to draft. A written-in current outside the known list shows as its own defaulted option so it
    survives re-render."""
    active = active_set_code()
    active_upper = active.upper()
    chosen = (current or active).upper()
    recent = [seed.code for seed in recent_released_sets()]
    known = {active_upper, PEASANT_CODE} | {code.upper() for code in recent}

    options: list[discord.SelectOption] = [write_in_option("Set")]
    if chosen not in known:
        options.append(set_select_option(
            chosen, label=f"Set: {chosen}", description=set_name_for(chosen), default=True))
    options.append(set_select_option(
        active, label=f"Set: {active}", description="The latest set", default=(chosen == active_upper)))
    options.append(discord.SelectOption(
        label=f"Set: {PEASANT_LABEL}", value=PEASANT_CODE, description=f"CubeCobra: {PEASANT_CUBE_ID}",
        emoji=emojis.get_emoji("cube"), default=(chosen == PEASANT_CODE)))
    for code in recent:
        options.append(set_select_option(
            code, label=f"Set: {code}", description=set_name_for(code), default=(chosen == code)))
    return options


class _LauncherSetSelect(discord.ui.Select):
    def __init__(self, current: str | None, row: int | None = None) -> None:
        super().__init__(placeholder=SET_PLACEHOLDER, options=_set_options(current),
                         min_values=1, max_values=1, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values[0] == WRITE_IN_VALUE:
            await interaction.response.send_modal(_LauncherSetModal(self.view))
            return
        self.view.set_code = self.values[0]
        await self.view.rerender(interaction)


class _LauncherSetModal(discord.ui.Modal, title="Draft a different set"):
    code = discord.ui.TextInput(label="Set code", placeholder="e.g. FIN", min_length=2, max_length=8)

    def __init__(self, view: "DraftLauncherView") -> None:
        super().__init__()
        self.launcher = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.launcher.set_code = self.code.value.strip().upper()
        await self.launcher.rerender(interaction)


def _preset_slot_time(bucket_key: str, now: datetime) -> datetime | None:
    """The next occurrence of an Early / Late slot: today's if still ahead, otherwise tomorrow's."""
    today = now.astimezone(SCHEDULE_TZ).date()
    slot = slot_event_time(today, bucket_key)
    if slot is None:
        return None
    if slot <= now:
        slot = slot_event_time(today + timedelta(days=1), bucket_key)
    return slot


def _when_day_label(when: datetime, now: datetime) -> str:
    local = when.astimezone(SCHEDULE_TZ)
    today = now.astimezone(SCHEDULE_TZ).date()
    if local.date() == today:
        return "Today"
    if local.date() == today + timedelta(days=1):
        return "Tomorrow"
    return local.strftime("%b %-d")


def _when_clock(when: datetime) -> str:
    return when.astimezone(SCHEDULE_TZ).strftime("%-I:%M %p ET")


def _when_options(scheduled_time: datetime | None, now: datetime) -> list[discord.SelectOption]:
    """Right now (default) plus the two named slots at their next occurrence, then a custom write-in.
    A custom time shows as its own defaulted option; the presets ping their slot role, custom does not."""
    early = _preset_slot_time("EARLY", now)
    late = _preset_slot_time("LATE", now)
    options = [discord.SelectOption(
        label="When: Right now", value="now", emoji="⚡", description="Open a live queue now",
        default=(scheduled_time is None))]
    for key, slot in (("EARLY", early), ("LATE", late)):
        bucket = bucket_by_key(key)
        options.append(discord.SelectOption(
            label=f"When: {bucket.name}", value=key, emoji=bucket.emoji,
            description=f"{_when_day_label(slot, now)} {_when_clock(slot)}",
            default=(scheduled_time is not None and scheduled_time == slot)))
    is_custom = scheduled_time is not None and scheduled_time not in (early, late)
    if is_custom:
        label = f"When: {_when_day_label(scheduled_time, now)} {_when_clock(scheduled_time)}"
        description = "Change the custom time"
    else:
        label = "When: Schedule for later…"
        description = "Pick a custom date and time"
    options.append(discord.SelectOption(
        label=label, value=WRITE_IN_VALUE, description=description, default=is_custom))
    return options


class _LauncherWhenSelect(discord.ui.Select):
    def __init__(self, current: datetime | None, row: int | None = None) -> None:
        super().__init__(placeholder=WHEN_PLACEHOLDER, min_values=1, max_values=1, row=row,
                         options=_when_options(current, datetime.now(timezone.utc)))

    async def callback(self, interaction: discord.Interaction) -> None:
        value = self.values[0]
        if value == WRITE_IN_VALUE:
            await interaction.response.send_modal(_LauncherWhenModal(self.view))
            return
        if value == "now":
            self.view.scheduled_time = None
            self.view.scheduled_ping = False
        else:
            self.view.scheduled_time = _preset_slot_time(value, datetime.now(timezone.utc))
            self.view.scheduled_ping = True
        await self.view.rerender(interaction)


class _LauncherWhenModal(discord.ui.Modal, title="Schedule a Pod"):
    when = discord.ui.TextInput(
        label="When (ET)", placeholder="Today 7pm, tomorrow 8:30pm, Fri 9pm, +3h", min_length=2, max_length=32)

    def __init__(self, view: "DraftLauncherView") -> None:
        super().__init__()
        self.launcher = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        now = datetime.now(timezone.utc)
        parsed = parse_new_time(self.when.value.strip(), now, now)
        if parsed is None:
            await self.launcher.rerender(interaction)
            await interaction.followup.send(f"⚠️ {WHEN_MODAL_BAD_TIME}", ephemeral=True)
            return
        self.launcher.scheduled_time = parsed
        self.launcher.scheduled_ping = False
        await self.launcher.rerender(interaction)


class _LauncherPairingSelect(discord.ui.Select):
    def __init__(self, current: str | None, row: int | None = None) -> None:
        super().__init__(placeholder=PAIRING_PLACEHOLDER, options=pairing_options(current),
                         min_values=1, max_values=1, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.pairing_mode = self.values[0]
        await self.view.rerender(interaction)


class _LauncherSeatingSelect(discord.ui.Select):
    def __init__(self, current: str | None, row: int | None = None) -> None:
        super().__init__(placeholder=SEATING_SELECT_PLACEHOLDER, options=seating_mode_options(current),
                         min_values=1, max_values=1, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.seating_mode = self.values[0]
        await self.view.rerender(interaction)


class _LauncherTimerButton(discord.ui.Button):
    def __init__(self, current: int | None, row: int | None = None) -> None:
        label = f"Pick Timer: {current}s" if current is not None else "Pick Timer"
        super().__init__(label=label, emoji="⏱️", style=discord.ButtonStyle.grey, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(_LauncherTimerModal(self.view))


class _LauncherTimerModal(discord.ui.Modal, title="Pick timer"):
    seconds = discord.ui.TextInput(label="Seconds per pick", placeholder="e.g. 60", min_length=1, max_length=3)

    def __init__(self, view: DraftLauncherView) -> None:
        super().__init__()
        self.launcher = view
        if view.pick_timer is not None:
            self.seconds.default = str(view.pick_timer)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.seconds.value.strip()
        if not raw.isdigit() or not (TIMER_MIN <= int(raw) <= TIMER_MAX):
            await interaction.response.send_message(
                f"⚠️ Enter a whole number of seconds between {TIMER_MIN} and {TIMER_MAX}.", ephemeral=True,
            )
            return
        self.launcher.pick_timer = int(raw)
        await self.launcher.rerender(interaction)


class _LauncherStartButton(discord.ui.Button):
    def __init__(self, scheduled: bool = False, row: int | None = None) -> None:
        label = "Confirm Draft" if scheduled else "Open Queue"
        emoji = "🗓️" if scheduled else "⚡"
        super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.success, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: DraftLauncherView = self.view
        if view.scheduled_time is not None:
            await _schedule_pod(
                interaction, view.set_code, view.pairing_mode, view.seating_mode, view.pick_timer,
                view.scheduled_time, view.scheduled_ping,
            )
            return
        await _open_queue(
            interaction, view.set_code, view.pairing_mode, view.seating_mode, view.pick_timer,
        )


async def _open_queue(
    interaction: discord.Interaction, set_code: str | None, pairing_mode: str | None,
    seating_mode: str | None, pick_timer: int | None,
) -> None:
    """Post the public queue card from the launcher and wire its signal, carrying the chosen set and
    presets. Dismisses the ephemeral launcher and runs the opener's own join through the normal path."""
    await interaction.response.defer()
    mention = queue_role_mention(interaction.guild)
    message = await interaction.channel.send(
        view=PodQueueView(
            names=[interaction.user.display_name], role_mention=mention, set_code=set_code,
            opened_at=datetime.now(timezone.utc),
        ),
        allowed_mentions=discord.AllowedMentions(roles=True),
    )
    signal_id = await asyncio.to_thread(
        pod_launch.create_queue_signal_sync,
        guild_id=str(interaction.guild_id or ""), channel_id=str(interaction.channel_id),
        message_id=str(message.id), signal_date=datetime.now(SCHEDULE_TZ).date(),
        opened_by=str(interaction.user.id),
        set_code=set_code, pairing_mode=pairing_mode, seating_mode=seating_mode, pick_timer=pick_timer,
    )
    result = await asyncio.to_thread(
        pod_launch.toggle_member_sync,
        str(message.id), QUEUE_BUCKET, str(interaction.user.id), interaction.user.display_name, "join",
    )
    teardown = teardown_at(datetime.now(timezone.utc), settings.pod_queue_inactivity_minutes)
    pod_launch.arm_queue_teardown(interaction.client, signal_id, teardown)
    log.info(f"opened pod queue as message {message.id} (signal {signal_id})")
    await interaction.delete_original_response()
    if result is not None:
        fired = await _claim_fire_if_ready(result)
        await _post_join_followups(interaction, result, fired)


async def _schedule_pod(
    interaction: discord.Interaction, set_code: str | None, pairing_mode: str | None,
    seating_mode: str | None, pick_timer: int | None, when: datetime, ping: bool,
) -> None:
    """Post a scheduled RSVP card in the coordination channel for a future pod, carrying the launcher's
    set and presets, with the opener seeded as the first Yes. Custom times skip the slot-role ping."""
    await interaction.response.defer()
    channel = interaction.client.get_channel(settings.pod_draft_channel_id)
    if not isinstance(channel, discord.TextChannel):
        await interaction.edit_original_response(content=LAUNCHER_SCHEDULE_NO_CHANNEL, view=None)
        return
    resolved_set = (set_code or active_set_code()).upper()
    name = await asyncio.to_thread(pod_launch.ondemand_event_name_sync, resolved_set, when)
    opener = [(str(interaction.user.id), interaction.user.display_name)]
    event_id = await post_scheduled_card(
        interaction.client, channel, set_code=resolved_set, event_time=when, name=name,
        preseed_yes=opener, ping_role=ping,
        pairing_mode=pairing_mode, seating_mode=seating_mode, pick_timer=pick_timer,
    )
    if event_id is None:
        await interaction.edit_original_response(content=LAUNCHER_SCHEDULE_FAILED, view=None)
        return
    ref = await asyncio.to_thread(pod_launch.scheduled_card_ref_sync, event_id)
    url = f"https://discord.com/channels/{interaction.guild_id}/{ref[1]}/{ref[2]}" if ref else channel.mention
    when_tag = f"<t:{int(when.timestamp())}:F>"
    log.info(f"scheduled pod {name} for {when.isoformat()} (event {event_id})")
    await interaction.edit_original_response(content=LAUNCHER_SCHEDULED.format(when=when_tag, url=url), view=None)


def _launcher_content(guild: discord.Guild | None, joinable: list) -> str:
    if guild is None or not joinable:
        return LAUNCHER_PROMPT
    lines = []
    for signal in joinable[:MAX_JOINABLE_LINES]:
        url = f"https://discord.com/channels/{guild.id}/{signal.channel_id}/{signal.message_id}"
        if signal.kind == KIND_QUEUE:
            lines.append(LAUNCHER_QUEUE_LINE.format(count=signal.count, url=url))
        else:
            when = f"<t:{int(signal.slot_time.timestamp())}:t>" if signal.slot_time else "later today"
            lines.append(LAUNCHER_SLOT_LINE.format(when=when, count=signal.count, url=url))
    if len(joinable) > MAX_JOINABLE_LINES:
        lines.append(LAUNCHER_MORE_LINE.format(count=len(joinable) - MAX_JOINABLE_LINES))
    return f"{LAUNCHER_JOIN_HINT}\n" + "\n".join(lines) + f"\n\n{LAUNCHER_PROMPT}"


class PodQueue(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="draft", description=desc.POD_QUEUE)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_queue(self, interaction: discord.Interaction) -> None:
        joinable = await asyncio.to_thread(
            pod_launch.joinable_signals_sync, str(interaction.guild_id or ""),
            now=datetime.now(timezone.utc), within=JOINABLE_WINDOW,
        )
        await interaction.response.send_message(
            content=_launcher_content(interaction.guild, joinable), view=DraftLauncherView(),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PodQueue(bot))
