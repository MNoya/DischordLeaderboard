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


COLLECTOR_BOOSTER_WINDOWS: tuple[CollectorBoosterWindow, ...] = (
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
