"""Pod-draft pairing-mode options: Swiss Tournament or Fast Bracket.

Surfaced through the lobby Settings panel (pod_settings_view). Fast Bracket is honored at start only
when the roster is exactly 8; other sizes fall back to Swiss.
"""
from __future__ import annotations

import discord

from bot.services.pod_format import settings_change_message


PAIRING_MODES = (
    ("swiss", "Swiss Tournament", "Three rounds, each paired after the previous fully finishes."),
    ("bracket", "Fast Bracket", "Pairs players the moment two reach the same record. 8p only"),
)
SELECT_PLACEHOLDER = "Choose pairing mode"


def pairing_label(mode: str | None) -> str:
    """Display label for a pairing mode; defaults to Swiss."""
    cur = (mode or "swiss").lower()
    return next((lbl for code, lbl, _ in PAIRING_MODES if code == cur), cur)


def pairing_change_message(actor: str, mode: str) -> str:
    """Public thread notice when the pairing mode changes, with the mode's description as subtext."""
    label = next((lbl for code, lbl, _ in PAIRING_MODES if code == mode), mode)
    desc = next((d for code, _, d in PAIRING_MODES if code == mode), "")
    return settings_change_message(actor, "Pairings", label, subtext=desc)


def pairing_options(current_mode: str | None) -> list[discord.SelectOption]:
    """The pairing-mode dropdown options, with the current mode defaulted."""
    cur = (current_mode or "swiss").lower()
    return [
        discord.SelectOption(label=label, value=code, description=desc, default=(cur == code))
        for code, label, desc in PAIRING_MODES
    ]
