"""Format groups and scoring formula for player rating.

Carries forward the legacy ECL formula:

    group_score = trophies × group_points × trophy_rate × t/(t+2)
    total = sum across groups

with a special case for LCQ Draft 2 (counts wins instead of trophies, uses winrate).

A ``QueueGroup`` collects raw 17lands ``format`` strings under a single label
that shares a points weight. The ``Sealed`` group rolls best-of-1 and
best-of-3 sealed under one entry — sealed is sealed for scoring purposes. LCQ
groups sit dormant until WOTC actually runs LCQ events for the season.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class QueueGroup:
    label: str
    points: int
    formats: tuple[str, ...]
    # None = standard formula; "lcq_draft_2" = wins-not-trophies × winrate × points
    rule: str | None = None


DEFAULT_QUEUE_GROUPS: tuple[QueueGroup, ...] = (
    QueueGroup("Premier", points=10, formats=("PremierDraft",)),
    QueueGroup("Traditional", points=9, formats=("TradDraft",)),
    QueueGroup("Sealed", points=8, formats=("Sealed", "TradSealed", "ArenaDirect_Sealed", "QualifierPlayInSealed")),
    QueueGroup("Quick", points=3, formats=("QuickDraft", "PickTwoDraft", "Emblem_QuickDraft")),
    QueueGroup("LCQ Draft 1", points=30, formats=("LimitedChampionshipQualifier_Draft1",)),
    QueueGroup(
        "LCQ Draft 2",
        points=10,
        formats=("LimitedChampionshipQualifier_Draft2",),
        rule="lcq_draft_2",
    ),
)


def supported_formats(groups: Iterable[QueueGroup] = DEFAULT_QUEUE_GROUPS) -> tuple[str, ...]:
    return tuple(fmt for g in groups for fmt in g.formats)


def _group_for_format(groups: Iterable[QueueGroup], fmt: str) -> QueueGroup | None:
    for g in groups:
        if fmt in g.formats:
            return g
    return None


def compute_score_breakdown(
    stats_rows: Sequence[dict],
    groups: Iterable[QueueGroup] = DEFAULT_QUEUE_GROUPS,
) -> list[dict]:
    """Per-group totals + score contribution. Skips groups with no matching rows."""
    grouped: dict[str, list[dict]] = {}
    groups_list = list(groups)
    for row in stats_rows:
        g = _group_for_format(groups_list, row["format"])
        if g is None:
            continue
        grouped.setdefault(g.label, []).append(row)

    breakdown: list[dict] = []
    for g in groups_list:
        rows = grouped.get(g.label)
        if not rows:
            continue
        breakdown.append({
            "label": g.label,
            "events": sum(r.get("events", 0) for r in rows),
            "wins": sum(r.get("wins", 0) for r in rows),
            "losses": sum(r.get("losses", 0) for r in rows),
            "trophies": sum(r.get("trophies", 0) for r in rows),
            "score": compute_score(rows, groups=(g,)),
        })
    return breakdown


def compute_score(
    stats_rows: Sequence[dict],
    groups: Iterable[QueueGroup] = DEFAULT_QUEUE_GROUPS,
) -> float:
    """Total score for one player across all their group-rolled stats.

    ``stats_rows`` items are dicts with keys: format, wins, losses, trophies, events.
    Rows whose format isn't in any group are ignored.
    """
    grouped: dict[str, list[dict]] = {}
    for row in stats_rows:
        g = _group_for_format(groups, row["format"])
        if g is None:
            continue
        grouped.setdefault(g.label, []).append(row)

    total = 0.0
    for g in groups:
        rows = grouped.get(g.label)
        if not rows:
            continue
        if g.rule == "lcq_draft_2":
            wins = sum(r.get("wins", 0) for r in rows)
            losses = sum(r.get("losses", 0) for r in rows)
            games = wins + losses
            if games == 0 or wins == 0:
                continue
            winrate = wins / games
            total += wins * winrate * g.points
            continue

        trophies = sum(r.get("trophies", 0) for r in rows)
        events = sum(r.get("events", 0) for r in rows)
        if trophies == 0 or events == 0:
            continue
        trophy_rate = trophies / events
        shrinkage = trophies / (trophies + 2)
        total += trophies * g.points * trophy_rate * shrinkage

    return round(total, 2)
