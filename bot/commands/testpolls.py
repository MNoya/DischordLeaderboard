"""Owner-only `!test` triggers for the on-demand pod signup surfaces.

`poll` posts a live daily launcher in this channel; `draft` posts a live /draft queue; `rsvp` posts a
live scheduled RSVP card. All reuse the production builders and persistent views and register real
signals, so clicking the buttons drives the real add / remove / fire path (a fire creates the thread
and Draftmancer lobby for real, and `rsvp` creates its thread, event, and timed jobs at post time).
Set POD_SIGNAL_FIRE_THRESHOLD low to reach a fire on your own.

`launcher` drives the whole surface for real: it stages a scheduled pod at the day's last slot so that
slot reflects as a committed jump-link with its Yes roster, leaving the other slots as live lazy
signals, then posts the live launcher. Everything routes through the production paths, so the preview
can't drift from what players see.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from bot.commands.pod_queue import (
    QUEUE_CLOSED_MANUAL,
    PodQueueView,
    queue_inactivity_close_reason,
    queue_role_mention,
)
from bot.commands.pod_rsvp import (
    build_rsvp_embed,
    post_scheduled_card,
    purge_native_events,
    refresh_scheduled_card,
)
from bot.commands.pod_table import offer_second_table
from bot.commands.test_group import test_group
from bot.config import PRODUCTION_GUILD_ID
from bot.services import pod_launch
from bot.services.pod_draft_manager import set_event_pairing_mode
from bot.services.ping_roles import (
    PING_ROLES,
    QUEUE_GRANT_PING,
    build_grant_view,
    build_welcome_view,
    forget_welcome,
    slot_grant_ping,
    spec_named,
    strip_pod_roles,
)
from bot.services.pod_schedule import POD_QUEUE_ROLE_NAME
from bot.services.pod_signals import RSVP_YES, SCHEDULE_TZ, poll_buckets_for, slot_event_time
from bot.sets import active_set_code
from bot.tasks.pod_daily_poll import close_launcher_for_date, post_launcher


log = logging.getLogger(__name__)


async def _show_welcome_preview(interaction: discord.Interaction, role_name: str) -> None:
    guild = interaction.guild
    spec = spec_named(role_name)
    role = discord.utils.get(guild.roles, name=role_name) if guild is not None else None
    ping = QUEUE_GRANT_PING if role_name == POD_QUEUE_ROLE_NAME else slot_grant_ping(spec)
    preview_role = role or _StubRole(role_name)
    await interaction.response.send_message(
        view=build_welcome_view(guild, interaction.user.mention, role, ping=ping),
        allowed_mentions=discord.AllowedMentions.none(),
    )
    onboarding = build_welcome_view(guild, interaction.user.mention, None)
    linked = build_grant_view(preview_role, spec, ping=ping, arena_name="Tester#00000")
    unlinked = build_grant_view(preview_role, spec, ping=ping, arena_name=None)
    await _send_labeled_card(interaction, "**Welcome via onboarding (no slot role):**", onboarding)
    await _send_labeled_card(interaction, "**Returning, picks up a new slot (linked):**", linked)
    await _send_labeled_card(interaction, "**Returning, picks up a new slot (not linked):**", unlinked)


async def _send_labeled_card(
    interaction: discord.Interaction, label: str, card: discord.ui.LayoutView,
) -> None:
    """A Components V2 view can't ride with a `content` field, so the preview label posts as its own
    message ahead of the card."""
    await interaction.followup.send(label, allowed_mentions=discord.AllowedMentions.none())
    await interaction.followup.send(view=card, allowed_mentions=discord.AllowedMentions.none())


class _StubRole:
    """Stand-in for a slot role the test guild hasn't created, so the grant-card preview still renders
    with a name mention and the default accent."""

    def __init__(self, role_name: str) -> None:
        self.mention = f"@{role_name}"
        self.color = discord.Color.default()


class _WelcomePreviewButton(discord.ui.Button):
    def __init__(self, role_name: str) -> None:
        super().__init__(label=role_name, style=discord.ButtonStyle.secondary)
        self.role_name = role_name

    async def callback(self, interaction: discord.Interaction) -> None:
        await _show_welcome_preview(interaction, self.role_name)


class WelcomePreviewView(discord.ui.View):
    """Buttons that replay the first-pod welcome and role-grant a new drafter sees, addressed to
    whoever clicks — eyeball the copy without wiping pod history to trip first contact."""

    def __init__(self) -> None:
        super().__init__(timeout=None)
        for spec in PING_ROLES:
            if spec.auto_grant or spec.name == POD_QUEUE_ROLE_NAME:
                self.add_item(_WelcomePreviewButton(spec.name))


async def setup(bot: commands.Bot) -> None:
    @test_group.command(name="poll")
    @commands.is_owner()
    async def test_poll(ctx: commands.Context) -> None:
        """Owner-only. Post a live daily launcher whose slots are still ahead — today if one remains,
        otherwise tomorrow — so the buttons are clickable and drive real signals."""
        now = datetime.now(SCHEDULE_TZ)
        last_slot = slot_event_time(now.date(), poll_buckets_for(now.date())[-1].key)
        day = now.date() if last_slot is not None and last_slot > now else now.date() + timedelta(days=1)
        await post_launcher(ctx.bot, ctx.channel, day)

    @test_group.command(name="launcher")
    @commands.is_owner()
    async def test_launcher(ctx: commands.Context, fill: int = 5, close: str = "") -> None:
        """Owner-only. Drive the launcher end to end: stage a real scheduled pod at the day's last slot
        so it reflects as a committed jump-link, seed `fill` Yes RSVPs on it so the committed slot shows
        its roster, then post the live launcher for that day. The other slots are real lazy signals whose
        buttons drive the fire path; set POD_SIGNAL_FIRE_THRESHOLD low to graduate one yourself. Uses
        today when a slot is still ahead, otherwise tomorrow, so the staged pod is always in the future.
        Pass `close` as the third word to immediately retire it into the closed state (grey, no buttons,
        no role ping, committed slot shown as its roster) so that surface can be eyeballed."""
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("Run `!test launcher` in a server text channel — the pod thread is created there.")
            return
        now = datetime.now(SCHEDULE_TZ)
        today = now.date()
        last_today = slot_event_time(today, poll_buckets_for(today)[-1].key)
        target_day = today if last_today > now else today + timedelta(days=1)
        reflect = poll_buckets_for(target_day)[-1]
        slot_time = slot_event_time(target_day, reflect.key)
        set_code = active_set_code()
        name = await asyncio.to_thread(pod_launch.ondemand_event_name_sync, set_code, slot_time)
        event_id = await post_scheduled_card(
            ctx.bot, ctx.channel, set_code=set_code, event_time=slot_time, name=name, ping_role=False,
        )
        if event_id is None:
            await ctx.send("Could not stage the reflected scheduled pod. Check the logs.")
            return
        if fill > 0:
            await _seed_fake_yes(ctx.channel, event_id, slot_time, name, fill)
        await ctx.send(f"Staged **{name}** at {reflect.name}; posting the live launcher for that day.")
        await post_launcher(ctx.bot, ctx.channel, target_day)
        if close.lower() == "close":
            await close_launcher_for_date(ctx.bot, target_day)

    @test_group.command(name="reset")
    @commands.is_owner()
    async def test_reset(ctx: commands.Context) -> None:
        """Owner-only. Clear this guild's on-demand pod signals (poll / queue / scheduled) and the
        bot-native pods they staged so the `!test` surfaces start from a clean slate — every slot goes
        back to lazy — delete the bot's scheduled events off the Events calendar, and strip the
        auto-granted pod ping roles. Finalized played pods and sesh pods are kept, as is any live lobby."""
        if ctx.guild is None or ctx.guild.id == PRODUCTION_GUILD_ID:
            await ctx.send("`!test reset` is disabled on the production guild — run it in a test server.")
            return
        guild_id = str(ctx.guild.id)
        counts = await asyncio.to_thread(pod_launch.reset_ondemand_signals_sync, guild_id)
        purged = await purge_native_events(ctx.guild, ctx.bot.user.id) if ctx.guild else 0
        roles_removed = 0
        if isinstance(ctx.author, discord.Member):
            roles_removed = await strip_pod_roles(ctx.author)
            forget_welcome(ctx.author.id)
        await ctx.send(
            f"Cleared on-demand pod signals: {counts['signals']} signals, {counts['members']} members, "
            f"{counts['events']} bot-native pods. Removed {purged} scheduled events from the calendar and "
            f"stripped {roles_removed} of your pod roles."
        )

    @test_group.command(name="welcome")
    @commands.is_owner()
    async def test_welcome(ctx: commands.Context) -> None:
        """Owner-only. Post slot buttons that replay the first-pod welcome and role-grant a new drafter
        sees, addressed to whoever clicks."""
        if ctx.guild is None:
            await ctx.send("Run `!test welcome` in the server so the role pills resolve.")
            return
        await ctx.send(
            "Click a slot to see the first-pod welcome and role-grant a new drafter gets.",
            view=WelcomePreviewView(),
        )

    @test_group.command(name="rsvp")
    @commands.is_owner()
    async def test_rsvp(
        ctx: commands.Context, minutes: int = 60, fill: int = 0, team: str = "",
    ) -> None:
        """Owner-only. Post a live scheduled RSVP card in this channel via the production creation
        path — thread, event, native Discord event, and timed jobs included. `minutes` sets how far
        out the pod starts; `fill` seeds that many fake Yes signups so the '≥8' multi-pod notice can
        be previewed without eight real people. Pass `team` as the third word to flip the card into a
        Team Draft through the real persist-and-refresh path, so the ` - Team Draft` title marker can
        be eyeballed without a live lobby vote."""
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("Run `!test rsvp` in a server text channel — the thread is created there.")
            return
        event_time = datetime.now(SCHEDULE_TZ) + timedelta(minutes=minutes)
        set_code = active_set_code()
        name = await asyncio.to_thread(pod_launch.ondemand_event_name_sync, set_code, event_time)
        event_id = await post_scheduled_card(
            ctx.bot, ctx.channel, set_code=set_code, event_time=event_time, name=name,
        )
        if event_id is None:
            await ctx.send("Could not create the scheduled card. Check the logs.")
            return
        if fill > 0:
            await _seed_fake_yes(ctx.channel, event_id, event_time, name, fill)
        if team.lower() == "team":
            await set_event_pairing_mode(event_id, "team")
            await refresh_scheduled_card(ctx.bot, event_id)

    @test_group.command(name="secondtable")
    @commands.is_owner()
    async def test_secondtable(ctx: commands.Context, total: int = 14, seated: int = 8) -> None:
        """Owner-only. Post a scheduled card, seed `total` fake Yes, then simulate the first pod firing
        with `seated` of them locked in and offer a second table to the rest. No live draft needed —
        this drives the same offer path `_start_draft` fires. Needs `total - seated` at or above the
        table threshold to actually post an offer."""
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("Run `!test secondtable` in a server text channel.")
            return
        event_time = datetime.now(SCHEDULE_TZ) + timedelta(minutes=60)
        set_code = active_set_code()
        name = await asyncio.to_thread(pod_launch.ondemand_event_name_sync, set_code, event_time)
        event_id = await post_scheduled_card(
            ctx.bot, ctx.channel, set_code=set_code, event_time=event_time, name=name,
        )
        if event_id is None:
            await ctx.send("Could not create the scheduled card. Check the logs.")
            return
        names = [f"Tester {i + 1}" for i in range(total)]
        ref = await asyncio.to_thread(pod_launch.scheduled_card_ref_sync, event_id)
        for i, display in enumerate(names):
            await asyncio.to_thread(pod_launch.set_rsvp_sync, ref[2], f"filltest-{i}", display, RSVP_YES)
        await offer_second_table(ctx.bot, event_id, {f"filltest-{i}" for i in range(seated)})

    @test_group.command(name="draft")
    @commands.is_owner()
    async def test_draft(ctx: commands.Context) -> None:
        """Owner-only. Post a live /draft queue in this channel; the Join / Leave buttons drive the real signal."""
        today = datetime.now(SCHEDULE_TZ).date()
        view = PodQueueView(role_mention=queue_role_mention(ctx.guild))
        message = await ctx.send(view=view, allowed_mentions=discord.AllowedMentions(roles=True))
        guild_id = str(ctx.guild.id) if ctx.guild else ""
        await asyncio.to_thread(
            pod_launch.create_queue_signal_sync,
            guild_id=guild_id, channel_id=str(ctx.channel.id), message_id=str(message.id),
            signal_date=today, opened_by=str(ctx.author.id),
        )

    @test_group.command(name="queueclosed")
    @commands.is_owner()
    async def test_queueclosed(ctx: commands.Context) -> None:
        """Owner-only. Post both closed-queue cards to eyeball the copy: the inactivity timeout keeps its
        roster of idle players, the manual close shows none (only the last player can close it). Inert
        previews through the real builder, no signal."""
        mention = queue_role_mention(ctx.guild)
        set_code = active_set_code()
        opened_at = datetime.now(timezone.utc) - timedelta(hours=1)
        opened_by = str(ctx.author.id)
        await ctx.send(view=PodQueueView(
            names=["Tester One", "Tester Two", "Tester Three"], role_mention=mention,
            close_reason=queue_inactivity_close_reason(), set_code=set_code,
            opened_at=opened_at, opened_by=opened_by,
        ))
        await ctx.send(view=PodQueueView(
            role_mention=mention, close_reason=QUEUE_CLOSED_MANUAL,
            set_code=set_code, opened_at=opened_at, opened_by=opened_by,
        ))


async def _seed_fake_yes(
    channel: discord.TextChannel, event_id: str, event_time: datetime, name: str, count: int,
) -> None:
    """Record `count` fake Yes RSVPs against the just-posted card and re-render it, so the multi-pod
    notice can be eyeballed solo. Fake members never touch Discord; they only fill the roster."""
    ref = await asyncio.to_thread(pod_launch.scheduled_card_ref_sync, event_id)
    if ref is None:
        return
    message_id = ref[2]
    rosters = None
    for i in range(count):
        result = await asyncio.to_thread(
            pod_launch.set_rsvp_sync, message_id, f"filltest-{i}", f"Tester {i + 1}", RSVP_YES)
        if result is not None:
            rosters = result.rosters
    if rosters is None:
        return
    try:
        card = await channel.fetch_message(int(message_id))
        await card.edit(embed=build_rsvp_embed(name, event_time, rosters))
    except discord.HTTPException:
        log.warning(f"could not re-render the fake-fill card {message_id}", exc_info=True)
