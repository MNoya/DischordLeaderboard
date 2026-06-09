"""Source of truth for Magic set metadata and which set is currently active.

Changes here ship as part of the codebase — bumping ``ACTIVE_SET_CODE`` and
pushing to master is what rotates the leaderboard onto a new set on Railway.
No env var indirection.

Dates are MTG Arena release dates (not tabletop). The active set's ``end_date``
holds the anticipated rotation date based on the next set's announced launch;
a real ``end_date`` is filled in when a successor set is added.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class SetSeed:
    code: str
    name: str
    start_date: date
    end_date: date | None
    expansion_match: str | None = None


ALL_SETS: tuple[SetSeed, ...] = (
    SetSeed("KHM", "Kaldheim", date(2021, 1, 28), date(2021, 4, 14)),
    SetSeed("STX", "Strixhaven: School of Mages", date(2021, 4, 15), date(2021, 7, 7)),
    SetSeed("WOE", "Wilds of Eldraine", date(2023, 9, 5), date(2023, 11, 13)),
    SetSeed("LCI", "The Lost Caverns of Ixalan", date(2023, 11, 14), date(2024, 2, 5)),
    SetSeed("MKM", "Murders at Karlov Manor", date(2024, 2, 6), date(2024, 4, 15)),
    SetSeed("OTJ", "Outlaws of Thunder Junction", date(2024, 4, 16), date(2024, 7, 29)),
    SetSeed("BLB", "Bloomburrow", date(2024, 7, 30), date(2024, 9, 23)),
    SetSeed("DSK", "Duskmourn: House of Horror", date(2024, 9, 24), date(2024, 11, 11)),
    SetSeed("FDN", "Foundations", date(2024, 11, 12), date(2025, 2, 10)),
    SetSeed("DFT", "Aetherdrift", date(2025, 2, 11), date(2025, 4, 7)),
    SetSeed("TDM", "Tarkir: Dragonstorm", date(2025, 4, 8), date(2025, 6, 8)),
    SetSeed("FIN", "Final Fantasy", date(2025, 6, 9), date(2025, 7, 28)),
    SetSeed("EOE", "Edge of Eternities", date(2025, 7, 29), date(2025, 9, 23)),
    SetSeed("CUBE", "Arena Powered Cube", date(2025, 10, 28), None, expansion_match="Cube - Powered"),
    SetSeed("TLA", "Avatar: The Last Airbender", date(2025, 11, 16), date(2026, 1, 19)),
    SetSeed("ECL", "Lorwyn Eclipsed", date(2026, 1, 20), date(2026, 3, 2)),
    SetSeed("TMT", "Teenage Mutant Ninja Turtles", date(2026, 3, 3), date(2026, 4, 20)),
    SetSeed("SOS", "Secrets of Strixhaven", date(2026, 4, 21), date(2026, 6, 22)),
    SetSeed("MSH", "Marvel Super Heroes", date(2026, 6, 23), date(2026, 8, 10)),
)

ACTIVE_SET_CODE = "SOS"


def upcoming_sets() -> tuple[SetSeed, ...]:
    """Registered sets that rotate in after the active one — not yet the leaderboard set, but
    draftable for pod/mock previews. Empty once the active set is the newest entry."""
    codes = [s.code for s in ALL_SETS]
    if ACTIVE_SET_CODE not in codes:
        return ()
    return ALL_SETS[codes.index(ACTIVE_SET_CODE) + 1:]


def is_known_set(code: str) -> bool:
    return any(s.code == code.upper() for s in ALL_SETS)


@dataclass(frozen=True)
class CollectorBoosterWindow:
    set_code: str
    start_date: date
    end_date: date


# Arena Direct box payouts. Current (7-win format):
# - play booster direct: the trophy pays 2 boxes, a 6-win finish pays 1
# - collector booster direct: 1 box for the trophy
# History:
# - 2024 sets: play booster directs on a 6-win format, the trophy pays 2 boxes
# - DFT: collector booster direct on a 6-win format, 1 box for the trophy
# - TDM: the 7-win format rolled out mid-set, so its collector booster direct stayed at 6 wins
# boxes_for_event keys off 17lands is_trophy, so the win cap is never hardcoded.
SIX_WIN_PLAY_DIRECT_SETS = frozenset({"OTJ", "FDN", "BLB", "DSK"})
SIX_WIN_COLLECTOR_DIRECT_SETS = frozenset({"DFT"})

COLLECTOR_BOOSTER_WINDOWS: tuple[CollectorBoosterWindow, ...] = (
    CollectorBoosterWindow("TDM", date(2025, 4, 18), date(2025, 4, 20)),
    CollectorBoosterWindow("FIN", date(2025, 6, 20), date(2025, 6, 22)),
    CollectorBoosterWindow("EOE", date(2025, 8, 8), date(2025, 8, 11)),
    CollectorBoosterWindow("TLA", date(2025, 11, 28), date(2025, 11, 30)),
    CollectorBoosterWindow("ECL", date(2026, 1, 30), date(2026, 2, 1)),
    CollectorBoosterWindow("TMT", date(2026, 3, 13), date(2026, 3, 15)),
    CollectorBoosterWindow("SOS", date(2026, 4, 30), date(2026, 5, 4)),
)

# Windows widen by a day each side so a draft finished just before/after the
# scheduled weekend still resolves to the collector payout.
COLLECTOR_WINDOW_SLACK = timedelta(days=1)


def is_collector_booster_window(set_code: str, when: date) -> bool:
    for w in COLLECTOR_BOOSTER_WINDOWS:
        if w.set_code != set_code:
            continue
        if w.start_date - COLLECTOR_WINDOW_SLACK <= when <= w.end_date + COLLECTOR_WINDOW_SLACK:
            return True
    return False


@dataclass(frozen=True)
class PreviewWindow:
    set_code: str
    start_date: date
    end_date: date


# Spoiler-season day ranges, inclusive on both ends, interpreted in US Eastern time.
# Independent of ALL_SETS — a set gets its window before it joins the rotation.
PREVIEW_WINDOWS: tuple[PreviewWindow, ...] = (
    PreviewWindow("MSH", date(2026, 6, 2), date(2026, 6, 8)),
)


EXPANSION_ALIASES: dict[str, str] = {
    s.expansion_match: s.code for s in ALL_SETS if s.expansion_match
}


def normalize_expansion(expansion: str) -> str:
    return EXPANSION_ALIASES.get(expansion, expansion)


def set_name_for(code: str) -> str:
    """Full set name for a code (e.g. SOS -> "Secrets of Strixhaven"); the bare code if unknown."""
    upper = code.upper()
    for s in ALL_SETS:
        if s.code == upper:
            return s.name
    return upper
