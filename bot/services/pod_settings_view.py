"""Combined pod-draft lobby Settings panel: draft format + pairing mode + seats in one ephemeral view.

Picking an option applies it, re-renders the panel (all dropdowns kept, the changed one defaulted),
and posts a public thread notice — so the confirmation everyone sees lives in the channel, not in the
private ephemeral. The Seat Order button is contextual to Manual seats + a live lobby.
"""
from __future__ import annotations

from typing import Awaitable, Callable

import discord
from discord import ui

from bot.services.pod_format import format_change_message, settings_change_message, settings_notice_marker
from bot.services.pod_notices import send_settings_notice
from bot.services.pod_drafts import is_championship
from bot.services.pod_registration_embed import update_registered_embed
from bot.services.pod_format_select import SELECT_PLACEHOLDER as FORMAT_PLACEHOLDER
from bot.services.pod_format_select import WRITE_IN_VALUE as FORMAT_WRITE_IN_VALUE
from bot.services.pod_format_select import FormatWriteInModal, format_options
from bot.services.pod_pairing_select import SELECT_PLACEHOLDER as PAIRING_PLACEHOLDER
from bot.services.pod_pairing_select import pairing_change_message, pairing_options
from bot.services.pod_seating_select import (
    SEATING_SELECT_PLACEHOLDER,
    SeatedNotify,
    SeatingApply,
    SeatOrderButton,
    SeatOrderProvider,
    seating_mode_change_message,
    seating_mode_options,
)
from bot.services.pod_tournament import actor_label
from bot.sets import active_set_code


Apply = Callable[[discord.Interaction, str], Awaitable[str | None]]
KickApply = Callable[[discord.Interaction, str], Awaitable[str | None]]
KickTargetsProvider = Callable[[], list[tuple[str, str]]]
LinkApply = Callable[[discord.Interaction, str, discord.abc.User], Awaitable[str | None]]
LinkTargetsProvider = Callable[[], Awaitable[list[str]]]
CancelApply = Callable[[discord.Interaction], Awaitable[str | None]]

LINK_SEAT_PROMPT = "Pick the unlinked Draftmancer seat to assign:"

TIMER_MIN = 10
TIMER_MAX = 600


def kick_notice(actor: str, name: str) -> str:
    return f"🔨 **{name}** was removed by {actor}"


def link_notice(actor: str, member_mention: str, arena_name: str) -> str:
    return f"🔗 {member_mention} linked to `{arena_name}` by {actor}"


def cancel_notice(actor: str) -> str:
    return f"{actor} canceled the draft 🥀"


def timer_notice(actor: str, seconds: int) -> str:
    return settings_change_message(actor, "Pick timer", f"{seconds}s")


class PodSettingsView(ui.View):
    def __init__(self, *, on_format: Apply | None = None, on_pairing: Apply | None = None,
                 current_code: str | None = None, current_mode: str | None = None,
                 on_seating_mode: Apply | None = None, current_seating: str | None = None,
                 on_seating: SeatingApply | None = None,
                 seat_order_provider: SeatOrderProvider | None = None,
                 on_seating_table: Callable[[discord.Interaction], Awaitable[None]] | None = None,
                 on_seated: SeatedNotify | None = None,
                 on_timer: Apply | None = None, current_timer: int | None = None,
                 kick_targets_provider: KickTargetsProvider | None = None,
                 on_kick: KickApply | None = None,
                 link_targets_provider: LinkTargetsProvider | None = None,
                 on_link: LinkApply | None = None,
                 on_cancel: CancelApply | None = None,
                 on_reschedule: Apply | None = None,
                 event_name: str | None = None,
                 notice_channel: discord.abc.Messageable | None = None) -> None:
        super().__init__(timeout=300)
        self.notice_channel = notice_channel
        self.on_format = on_format
        self.on_pairing = on_pairing
        self.current_code = current_code
        self.current_mode = current_mode
        self.on_seating_mode = on_seating_mode
        self.current_seating = current_seating
        self.on_seating = on_seating
        self.seat_order_provider = seat_order_provider
        self.on_seating_table = on_seating_table
        self.on_seated = on_seated
        self.on_timer = on_timer
        self.current_timer = current_timer
        self.kick_targets_provider = kick_targets_provider
        self.on_kick = on_kick
        self.link_targets_provider = link_targets_provider
        self.on_link = on_link
        self.on_cancel = on_cancel
        self.on_reschedule = on_reschedule
        self.event_name = event_name
        if on_format is not None:
            self.add_item(_FormatSetting(current_code))
        if on_pairing is not None:
            self.add_item(_PairingSetting(current_mode))
        if on_seating_mode is not None:
            self.add_item(_SeatingSetting(current_seating))
        if (on_seating is not None and seat_order_provider is not None
                and (current_seating or "random") == "manual"):
            self.add_item(SeatOrderButton(
                seat_order_provider=seat_order_provider, on_seating=on_seating, on_seated=on_seated, row=3))
        if on_timer is not None:
            self.add_item(_TimerButton(current_timer, row=3))
        if link_targets_provider is not None and on_link is not None:
            self.add_item(_LinkPlayersButton(row=3))
        if kick_targets_provider is not None and on_kick is not None:
            self.add_item(_KickPlayerButton(row=3))
        if on_reschedule is not None:
            self.add_item(_RescheduleButton(row=4))
        if on_cancel is not None:
            self.add_item(_CancelDraftButton(row=4))

    async def apply(self, interaction: discord.Interaction, *, on_apply: Apply,
                    value: str, attr: str, notice: str, marker: str) -> None:
        await interaction.response.defer()
        err = await on_apply(interaction, value)
        if err:
            await interaction.followup.send(f"⚠️ {err}", ephemeral=True)
            return
        setattr(self, attr, value)
        await interaction.edit_original_response(view=PodSettingsView(
            on_format=self.on_format, on_pairing=self.on_pairing,
            current_code=self.current_code, current_mode=self.current_mode,
            on_seating_mode=self.on_seating_mode, current_seating=self.current_seating,
            on_seating=self.on_seating, seat_order_provider=self.seat_order_provider,
            on_seating_table=self.on_seating_table, on_seated=self.on_seated,
            on_timer=self.on_timer, current_timer=self.current_timer,
            kick_targets_provider=self.kick_targets_provider, on_kick=self.on_kick,
            link_targets_provider=self.link_targets_provider, on_link=self.on_link,
            on_cancel=self.on_cancel, on_reschedule=self.on_reschedule, event_name=self.event_name,
            notice_channel=self.notice_channel,
        ))
        channel = self.notice_channel or interaction.channel
        if channel is not None:
            await send_settings_notice(channel, interaction.client.user, notice, marker=marker)
        await update_registered_embed(
            channel,
            client_user=interaction.client.user,
            set_code=self.current_code or active_set_code(),
            pairing_mode=self.current_mode,
            seating_mode=self.current_seating,
            championship=is_championship(self.event_name),
        )

    async def _apply_format_code(self, interaction: discord.Interaction, code: str) -> None:
        await self.apply(interaction, on_apply=self.on_format, value=code, attr="current_code",
                         notice=format_change_message(actor_label(interaction), code),
                         marker=settings_notice_marker("Format"))

    async def _apply_pick_timer(self, interaction: discord.Interaction, seconds: int) -> None:
        await self.apply(interaction, on_apply=self.on_timer, value=str(seconds), attr="current_timer",
                         notice=timer_notice(actor_label(interaction), seconds),
                         marker=settings_notice_marker("Pick timer"))


class _FormatSetting(ui.Select):
    def __init__(self, current_code: str | None) -> None:
        super().__init__(placeholder=FORMAT_PLACEHOLDER, options=format_options(current_code),
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PodSettingsView = self.view
        code = self.values[0]
        if code == FORMAT_WRITE_IN_VALUE:
            await interaction.response.send_modal(FormatWriteInModal(view._apply_format_code))
            return
        await view._apply_format_code(interaction, code)


class _PairingSetting(ui.Select):
    def __init__(self, current_mode: str | None) -> None:
        super().__init__(placeholder=PAIRING_PLACEHOLDER, options=pairing_options(current_mode),
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PodSettingsView = self.view
        mode = self.values[0]
        await view.apply(interaction, on_apply=view.on_pairing, value=mode, attr="current_mode",
                         notice=pairing_change_message(actor_label(interaction), mode),
                         marker=settings_notice_marker("Pairings"))


class _SeatingSetting(ui.Select):
    def __init__(self, current_seating: str | None) -> None:
        super().__init__(placeholder=SEATING_SELECT_PLACEHOLDER, options=seating_mode_options(current_seating),
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PodSettingsView = self.view
        mode = self.values[0]
        await view.apply(interaction, on_apply=view.on_seating_mode, value=mode, attr="current_seating",
                         notice=seating_mode_change_message(actor_label(interaction), mode),
                         marker=settings_notice_marker("Seats"))
        if mode == "leaderboard" and view.on_seating_table is not None:
            await view.on_seating_table(interaction)


class _TimerButton(ui.Button):
    def __init__(self, current_timer: int | None, row: int | None = None) -> None:
        label = f"Pick Timer: {current_timer}s" if current_timer is not None else "Pick Timer"
        super().__init__(label=label, emoji="⏱️", style=discord.ButtonStyle.grey, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(_TimerModal(self.view))


class _TimerModal(ui.Modal, title="Pick timer"):
    seconds = ui.TextInput(label="Seconds per pick", placeholder="e.g. 60", min_length=1, max_length=3)

    def __init__(self, view: PodSettingsView) -> None:
        super().__init__()
        self.view = view
        if view.current_timer is not None:
            self.seconds.default = str(view.current_timer)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.seconds.value.strip()
        if not raw.isdigit() or not (TIMER_MIN <= int(raw) <= TIMER_MAX):
            await interaction.response.send_message(
                f"⚠️ Enter a whole number of seconds between {TIMER_MIN} and {TIMER_MAX}.", ephemeral=True,
            )
            return
        await self.view._apply_pick_timer(interaction, int(raw))


class _RescheduleButton(ui.Button):
    def __init__(self, row: int | None = None) -> None:
        super().__init__(label="Reschedule", emoji="🕐", style=discord.ButtonStyle.grey, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(_RescheduleModal(self.view))


class _RescheduleModal(ui.Modal, title="Reschedule pod"):
    new_time = ui.TextInput(
        label="New start (time from now, or ET time)", placeholder="1h, 21:00, or 2026-07-18 21:00")

    def __init__(self, view: PodSettingsView) -> None:
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        err = await self.view.on_reschedule(interaction, self.new_time.value)
        if err:
            await interaction.followup.send(f"⚠️ {err}", ephemeral=True)


class _KickPlayerButton(ui.Button):
    def __init__(self, row: int | None = None) -> None:
        super().__init__(label="Kick Player", emoji="🔨", style=discord.ButtonStyle.grey, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PodSettingsView = self.view
        targets = view.kick_targets_provider()
        if not targets:
            await interaction.response.send_message(
                "No players or spectators in the Draftmancer session.", ephemeral=True,
            )
            return
        await interaction.response.send_message(
            view=_KickSelectView(targets, view.on_kick), ephemeral=True,
        )


class _KickSelectView(ui.View):
    def __init__(self, targets: list[tuple[str, str]], on_kick: KickApply) -> None:
        super().__init__(timeout=120)
        self.add_item(_KickSelect(targets, on_kick))


class _KickSelect(ui.Select):
    def __init__(self, targets: list[tuple[str, str]], on_kick: KickApply) -> None:
        options = [discord.SelectOption(label=name, value=user_id) for user_id, name in targets[:25]]
        super().__init__(placeholder="Remove a player or spectator from the table", options=options,
                         min_values=1, max_values=1)
        self.names = dict(targets)
        self.on_kick = on_kick

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        user_id = self.values[0]
        name = self.names.get(user_id, "player")
        err = await self.on_kick(interaction, user_id)
        if err:
            await interaction.followup.send(f"⚠️ {err}", ephemeral=True)
            return
        await interaction.delete_original_response()
        if interaction.channel is not None:
            await interaction.channel.send(kick_notice(actor_label(interaction), name))


class _LinkPlayersButton(ui.Button):
    def __init__(self, row: int | None = None) -> None:
        super().__init__(label="Link Players", emoji="🔗", style=discord.ButtonStyle.grey, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PodSettingsView = self.view
        targets = await view.link_targets_provider()
        if not targets:
            await interaction.response.send_message(
                "Everyone in the Draftmancer session is already linked.", ephemeral=True,
            )
            return
        await interaction.response.send_message(
            LINK_SEAT_PROMPT,
            view=LinkSeatSelectView(targets, view.on_link), ephemeral=True,
        )


class LinkSeatSelectView(ui.View):
    """Two-step seat→member link picker, shared by the Settings 'Link Players' button and the ready-check
    unlinked-seat confirm so an organizer can bind a stray seat from either spot."""

    def __init__(self, targets: list[str], on_link: LinkApply) -> None:
        super().__init__(timeout=120)
        self.add_item(_LinkSeatSelect(targets, on_link))


class _LinkSeatSelect(ui.Select):
    def __init__(self, targets: list[str], on_link: LinkApply) -> None:
        options = [discord.SelectOption(label=name, value=name) for name in targets[:25]]
        super().__init__(placeholder="Unlinked Draftmancer seat", options=options,
                         min_values=1, max_values=1)
        self.on_link = on_link

    async def callback(self, interaction: discord.Interaction) -> None:
        arena_name = self.values[0]
        await interaction.response.edit_message(
            content=f"Who is `{arena_name}`?",
            view=_LinkMemberSelectView(arena_name, self.on_link),
        )


class _LinkMemberSelectView(ui.View):
    def __init__(self, arena_name: str, on_link: LinkApply) -> None:
        super().__init__(timeout=120)
        self.add_item(_LinkMemberSelect(arena_name, on_link))


class _LinkMemberSelect(ui.UserSelect):
    def __init__(self, arena_name: str, on_link: LinkApply) -> None:
        super().__init__(placeholder="Pick the Discord member", min_values=1, max_values=1)
        self.arena_name = arena_name
        self.on_link = on_link

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        member = self.values[0]
        err = await self.on_link(interaction, self.arena_name, member)
        if err:
            await interaction.followup.send(f"⚠️ {err}", ephemeral=True)
            return
        await interaction.edit_original_response(
            content=f"🔗 **{member.display_name}** linked as `{self.arena_name}`.", view=None,
        )
        if interaction.channel is not None:
            await interaction.channel.send(
                link_notice(actor_label(interaction), member.mention, self.arena_name),
                allowed_mentions=discord.AllowedMentions(users=True),
            )


class _CancelDraftButton(ui.Button):
    def __init__(self, row: int | None = None) -> None:
        super().__init__(label="Cancel Draft", emoji="🗑️", style=discord.ButtonStyle.danger, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PodSettingsView = self.view
        event_name = view.event_name or "this pod draft"
        await interaction.response.send_message(
            f"This permanently deletes **{event_name}** — participants, matches, replays, and the "
            "leaderboard page. This can't be undone.",
            view=_CancelConfirmView(view.on_cancel, event_name),
            ephemeral=True,
        )


class _CancelConfirmView(ui.View):
    def __init__(self, on_cancel: CancelApply, event_name: str) -> None:
        super().__init__(timeout=60)
        self.on_cancel = on_cancel
        self.event_name = event_name

    @ui.button(label="Delete Event", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.response.defer()
        err = await self.on_cancel(interaction)
        if err:
            await interaction.followup.send(f"⚠️ {err}", ephemeral=True)
            return
        await interaction.edit_original_response(content=f"🗑️ **{self.event_name}** deleted.", view=None)
        if interaction.channel is not None:
            await interaction.channel.send(cancel_notice(actor_label(interaction)))
