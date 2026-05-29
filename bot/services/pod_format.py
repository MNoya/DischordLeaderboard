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


PEASANT_CODE = "PEASANT"
PEASANT_LABEL = "Peasant Cube"
PEASANT_CUBE_ID = "DaneeliusPeasantAllStars"

# Registered custom (CubeCobra) pod formats, keyed by the code stored in pod_draft_events.set_code.
CUSTOM_FORMATS: dict[str, PodFormat] = {
    PEASANT_CODE: PodFormat(PEASANT_CODE, PEASANT_LABEL, PEASANT_CUBE_ID),
}

LATEST_SET_LABEL = "Latest Set"
SELECT_PLACEHOLDER = "Select a format"
FORMAT_LOCKED_MSG = "The draft has already started — the format can't be changed now."
EVENT_MISSING_MSG = "Pod-draft event not found."


def custom_formats() -> list[PodFormat]:
    return list(CUSTOM_FORMATS.values())


def cube_id_for(code: str) -> str | None:
    fmt = CUSTOM_FORMATS.get(code.upper())
    return fmt.cube_id if fmt else None


def label_for(code: str) -> str | None:
    """Display label for a custom (cube) format; None for a plain set — its name lives in the title."""
    fmt = CUSTOM_FORMATS.get(code.upper())
    return fmt.label if fmt else None


def format_applied_message(code: str) -> str:
    return f"Format set to **{label_for(code) or code}**."
