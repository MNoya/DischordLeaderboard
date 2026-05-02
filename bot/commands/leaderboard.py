from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bot import audit
from bot.config import settings
from bot.models import MagicSet, Player, PlayerSetScore

logger = logging.getLogger(__name__)


@dataclass
class LeaderboardEntry:
    rank: int
    display_name: str
    score: float
    trophies: int


@dataclass
class LeaderboardData:
    set_code: str
    set_name: str
    top: list[LeaderboardEntry]
    viewer: LeaderboardEntry | None
    last_updated: datetime | None = None


def _current_set(session: Session) -> MagicSet | None:
    return session.execute(
        select(MagicSet).where(MagicSet.code == settings.current_set_code)
    ).scalar_one_or_none()


def process_leaderboard(
    session: Session, viewer_discord_id: str | None, top_n: int = 8
) -> LeaderboardData | None:
    magic_set = _current_set(session)
    if magic_set is None:
        return None

    rows = session.execute(
        select(Player.id, Player.display_name, Player.discord_id,
               PlayerSetScore.score, PlayerSetScore.trophies)
        .join(PlayerSetScore, PlayerSetScore.player_id == Player.id)
        .where(Player.active.is_(True), PlayerSetScore.set_id == magic_set.id)
        .order_by(PlayerSetScore.score.desc(), Player.display_name.asc())
    ).all()

    ranked = [
        (idx + 1, r.id, r.display_name, r.discord_id, float(r.score), int(r.trophies))
        for idx, r in enumerate(rows)
    ]
    top = [
        LeaderboardEntry(rank=rank, display_name=name, score=score, trophies=trophies)
        for rank, _id, name, _did, score, trophies in ranked[:top_n]
    ]

    viewer_entry: LeaderboardEntry | None = None
    if viewer_discord_id is not None:
        for rank, _id, name, did, score, trophies in ranked:
            if did == viewer_discord_id:
                viewer_entry = LeaderboardEntry(
                    rank=rank, display_name=name, score=score, trophies=trophies,
                )
                break

    last_updated = session.execute(
        select(func.max(PlayerSetScore.last_calculated_at))
        .where(PlayerSetScore.set_id == magic_set.id)
    ).scalar()

    return LeaderboardData(
        set_code=magic_set.code,
        set_name=magic_set.name,
        top=top,
        viewer=viewer_entry,
        last_updated=last_updated,
    )


def _format_row(e: LeaderboardEntry, name_width: int, score_width: int, trophy_width: int, rank_col_width: int, highlight: bool = False) -> str:
    name = e.display_name[:name_width]
    rank_label = f"{e.rank}."
    line = f"{rank_label:<{rank_col_width}} {name:<{name_width}}  {e.score:>{score_width}.1f}  {e.trophies:>{trophy_width}}"
    if highlight:
        line += "  <-"
    return line


def _format_table(top: list[LeaderboardEntry], viewer: LeaderboardEntry | None) -> str:
    name_width = max([len(e.display_name) for e in top] + [len("Player")])
    score_width = max([len(f"{e.score:.1f}") for e in top] + [len("Pts")])
    # Trophy column padded to at least 2 so single-digit values roughly match the emoji's visual width
    trophy_width = max([len(str(e.trophies)) for e in top] + [2])
    # Header trophy field is 1 char narrower because the emoji renders ~1 col wider than a digit
    header_trophy_width = max(trophy_width - 1, 1)
    # Rank column width covers "#." header and the longest "N." rank label
    rank_col_width = max([len(f"{e.rank}.") for e in top] + [len("#.")])

    header = f"{'#.':<{rank_col_width}} {'Player':<{name_width}}  {'Pts':>{score_width}}  {'🏆':>{header_trophy_width}}"
    sep = "-" * (len(header) + 1)

    lines = [header, sep]
    for e in top:
        highlight = viewer is not None and e.rank == viewer.rank
        lines.append(_format_row(e, name_width, score_width, trophy_width, rank_col_width, highlight))

    return "```\n" + "\n".join(lines) + "\n```"


def render_embed(data: LeaderboardData) -> discord.Embed:
    embed = discord.Embed(
        title=f"🏆 Leaderboard — {data.set_name}",
        color=discord.Color.gold(),
    )
    if not data.top:
        embed.description = "No players have stats yet for this set."
    else:
        description = _format_table(data.top, data.viewer)
        # Viewer summary lives outside the code block so we can use bold/emoji
        if data.viewer is not None:
            viewer_in_top = any(e.rank == data.viewer.rank for e in data.top)
            if not viewer_in_top:
                description += (
                    f"\n**You are #{data.viewer.rank}** — "
                    f"{data.viewer.score:.1f} pts • {data.viewer.trophies} 🏆"
                )
        embed.description = description

    if data.viewer is None:
        embed.add_field(
            name="Not signed up",
            value="Run `/join` to appear on the leaderboard!",
            inline=False,
        )

    if data.last_updated is not None:
        embed.timestamp = data.last_updated
        embed.set_footer(text="Last updated")
    return embed


def render_view() -> discord.ui.View:
    """Single 'Stats' link button pointing at the public website."""
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Stats", url=settings.public_site_url, style=discord.ButtonStyle.link))
    return view


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Show the current set leaderboard.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        from bot.database import SessionLocal

        user_id = str(interaction.user.id)
        audit.event("leaderboard_invoked", user_id=user_id)

        with SessionLocal() as session:
            data = process_leaderboard(session, viewer_discord_id=user_id)

        if data is None:
            await interaction.response.send_message(
                "No active set is configured. The bot's `CURRENT_SET_CODE` doesn't match any registered set.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=render_embed(data), view=render_view(), ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))
