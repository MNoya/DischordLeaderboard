"""Combined pod-draft lobby Settings panel: draft format + pairing mode + seats in one ephemeral view.

Picking an option applies it, re-renders the panel (all dropdowns kept, the changed one defaulted),
and posts a public thread notice — so the confirmation everyone sees lives in the channel, not in the
private ephemeral. The Seat Order button is contextual to Manual seats + a live lobby.
"""
from __future__ import annotations

from typing import Awaitable, Callable

import discord
from discord import ui

from bot.services.pod_format import format_change_message, settings_notice_marker
from bot.services.pod_notices import send_settings_notice
from bot.services.pod_drafts import is_championship
from bot.services.pod_registration_embed import update_registered_embed
from bot.services.pod_format_select import SELECT_PLACEHOLDER as FORMAT_PLACEHOLDER
from bot.services.pod_format_select import format_options
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
from bot.sets import ACTIVE_SET_CODE


Apply = Callable[[discord.Interaction, str], Awaitable[str | None]]
KickApply = Callable[[discord.Interaction, str], Awaitable[str | None]]
KickTargetsProvider = Callable[[], list[tuple[str, str]]]
CancelApply = Callable[[discord.Interaction], Awaitable[str | None]]


def kick_notice(actor: str, name: str) -> str:
    return f"🔨 **{name}** was removed by {actor}"


def cancel_notice(actor: str) -> str:
    return f"{actor} canceled the draft 🥀"


class PodSettingsView(ui.View):
    def __init__(self, *, on_format: Apply, on_pairing: Apply,
                 current_code: str | None, current_mode: str | None,
                 on_seating_mode: Apply | None = None, current_seating: str | None = None,
                 on_seating: SeatingApply | None = None,
                 seat_order_provider: SeatOrderProvider | None = None,
                 on_seating_table: Callable[[discord.Interaction], Awaitable[None]] | None = None,
                 on_seated: SeatedNotify | None = None,
                 kick_targets_provider: KickTargetsProvider | None = None,
                 on_kick: KickApply | None = None,
                 on_cancel: CancelApply | None = None,
                 event_name: str | None = None) -> None:
        super().__init__(timeout=300)
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
        self.kick_targets_provider = kick_targets_provider
        self.on_kick = on_kick
        self.on_cancel = on_cancel
        self.event_name = event_name
        self.add_item(_FormatSetting(current_code))
        self.add_item(_PairingSetting(current_mode))
        if on_seating_mode is not None:
            self.add_item(_SeatingSetting(current_seating))
        if (on_seating is not None and seat_order_provider is not None
                and (current_seating or "random") == "manual"):
            self.add_item(SeatOrderButton(
                seat_order_provider=seat_order_provider, on_seating=on_seating, on_seated=on_seated, row=3))
        if kick_targets_provider is not None and on_kick is not None:
            self.add_item(_KickPlayerButton(row=3))
        if on_cancel is not None:
            self.add_item(_CancelDraftButton(row=3))

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
            kick_targets_provider=self.kick_targets_provider, on_kick=self.on_kick,
            on_cancel=self.on_cancel, event_name=self.event_name,
        ))
        if interaction.channel is not None:
            await send_settings_notice(interaction.channel, interaction.client.user, notice, marker=marker)
        await update_registered_embed(
            interaction.channel,
            client_user=interaction.client.user,
            set_code=self.current_code or ACTIVE_SET_CODE,
            pairing_mode=self.current_mode,
            seating_mode=self.current_seating,
            championship=is_championship(self.event_name),
        )


class _FormatSetting(ui.Select):
    def __init__(self, current_code: str | None) -> None:
        super().__init__(placeholder=FORMAT_PLACEHOLDER, options=format_options(current_code),
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PodSettingsView = self.view
        code = self.values[0]
        await view.apply(interaction, on_apply=view.on_format, value=code, attr="current_code",
                         notice=format_change_message(actor_label(interaction), code),
                         marker=settings_notice_marker("Format"))


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
        await interaction.edit_original_response(content=f"🔨 **{name}** removed.", view=None)
        if interaction.channel is not None:
            await interaction.channel.send(kick_notice(actor_label(interaction), name))


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
