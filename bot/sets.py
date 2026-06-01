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
from datetime import date


@dataclass(frozen=True)
class SetSeed:
    code: str
    name: str
    start_date: date
    end_date: date | None
    expansion_match: str | None = None


ALL_SETS: tuple[SetSeed, ...] = (
    SetSeed("KHM", "Kaldheim",                     date(2021,  1, 28), date(2021,  4, 14)),
    SetSeed("STX", "Strixhaven: School of Mages",  date(2021,  4, 15), date(2021,  7,  7)),
    SetSeed("WOE", "Wilds of Eldraine",            date(2023,  9,  5), date(2023, 11, 13)),
    SetSeed("LCI", "The Lost Caverns of Ixalan",   date(2023, 11, 14), date(2024,  2,  5)),
    SetSeed("MKM", "Murders at Karlov Manor",      date(2024,  2,  6), date(2024,  4, 15)),
    SetSeed("OTJ", "Outlaws of Thunder Junction",  date(2024,  4, 16), date(2024,  7, 29)),
    SetSeed("BLB", "Bloomburrow",                  date(2024,  7, 30), date(2024,  9, 23)),
    SetSeed("DSK", "Duskmourn: House of Horror",   date(2024,  9, 24), date(2024, 11, 11)),
    SetSeed("FDN", "Foundations",                  date(2024, 11, 12), date(2025,  2, 10)),
    SetSeed("DFT", "Aetherdrift",                  date(2025,  2, 11), date(2025,  4,  7)),
    SetSeed("TDM", "Tarkir: Dragonstorm",          date(2025,  4,  8), date(2025,  6,  8)),
    SetSeed("FIN", "Final Fantasy",                date(2025,  6,  9), date(2025,  7, 28)),
    SetSeed("EOE", "Edge of Eternities",           date(2025,  7, 29), date(2025,  9, 23)),
    SetSeed("CUBE", "Arena Powered Cube",          date(2025, 10, 28), None, expansion_match="Cube - Powered"),
    SetSeed("TLA", "Avatar: The Last Airbender",   date(2025, 11, 16), date(2026,  1, 19)),
    SetSeed("ECL", "Lorwyn Eclipsed",              date(2026,  1, 20), date(2026,  3,  2)),
    SetSeed("TMT", "Teenage Mutant Ninja Turtles", date(2026,  3,  3), date(2026,  4, 20)),
    SetSeed("SOS", "Secrets of Strixhaven",        date(2026,  4, 21), date(2026,  6, 22)),
)

ACTIVE_SET_CODE = "SOS"


@dataclass(frozen=True)
class CollectorBoosterWindow:
    set_code: str
    start_date: date
    end_date: date


# Arena Direct's box payout changed across three eras.
# 2024 sets capped at 6 wins, where the 6-win trophy paid 2 Play Booster boxes.
# DFT's premiere instead paid 1 Collector box at its 6-win trophy.
# From April 2025 the ladder extended to 7 wins, paying 2 boxes at 7 and 1 at 6.
# Collector Booster premiere weekends instead pay 1 box at 7 wins and nothing at 6.
SIX_WIN_PLAY_DIRECT_SETS = frozenset({"OTJ", "FDN", "BLB", "DSK"})
SIX_WIN_COLLECTOR_DIRECT_SETS = frozenset({"DFT"})

COLLECTOR_BOOSTER_WINDOWS: tuple[CollectorBoosterWindow, ...] = (
    CollectorBoosterWindow("TDM", date(2025, 4, 18), date(2025, 4, 21)),
    CollectorBoosterWindow("FIN", date(2025, 6, 20), date(2025, 6, 22)),
    CollectorBoosterWindow("EOE", date(2025, 8, 8), date(2025, 8, 11)),
    CollectorBoosterWindow("ECL", date(2026, 1, 30), date(2026, 2, 1)),
    CollectorBoosterWindow("SOS", date(2026, 4, 30), date(2026, 5, 4)),
)


def is_collector_booster_window(set_code: str, when: date) -> bool:
    for w in COLLECTOR_BOOSTER_WINDOWS:
        if w.set_code == set_code and w.start_date <= when <= w.end_date:
            return True
    return False


EXPANSION_ALIASES: dict[str, str] = {
    s.expansion_match: s.code for s in ALL_SETS if s.expansion_match
}


def normalize_expansion(expansion: str) -> str:
    return EXPANSION_ALIASES.get(expansion, expansion)
