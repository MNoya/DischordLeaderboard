"""Dump every episode with its PROPOSED multi-category classification for human review.

Writes ``episode-categories-review.md`` at the repo root. Read-only — it does not touch the DB
or the live single-category classifier. A throwaway artifact while the category taxonomy is being
settled: the three proposed axes are Set (one, or — for none), Evergreen (a flag), and Categories
(multi-valued). Run with DATABASE_URL pointed at the local DB.
"""
from __future__ import annotations

import re

from sqlalchemy import select

from bot.database import SessionLocal
from bot.media_sets import EVERGREEN, resolve_set
from bot.models import Episode

_SHORT_MAX_S = 90
_SHORT_HASHTAG_MAX_S = 180
_HASHTAG = re.compile(r"#\w")

_TITLE_CATEGORY_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("First Impressions", re.compile(r"primer|first impressions|first look", re.I)),
    ("State of the Format", re.compile(r"state of the format|format address|format update", re.I)),
    ("Set Review", re.compile(r"set review|tier list|ranking", re.I)),
    ("Draft", re.compile(r"draft-?along|draft log|live draft|drafting with", re.I)),
    ("Coaching", re.compile(r"coaching|draft class", re.I)),
)

_TOP_LIST = re.compile(r"\btop \d+", re.I)
_RANK_CONTEXT = re.compile(r"mythic|competitor|\bplayer\b|pro tour|\bpt\b|qualifier|arena direct", re.I)


def episode_type(kind: str, duration_seconds: int, title: str) -> str:
    if kind != "video" or duration_seconds <= 0:
        return "podcast" if kind == "episode" else "video"
    if duration_seconds <= _SHORT_MAX_S:
        return "short"
    if duration_seconds <= _SHORT_HASHTAG_MAX_S and _HASHTAG.search(title):
        return "short"
    return "video"


def is_evergreen(playlists: list[str]) -> bool:
    return any("evergreen" in p.lower() for p in playlists)


def resolve_categories(playlists: list[str], title: str, is_video: bool = False) -> list[str]:
    categories: list[str] = []
    for category in _categories_from_playlists(playlists) + _categories_from_title(title):
        if category not in categories:
            categories.append(category)
    if is_evergreen(playlists) and "Evergreen" not in categories:
        categories.append("Evergreen")
    if categories:
        return categories
    return ["Draft"] if is_video else ["Evergreen"]


def _categories_from_playlists(playlists: list[str]) -> list[str]:
    lowered = [p.lower() for p in playlists]
    found: list[str] = []
    if any("set review" in p for p in lowered):
        found.append("Set Review")
    if any("coaching" in p or "draft class" in p for p in lowered):
        found.append("Coaching")
    if any(re.search(r"\bdraft\b", p) and "coaching" not in p and "class" not in p for p in lowered):
        found.append("Draft")
    if any("top 10" in p for p in lowered):
        found.append("Top 10")
    return found


def _categories_from_title(title: str) -> list[str]:
    found = [name for name, pattern in _TITLE_CATEGORY_RULES if pattern.search(title)]
    if _TOP_LIST.search(title) and not _RANK_CONTEXT.search(title):
        found.append("Top 10")
    return found


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def main() -> None:
    with SessionLocal() as session:
        episodes = session.execute(select(Episode).order_by(Episode.published_at.desc())).scalars().all()

    lines = [
        "# Episode categorization review",
        "",
        f"{len(episodes)} episodes, newest first. Proposed model — **Set**: one value, or — for none "
        "(Evergreen is NOT a set); **Categories**: multi-valued, where `Evergreen` is the catch-all for "
        "set-agnostic content (from the Evergreen Episodes playlist, or when nothing else matches) and can "
        "co-occur with a set. `Playlists` is the source so you can check each derivation.",
        "",
        "| # | Date | Type | Set | Categories | Title | Playlists |",
        "|---|------|------|-----|-----------|-------|-----------|",
    ]
    for index, episode in enumerate(episodes, 1):
        playlists = episode.playlists or []
        media_set = resolve_set(playlists, episode.title)
        set_code = "—" if media_set.code == EVERGREEN.code else media_set.code
        kind = episode_type(episode.kind, episode.duration_seconds, episode.title)
        categories = ", ".join(resolve_categories(playlists, episode.title, is_video=kind == "video"))
        date = episode.published_at.strftime("%Y-%m-%d")
        playlist_cell = _cell(", ".join(playlists))
        lines.append(
            f"| {index} | {date} | {kind} | {set_code} | {categories} "
            f"| {_cell(episode.title)} | {playlist_cell} |"
        )

    with open("episode-categories-review.md", "w") as handle:
        handle.write("\n".join(lines) + "\n")
    print(f"wrote episode-categories-review.md ({len(episodes)} rows)")


if __name__ == "__main__":
    main()
