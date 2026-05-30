"""Combined pod-draft lobby Settings panel: draft format + pairing mode in one ephemeral view.

Picking an option applies it, re-renders the panel (both dropdowns kept, the changed one defaulted),
and posts a public thread notice — so the confirmation everyone sees lives in the channel, not in the
private ephemeral.
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

import discord
from discord import ui

from bot.services.pod_format import format_change_message
from bot.services.pod_format_select import SELECT_PLACEHOLDER as FORMAT_PLACEHOLDER
from bot.services.pod_format_select import format_options
from bot.services.pod_pairing_select import SELECT_PLACEHOLDER as PAIRING_PLACEHOLDER
from bot.services.pod_pairing_select import pairing_change_message, pairing_options
from bot.services.pod_tournament import actor_label

log = logging.getLogger("bot.pod_settings_view")

Apply = Callable[[discord.Interaction, str], Awaitable[str | None]]


class PodSettingsView(ui.View):
    def __init__(self, *, on_format: Apply, on_pairing: Apply,
                 current_code: str | None, current_mode: str | None) -> None:
        super().__init__(timeout=300)
        self.on_format = on_format
        self.on_pairing = on_pairing
        self.current_code = current_code
        self.current_mode = current_mode
        self.add_item(_FormatSetting(current_code))
        self.add_item(_PairingSetting(current_mode))

    async def apply(self, interaction: discord.Interaction, *, on_apply: Apply,
                    value: str, attr: str, notice: str) -> None:
        await interaction.response.defer()
        err = await on_apply(interaction, value)
        if err:
            await interaction.followup.send(f"⚠️ {err}", ephemeral=True)
            return
        setattr(self, attr, value)
        await interaction.edit_original_response(view=PodSettingsView(
            on_format=self.on_format, on_pairing=self.on_pairing,
            current_code=self.current_code, current_mode=self.current_mode,
        ))
        if interaction.channel is not None:
            try:
                await interaction.channel.send(notice)
            except discord.HTTPException:
                log.warning("could not post settings-change notice", exc_info=True)


class _FormatSetting(ui.Select):
    def __init__(self, current_code: str | None) -> None:
        super().__init__(placeholder=FORMAT_PLACEHOLDER, options=format_options(current_code),
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PodSettingsView = self.view
        code = self.values[0]
        await view.apply(interaction, on_apply=view.on_format, value=code, attr="current_code",
                         notice=format_change_message(actor_label(interaction), code))


class _PairingSetting(ui.Select):
    def __init__(self, current_mode: str | None) -> None:
        super().__init__(placeholder=PAIRING_PLACEHOLDER, options=pairing_options(current_mode),
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PodSettingsView = self.view
        mode = self.values[0]
        await view.apply(interaction, on_apply=view.on_pairing, value=mode, attr="current_mode",
                         notice=pairing_change_message(actor_label(interaction), mode))
