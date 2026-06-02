"""Pod-draft seat-order control: a Settings-panel button + modal to manually arrange the Draftmancer table.

The organizer reorders the lobby names (seat 1 at the top); matching is by player name and any leading
numbering is ignored. Applied pre-draft via setSeating.
"""
from __future__ import annotations

import logging
import re
from typing import Awaitable, Callable

import discord
from discord import ui

log = logging.getLogger("bot.pod_seating_select")

SEAT_BUTTON_LABEL = "Seat Order"
SEAT_BUTTON_EMOJI = "🪑"
_LEADING_NUM_PREFIX_RE = re.compile(r"^\s*#?\d+(?=$|[\s.):\-])[.):\-]*\s*")

SeatingApply = Callable[[discord.Interaction, list[str]], Awaitable[str | None]]
SeatOrderProvider = Callable[[], Awaitable[list[tuple[str, str]]]]


def seating_change_message(actor: str, labels: list[str]) -> str:
    """Public thread notice when the seating order changes, top-to-bottom as subtext."""
    order = " → ".join(labels)
    return f"🪑 **{actor}** updated the seating order\n-# {order}"


def parse_seat_reorder(
    text: str, current_order: list[str], labels: list[str],
) -> tuple[list[str] | None, str | None]:
    """Map edited modal text back to a reordered userName list, matching by player name. Any leading
    numbering is ignored. Returns (reordered_names, None) on success, else (None, error_message)."""
    lines = [stripped for stripped in (ln.strip() for ln in text.splitlines()) if stripped]
    if len(lines) != len(current_order):
        return None, f"List all {len(current_order)} players, one per line (seat 1 at the top)."
    reordered = _parse_by_name(lines, current_order, labels)
    if reordered is None:
        return None, "Couldn't read that — keep each player's name from the list, one per line."
    return reordered, None


def _parse_by_name(lines: list[str], current_order: list[str], labels: list[str]) -> list[str] | None:
    label_to_name: dict[str, str] = {}
    for name, label in zip(current_order, labels):
        key = label.strip().lower()
        if key in label_to_name:
            return None
        label_to_name[key] = name
    picked: list[str] = []
    for line in lines:
        key = _LEADING_NUM_PREFIX_RE.sub("", line).strip().lower()
        name = label_to_name.get(key)
        if name is None:
            return None
        picked.append(name)
    if sorted(picked) != sorted(current_order):
        return None
    return picked


class SeatOrderModal(ui.Modal, title="Seat Order"):
    def __init__(self, *, current_order: list[str], labels: list[str], on_seating: SeatingApply) -> None:
        super().__init__()
        self.current_order = current_order
        self.labels = labels
        self.on_seating = on_seating
        default = "\n".join(labels)
        self.entry = ui.TextInput(
            label="Seat 1 at the top — one player per line",
            style=discord.TextStyle.paragraph,
            default=default,
            required=True,
            max_length=1000,
        )
        self.add_item(self.entry)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        reordered, err = parse_seat_reorder(self.entry.value, self.current_order, self.labels)
        if err is not None:
            await interaction.response.send_message(f"⚠️ {err}", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        apply_err = await self.on_seating(interaction, reordered)
        if apply_err is not None:
            await interaction.followup.send(f"⚠️ {apply_err}", ephemeral=True)
            return
        new_labels = [self.labels[self.current_order.index(name)] for name in reordered]
        await interaction.followup.send("Seating updated.", ephemeral=True)
        if interaction.channel is not None:
            from bot.services.pod_tournament import actor_label
            try:
                await interaction.channel.send(seating_change_message(actor_label(interaction), new_labels))
            except discord.HTTPException:
                log.warning("could not post seating-change notice", exc_info=True)


class SeatOrderButton(ui.Button):
    def __init__(self, *, seat_order_provider: SeatOrderProvider, on_seating: SeatingApply,
                 row: int | None = None) -> None:
        super().__init__(label=SEAT_BUTTON_LABEL, emoji=SEAT_BUTTON_EMOJI,
                         style=discord.ButtonStyle.grey, row=row)
        self.seat_order_provider = seat_order_provider
        self.on_seating = on_seating

    async def callback(self, interaction: discord.Interaction) -> None:
        order = await self.seat_order_provider()
        if len(order) < 2:
            await interaction.response.send_message(
                "Need at least 2 players in the Draftmancer lobby to set seating.", ephemeral=True)
            return
        current_order = [name for name, _ in order]
        labels = [lbl for _, lbl in order]
        await interaction.response.send_modal(
            SeatOrderModal(current_order=current_order, labels=labels, on_seating=self.on_seating))
