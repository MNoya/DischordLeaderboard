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


ALL_SETS: tuple[SetSeed, ...] = (
    SetSeed("FIN", "Final Fantasy",              date(2025,  6, 10), date(2025, 11, 17)),
    SetSeed("TLA", "Avatar: The Last Airbender", date(2025, 11, 18), date(2026,  1, 19)),
    SetSeed("ECL", "Lorwyn Eclipsed",            date(2026,  1, 20), date(2026,  4, 20)),
    SetSeed("SOS", "Secrets of Strixhaven",      date(2026,  4, 21), date(2026,  6, 22)),
)

ACTIVE_SET_CODE = "SOS"
