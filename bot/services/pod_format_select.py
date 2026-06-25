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
from bot.sets import active_set_code, upcoming_sets


ApplyFormatCallback = Callable[[discord.Interaction, str], Awaitable[str | None]]

WRITE_IN_VALUE = "__format_write_in__"


def format_options(current_code: str | None) -> list[discord.SelectOption]:
    """The format dropdown options (active set + upcoming sets + custom cubes + a write-in launcher),
    with the current one defaulted. Labels are prefixed with 'Format:' so the collapsed dropdown reads
    e.g. 'Format: SOS', matching the Pairings and Seats dropdowns and the lobby footer. Upcoming sets
    (e.g. MSH before it rotates in) let a pod preview-draft a set the bot serves via setRestriction; the
    write-in option drafts any other set code the user types."""
    cur = (current_code or "").upper()
    active = active_set_code()
    upcoming_codes = {s.code for s in upcoming_sets()}
    known = {active} | upcoming_codes | set(CUSTOM_FORMATS)
    options = [discord.SelectOption(
        label=f"Format: {active}",
        value=active,
        description=f"Draft the latest set ({active})",
        default=cur in ("", active),
    )]
    for seed in upcoming_sets():
        options.append(discord.SelectOption(
            label=f"Format: {seed.code}",
            value=seed.code,
            description=f"Preview draft: {seed.name}",
            default=(cur == seed.code),
        ))
    for fmt in custom_formats():
        options.append(discord.SelectOption(
            label=f"Format: {fmt.label}",
            value=fmt.code,
            description=f"CubeCobra: {fmt.cube_id}",
            default=(cur == fmt.code.upper()),
        ))
    if cur and cur not in known:
        options.append(discord.SelectOption(
            label=f"Format: {cur}", value=cur, description="Written-in set code", default=True,
        ))
    options.append(discord.SelectOption(
        label="Format: Write in…",
        value=WRITE_IN_VALUE,
        description="Type any set code the bot will try to draft",
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
        if code == WRITE_IN_VALUE:
            await interaction.response.send_modal(FormatWriteInModal(self._apply_write_in))
            return
        await interaction.response.defer()
        await self._apply_and_refresh(interaction, code)

    async def _apply_write_in(self, interaction: discord.Interaction, code: str) -> None:
        await interaction.response.defer()
        await self._apply_and_refresh(interaction, code)

    async def _apply_and_refresh(self, interaction: discord.Interaction, code: str) -> None:
        err = await self._on_apply(interaction, code)
        if err:
            await interaction.edit_original_response(content=f"⚠️ {err}", view=None)
            return
        await interaction.edit_original_response(
            content=format_applied_message(code),
            view=FormatSelectView(self._on_apply, current_code=code),
        )


class FormatWriteInModal(ui.Modal, title="Write in a set code"):
    code = ui.TextInput(
        label="Set code",
        placeholder="e.g. MH3, FIN, DSK",
        min_length=2,
        max_length=5,
        required=True,
    )

    def __init__(self, on_code: Callable[[discord.Interaction, str], Awaitable[None]]) -> None:
        super().__init__()
        self._on_code = on_code

    async def on_submit(self, interaction: discord.Interaction) -> None:
        typed = self.code.value.strip().upper()
        if not typed.isalnum():
            await interaction.response.send_message(
                f"⚠️ `{self.code.value}` isn't a valid set code — use letters and numbers only.",
                ephemeral=True,
            )
            return
        await self._on_code(interaction, typed)
