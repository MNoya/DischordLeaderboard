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
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot import emojis
from bot.commands import descriptions as desc
from bot.commands.messages import MSG_FIRST_POD_TIP_QUEUE, MSG_LOBBY_GATHERING, MSG_PLAYERS_JOINED
from bot.config import settings
from bot.discord_helpers import NBSP
from bot.services import pod_launch
from bot.services.pod_roles import find_role, grant_pod_drafters, grant_role
from bot.services.pod_schedule import POD_QUEUE_ROLE_NAME
from bot.services.pod_signals import QUEUE_BUCKET, SCHEDULE_TZ, STATUS_FIRED, should_fire, teardown_at
from bot.sets import active_set_code


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
QUEUE_ROLE_GRANTED = (
    "⚡ You're now on {role} and will be pinged when a queue opens or needs more players. "
    "Run `/roles` to manage your notifications."
)
QUEUE_NUDGE = "⚡ {count} players in queue! {mention}"
QUEUE_NUDGE_QUIET_MINUTES = 30
QUEUE_PLAYERS_EMPTY = "Players"


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
    ) -> None:
        super().__init__(timeout=None)
        names = names or []
        threshold = settings.pod_signal_fire_threshold
        container = discord.ui.Container(accent_colour=discord.Colour.green())
        self.add_item(container)
        container.add_item(discord.ui.TextDisplay(f"## {NBSP * 2}⚡ {role_mention or QUEUE_TITLE}"))
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
        container.add_item(discord.ui.TextDisplay(f"-# {QUEUE_CLOSES.format(window=window)}"))
        self.add_item(PodQueueActions())


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
            thread_mention=f"<#{thread_id}>" if thread_id else None,
        )
    else:
        view = PodQueueView(names=result.names, role_mention=mention)
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
    set_code = active_set_code()
    now = datetime.now(timezone.utc)
    name = await asyncio.to_thread(pod_launch.ondemand_event_name_sync, set_code, now)
    event_id = await pod_launch.launch_from_signal(
        bot, state.signal_id, set_code=set_code, event_time=now, name=name, open_now=True,
    )
    if event_id is None:
        await asyncio.to_thread(pod_launch.release_fire_sync, state.signal_id)
        log.warning(f"queue fire for {state.signal_id} failed to launch; reverted to open")
        return
    await _link_thread_on_card(bot, state.signal_id, event_id)


async def _link_thread_on_card(bot: commands.Bot, signal_id: str, event_id: str) -> None:
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
            thread_mention=f"<#{thread_id}>",
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


class PodQueue(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="draft", description=desc.POD_QUEUE)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_queue(self, interaction: discord.Interaction) -> None:
        mention = queue_role_mention(interaction.guild)
        await interaction.response.send_message(
            view=PodQueueView(names=[interaction.user.display_name], role_mention=mention),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        message = await interaction.original_response()

        guild_id = str(interaction.guild_id or "")
        signal_id = await asyncio.to_thread(
            pod_launch.create_queue_signal_sync,
            guild_id=guild_id, channel_id=str(interaction.channel_id), message_id=str(message.id),
            signal_date=datetime.now(SCHEDULE_TZ).date(), opened_by=str(interaction.user.id),
        )
        result = await asyncio.to_thread(
            pod_launch.toggle_member_sync,
            str(message.id), QUEUE_BUCKET, str(interaction.user.id), interaction.user.display_name, "join",
        )
        teardown = teardown_at(datetime.now(timezone.utc), settings.pod_queue_inactivity_minutes)
        pod_launch.arm_queue_teardown(interaction.client, signal_id, teardown)
        log.info(f"opened pod queue as message {message.id} (signal {signal_id})")
        if result is not None:
            fired = await _claim_fire_if_ready(result)
            await _post_join_followups(interaction, result, fired)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PodQueue(bot))
