"""Pod-draft format registry — the source of truth for which formats a pod can draft.

A pod draft's format is identified by its `set_code`: a real set code (e.g. `SOS`) drafts that
set via Draftmancer's `setRestriction`, while a registered custom code (e.g. `PEASANT`) loads a
CubeCobra cube via `importCube`. The mapping lives here in code — adding a cube is a two-line edit,
same friction as rotating a set in `bot/sets.py`. Keeping the code as `set_code` means the
frontend's existing per-set filters bucket cube pods for free.

Pure data: no Discord deps, so the data layer can import `label_for` to persist the display label.
The selector UI that drives this lives in `lobby_embed.FormatSelectView`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PodFormat:
    code: str
    label: str
    cube_id: str | None
    session_slug: str


PEASANT_CODE = "PEASANT"
PEASANT_LABEL = "Peasant Cube"
PEASANT_CUBE_ID = "DaneeliusPeasantAllStars"
PEASANT_SESSION_SLUG = "Peasant"

# Registered custom (CubeCobra) pod formats, keyed by the code stored in pod_draft_events.set_code.
CUSTOM_FORMATS: dict[str, PodFormat] = {
    PEASANT_CODE: PodFormat(PEASANT_CODE, PEASANT_LABEL, PEASANT_CUBE_ID, PEASANT_SESSION_SLUG),
}

LATEST_SET_LABEL = "Latest Set"
SELECT_PLACEHOLDER = "Select a format"
FORMAT_LOCKED_MSG = "The draft has already started — the format can't be changed now."
EVENT_MISSING_MSG = "Pod-draft event not found."


def custom_formats() -> list[PodFormat]:
    return list(CUSTOM_FORMATS.values())


def is_custom(code: str | None) -> bool:
    return bool(code) and code.upper() in CUSTOM_FORMATS


def cube_id_for(code: str) -> str | None:
    fmt = CUSTOM_FORMATS.get(code.upper())
    return fmt.cube_id if fmt else None


def session_slug_for(code: str | None) -> str | None:
    """Short token used in the Draftmancer session id for a custom format; None for a plain set."""
    fmt = CUSTOM_FORMATS.get(code.upper()) if code else None
    return fmt.session_slug if fmt else None


def detect_in_title(title: str) -> str | None:
    """Custom format code whose label appears in a sesh title, else None. Case-insensitive."""
    lowered = title.lower()
    for fmt in CUSTOM_FORMATS.values():
        if fmt.label.lower() in lowered:
            return fmt.code
    return None


def label_for(code: str) -> str | None:
    """Display label for a custom (cube) format; None for a plain set — its name lives in the title."""
    fmt = CUSTOM_FORMATS.get(code.upper())
    return fmt.label if fmt else None


def format_display(code: str) -> str:
    """Always-present format label for footers/cards: the cube label, or the bare set code."""
    return label_for(code) or code.upper()


def format_applied_message(code: str) -> str:
    return f"Format set to **{label_for(code) or code}**."


def settings_change_message(actor: str, setting: str, value: str, *, subtext: str | None = None) -> str:
    """Public thread notice for a lobby Settings change; shared by Format and Pairings."""
    line = f"⚙️ **{actor}** set {setting} to **{value}**"
    return f"{line}\n-# {subtext}" if subtext else line


def format_change_message(actor: str, code: str) -> str:
    """Public thread notice when the draft format changes."""
    return settings_change_message(actor, "Format", label_for(code) or code)
