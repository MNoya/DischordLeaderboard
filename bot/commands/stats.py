from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bot import audit
from bot.config import settings
from bot.database import SessionLocal
from bot.models import MagicSet, Player, PlayerSetScore, PlayerStats
from bot.scoring import compute_score_breakdown
from bot.services.pod_drafts import player_pod_stats
from bot.sets import ACTIVE_SET_CODE

logger = logging.getLogger(__name__)


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
    pod_in_set: dict | None = None


def _resolve_player(session: Session, player_name: str | None, viewer_discord_id: str) -> Player | None:
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


def process_stats(
    session: Session,
    player_name: str | None,
    viewer_discord_id: str,
) -> StatsData | None:
    player = _resolve_player(session, player_name, viewer_discord_id)
    if player is None:
        return None

    magic_set = session.execute(
        select(MagicSet).where(MagicSet.code == ACTIVE_SET_CODE)
    ).scalar_one_or_none()
    if magic_set is None:
        return None

    stats_rows = session.execute(
        select(PlayerStats).where(
            PlayerStats.player_id == player.id,
            PlayerStats.set_id == magic_set.id,
        )
    ).scalars().all()
    breakdown = compute_score_breakdown([
        {"format": r.format, "events": r.events, "wins": r.wins, "losses": r.losses, "trophies": r.trophies}
        for r in stats_rows
    ])

    score_row = session.execute(
        select(PlayerSetScore).where(
            PlayerSetScore.player_id == player.id,
            PlayerSetScore.set_id == magic_set.id,
        )
    ).scalar_one_or_none()

    total_score = float(score_row.score) if score_row else 0.0
    total_trophies = int(score_row.trophies) if score_row else 0
    last_updated = score_row.last_calculated_at if score_row else None

    rank: int | None = None
    if score_row is not None:
        higher_count = session.execute(
            select(func.count())
            .select_from(PlayerSetScore)
            .join(Player, Player.id == PlayerSetScore.player_id)
            .where(
                Player.active.is_(True),
                PlayerSetScore.set_id == magic_set.id,
                PlayerSetScore.score > score_row.score,
            )
        ).scalar()
        rank = (higher_count or 0) + 1

    pod = player_pod_stats(session, player.discord_id)
    pod_in_set = pod["by_set"].get(magic_set.code) if pod else None

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
        pod_in_set=pod_in_set,
    )


def _format_breakdown(breakdown: list[dict]) -> str:
    if not breakdown:
        return "_No drafts logged yet for this set._"
    lines: list[str] = []
    for b in breakdown:
        games = b["wins"] + b["losses"]
        winrate = b["wins"] / games if games > 0 else 0.0
        events_word = "event" if b["events"] == 1 else "events"
        trophy_word = "trophy" if b["trophies"] == 1 else "trophies"
        lines.append(
            f"**{b['label']}** — {b['events']} {events_word}, "
            f"{b['wins']}-{b['losses']} ({winrate:.0%}), "
            f"{b['trophies']} {trophy_word} → {b['score']:.1f} pts"
        )
    return "\n".join(lines)


def render_embed(data: StatsData) -> discord.Embed:
    profile_url = f"{settings.public_site_url.rstrip('/')}/{data.set_code}/player/{data.player_slug}"
    embed = discord.Embed(
        title=f"📊 Stats — {data.player_name}",
        url=profile_url,
        color=discord.Color.blurple(),
    )
    if data.rank is not None:
        summary = f"Rank **#{data.rank}** • **{data.total_score:.1f} pts** • {data.total_trophies} 🏆"
    else:
        summary = "_Not yet on the leaderboard for this set._"

    embed.description = f"{summary}\n\n{_format_breakdown(data.breakdown)}"

    if data.pod_in_set and data.pod_in_set["events"]:
        p = data.pod_in_set
        games = p["wins"] + p["losses"]
        winrate = p["wins"] / games if games else 0.0
        events_word = "event" if p["events"] == 1 else "events"
        trophy_word = "trophy" if p["trophies"] == 1 else "trophies"
        pod_line = (
            f"**Pod** — {p['events']} {events_word}, "
            f"{p['wins']}-{p['losses']} ({winrate:.0%}), "
            f"{p['trophies']} {trophy_word}"
        )
        embed.description = f"{embed.description}\n{pod_line}"

    if data.last_updated is not None:
        embed.timestamp = data.last_updated
        embed.set_footer(text=f"{data.set_code} • Last updated")
    else:
        embed.set_footer(text=data.set_code)
    return embed


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="stats", description="See your stats breakdown for the current set.")
    @app_commands.describe(player="Player display name to look up (defaults to you)")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def stats(
        self, interaction: discord.Interaction, player: str | None = None
    ) -> None:
        user_id = str(interaction.user.id)
        audit.event("stats_invoked", user_id=user_id, player=player)

        with SessionLocal() as session:
            data = process_stats(session, player_name=player, viewer_discord_id=user_id)

        if data is None:
            if player:
                msg = f"No active player found with display name `{player}`."
            else:
                msg = "You're not on the leaderboard. Run `/join` to get started."
            await interaction.response.send_message(msg, ephemeral=(interaction.guild is not None))
            return

        await interaction.response.send_message(embed=render_embed(data), ephemeral=(interaction.guild is not None))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Stats(bot))
