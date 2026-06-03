"""Discord selector for choosing a pod-draft format.

Shared by `/pod-format`, the lobby "Change Format" button, and the `!test format` preview.
Persistence is injected via the `on_apply` callback so the same view backs the live DB-write flow
and the in-memory testlobby sandbox. Format definitions live in the pure `pod_format` registry.
"""
from __future__ import annotations

from typing import Awaitable, Callable

import discord
from discord import ui

from bot.services.pod_format import (
    CUSTOM_FORMATS,
    SELECT_PLACEHOLDER,
    custom_formats,
    format_applied_message,
)
from bot.sets import ACTIVE_SET_CODE


ApplyFormatCallback = Callable[[discord.Interaction, str], Awaitable[str | None]]


def format_options(current_code: str | None) -> list[discord.SelectOption]:
    """The format dropdown options (current set + custom cubes), with the active one defaulted. Labels
    are prefixed with 'Format:' so the collapsed dropdown reads e.g. 'Format: SOS', matching the
    Pairings and Seats dropdowns and the lobby footer."""
    cur = (current_code or "").upper()
    on_custom = cur in CUSTOM_FORMATS
    options = [discord.SelectOption(
        label=f"Format: {ACTIVE_SET_CODE}",
        value=ACTIVE_SET_CODE,
        description=f"Draft the latest set ({ACTIVE_SET_CODE})",
        default=not on_custom,
    )]
    for fmt in custom_formats():
        options.append(discord.SelectOption(
            label=f"Format: {fmt.label}",
            value=fmt.code,
            description=f"CubeCobra: {fmt.cube_id}",
            default=(cur == fmt.code.upper()),
        ))
    return options


class FormatSelectView(ui.View):
    def __init__(self, on_apply: ApplyFormatCallback, *, current_code: str | None = None) -> None:
        super().__init__(timeout=300)
        self.add_item(FormatSelect(on_apply, current_code))


class FormatSelect(ui.Select):
    def __init__(self, on_apply: ApplyFormatCallback, current_code: str | None) -> None:
        super().__init__(
            placeholder=SELECT_PLACEHOLDER, options=format_options(current_code),
            min_values=1, max_values=1,
        )
        self._on_apply = on_apply

    async def callback(self, interaction: discord.Interaction) -> None:
        code = self.values[0]
        await interaction.response.defer()
        err = await self._on_apply(interaction, code)
        if err:
            await interaction.edit_original_response(content=f"⚠️ {err}", view=None)
            return
        await interaction.edit_original_response(
            content=format_applied_message(code),
            view=FormatSelectView(self._on_apply, current_code=code),
        )
