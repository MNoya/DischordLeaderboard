from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import discord
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bot.config import settings
from bot.models import DraftEvent, MagicSet, Player, PlayerStats
from bot.scoring import boxes_for_event, compute_score, compute_score_breakdown
from bot.services.pod_drafts import player_pod_stats
from bot.sets import ACTIVE_SET_CODE


@dataclass
class StatsData:
    set_code: str
    set_name: str
    player_name: str
    player_slug: str
    rank: int | None
    total_score: float
    total_trophies: int
    breakdown: list[dict] = field(default_factory=list)
    last_updated: datetime | None = None
    pod_stats: dict | None = None
    direct_stats: dict | None = None
    opted_out: bool = False
    has_token: bool = False


def process_stats(
    session: Session,
    player_name: str | None,
    viewer_discord_id: str,
    set_code: str = ACTIVE_SET_CODE,
) -> StatsData | None:
    player = resolve_player(session, player_name, viewer_discord_id)
    if player is None:
        return None

    magic_set = session.execute(
        select(MagicSet).where(MagicSet.code == set_code)
    ).scalar_one_or_none()
    if magic_set is None:
        return None

    stats_rows = session.execute(
        select(PlayerStats).where(
            PlayerStats.player_id == player.id,
            PlayerStats.set_id == magic_set.id,
        )
    ).scalars().all()
    stat_dicts = [
        {"format": r.format, "events": r.events, "wins": r.wins, "losses": r.losses, "trophies": r.trophies}
        for r in stats_rows
    ]
    breakdown = compute_score_breakdown(stat_dicts)
    total_score = compute_score(stat_dicts)
    total_trophies = sum(int(r.trophies or 0) for r in stats_rows)
    last_updated = max((r.last_fetched_at for r in stats_rows if r.last_fetched_at), default=None)

    rank: int | None = None
    if total_score > 0:
        for entry in rank_players_for_set(session, magic_set.id):
            if entry[1] == player.id:
                rank = entry[0]
                break

    pod = player_pod_stats(session, player.discord_id)
    pod_bucket = pod["by_set"].get(magic_set.code) if pod else None
    pod_stats = pod if pod_bucket and pod_bucket["events"] > 0 else None

    direct_rows = session.execute(
        select(DraftEvent.wins, DraftEvent.losses, DraftEvent.finished_at).where(
            DraftEvent.player_id == player.id,
            DraftEvent.set_id == magic_set.id,
            DraftEvent.format == "ArenaDirect_Sealed",
        )
    ).all()
    direct_stats: dict | None = None
    if direct_rows:
        wins = sum(int(r.wins or 0) for r in direct_rows)
        losses = sum(int(r.losses or 0) for r in direct_rows)
        boxes = sum(boxes_for_event(magic_set.code, int(r.wins or 0), r.finished_at) for r in direct_rows)
        direct_stats = {"events": len(direct_rows), "wins": wins, "losses": losses, "boxes": boxes}

    return StatsData(
        set_code=magic_set.code,
        set_name=magic_set.name,
        player_name=player.display_name,
        player_slug=player.slug,
        rank=rank,
        total_score=total_score,
        total_trophies=total_trophies,
        breakdown=breakdown,
        last_updated=last_updated,
        pod_stats=pod_stats,
        direct_stats=direct_stats,
        opted_out=not player.leaderboard_opt_in,
        has_token=player.seventeenlands_token is not None,
    )


def profile_url(data: StatsData) -> str:
    return f"{settings.public_site_url.rstrip('/')}/{data.set_code}/player/{data.player_slug}"


def render_embed(data: StatsData) -> discord.Embed:
    embed = discord.Embed(
        title=f"📊 Stats — {data.player_name} — {data.set_code}",
        url=profile_url(data),
        color=discord.Color.blurple(),
    )
    if data.opted_out:
        summary = f"{data.total_trophies} 🏆"
    elif data.rank is not None:
        summary = f"Rank **#{data.rank}** • **{data.total_score:.1f} pts** • {data.total_trophies} 🏆"
    else:
        summary = "_Not yet on the leaderboard for this set._"

    embed.description = f"{summary}\n\n{_format_breakdown(data.breakdown, data.direct_stats, data.opted_out)}"

    if data.pod_stats:
        b = data.pod_stats["by_set"].get(data.set_code)
        if b and b["events"]:
            games = b["wins"] + b["losses"]
            wr = b["wins"] / games if games else 0.0
            events_word = "event" if b["events"] == 1 else "events"
            trophy_word = "trophy" if b["trophies"] == 1 else "trophies"
            embed.description = (
                f"{embed.description}\n"
                f"**Pod** — {b['events']} {events_word}, "
                f"{b['wins']}-{b['losses']} ({wr:.0%}), "
                f"{b['trophies']} {trophy_word}"
            )

    if data.last_updated is not None:
        embed.timestamp = data.last_updated
        embed.set_footer(text=f"{data.set_code} • Last updated")
    else:
        embed.set_footer(text=data.set_code)
    return embed


def rank_players_for_set(
    session: Session, set_id: str,
) -> list[tuple[int, str, str, str, str | None, float, int]]:
    """Compute every active, opted-in player's score for the set from PlayerStats; sort and rank.

    Returns (rank, player_id, slug, display_name, discord_id, score, trophies) per player.
    Shared by the /stats and /leaderboard surfaces.
    """
    rows = session.execute(
        select(
            Player.id, Player.slug, Player.display_name, Player.discord_id,
            PlayerStats.format, PlayerStats.events, PlayerStats.wins,
            PlayerStats.losses, PlayerStats.trophies,
        )
        .join(PlayerStats, PlayerStats.player_id == Player.id)
        .where(
            Player.active.is_(True),
            Player.leaderboard_opt_in.is_(True),
            PlayerStats.set_id == set_id,
        )
    ).all()

    bucket: dict[str, dict] = {}
    for r in rows:
        b = bucket.setdefault(r.id, {
            "slug": r.slug, "display_name": r.display_name, "discord_id": r.discord_id,
            "stats": [], "trophies": 0,
        })
        b["stats"].append({
            "format": r.format, "events": int(r.events or 0),
            "wins": int(r.wins or 0), "losses": int(r.losses or 0),
            "trophies": int(r.trophies or 0),
        })
        b["trophies"] += int(r.trophies or 0)

    scored = [
        (compute_score(b["stats"]), b["trophies"], pid, b["slug"], b["display_name"], b["discord_id"])
        for pid, b in bucket.items()
    ]
    scored.sort(key=lambda x: (-x[0], x[4].lower()))
    return [
        (idx + 1, pid, slug, name, did, score, trophies)
        for idx, (score, trophies, pid, slug, name, did) in enumerate(scored)
    ]


def resolve_player(session: Session, player_name: str | None, viewer_discord_id: str) -> Player | None:
    if player_name:
        return session.execute(
            select(Player).where(
                func.lower(Player.display_name) == player_name.lower(),
                Player.active.is_(True),
            )
        ).scalar_one_or_none()
    return session.execute(
        select(Player).where(Player.discord_id == viewer_discord_id)
    ).scalar_one_or_none()


def _format_breakdown(breakdown: list[dict], direct_stats: dict | None = None, opted_out: bool = False) -> str:
    if not breakdown:
        return "_No drafts logged yet for this set._"
    lines: list[str] = []
    for b in breakdown:
        games = b["wins"] + b["losses"]
        winrate = b["wins"] / games if games > 0 else 0.0
        events_word = "event" if b["events"] == 1 else "events"
        trophy_word = "trophy" if b["trophies"] == 1 else "trophies"
        score_suffix = "" if opted_out else f" → {b['score']:.1f} pts"
        lines.append(
            f"**{b['label']}** — {b['events']} {events_word}, "
            f"{b['wins']}-{b['losses']} ({winrate:.0%}), "
            f"{b['trophies']} {trophy_word}{score_suffix}"
        )
        if b["label"] == "Sealed" and direct_stats is not None:
            d_events = direct_stats["events"]
            d_wins = direct_stats["wins"]
            d_losses = direct_stats["losses"]
            d_boxes = direct_stats["boxes"]
            d_games = d_wins + d_losses
            d_winrate = d_wins / d_games if d_games > 0 else 0.0
            events_word = "event" if d_events == 1 else "events"
            box_word = "box" if d_boxes == 1 else "boxes"
            lines.append(
                f"↳ **Direct** — {d_events} {events_word}, "
                f"{d_wins}-{d_losses} ({d_winrate:.0%}), "
                f"{d_boxes} {box_word}"
            )
    return "\n".join(lines)
