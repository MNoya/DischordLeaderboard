from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bot import audit
from bot.config import settings
from bot.models import LeaderboardMessage, MagicSet, Player, PlayerSetScore, PlayerStats
from bot.sets import ACTIVE_SET_CODE

logger = logging.getLogger(__name__)


@dataclass
class LeaderboardEntry:
    rank: int
    player_id: str
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
    drafter_count: int = 0  # active players with at least one event in this set


def _current_set(session: Session) -> MagicSet | None:
    return session.execute(
        select(MagicSet).where(MagicSet.code == ACTIVE_SET_CODE)
    ).scalar_one_or_none()


def process_leaderboard(
    session: Session, viewer_discord_id: str | None, top_n: int = 10,
    include_zero_scores: bool = False,
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
    # Default view hides players with no points yet — they're "drafting but
    # not on the board". The full-DM view passes include_zero_scores=True
    # so signed-up players who haven't scored still appear
    visible = ranked if include_zero_scores else [row for row in ranked if row[4] > 0]
    top = [
        LeaderboardEntry(rank=rank, player_id=pid, display_name=name, score=score, trophies=trophies)
        for rank, pid, name, _did, score, trophies in visible[:top_n]
    ]

    viewer_entry: LeaderboardEntry | None = None
    if viewer_discord_id is not None:
        for rank, pid, name, did, score, trophies in ranked:
            if did == viewer_discord_id:
                viewer_entry = LeaderboardEntry(
                    rank=rank, player_id=pid, display_name=name, score=score, trophies=trophies,
                )
                break

    last_updated = session.execute(
        select(func.max(PlayerSetScore.last_calculated_at))
        .where(PlayerSetScore.set_id == magic_set.id)
    ).scalar()

    drafter_count = session.execute(
        select(func.count(func.distinct(PlayerStats.player_id)))
        .join(Player, Player.id == PlayerStats.player_id)
        .where(
            PlayerStats.set_id == magic_set.id,
            PlayerStats.events > 0,
            Player.active.is_(True),
        )
    ).scalar() or 0

    return LeaderboardData(
        set_code=magic_set.code,
        set_name=magic_set.name,
        top=top,
        viewer=viewer_entry,
        last_updated=last_updated,
        drafter_count=drafter_count,
    )


MEDAL_EMOJIS = {1: "🥇", 2: "🥈", 3: "🥉"}


def _player_url(player_id: str) -> str:
    """Build the public-site URL for a player's profile.

    The site doesn't exist yet — this URL pattern is reserved so leaderboard
    messages already in channels start working without a code change once
    the frontend ships.
    """
    return f"{settings.public_site_url.rstrip('/')}/player/{player_id}"


def _format_leaderboard(top: list[LeaderboardEntry]) -> str:
    """Wrap each row in inline code (single backticks) — renders as monospace
    without the code-block brick, and spaces are preserved so columns align.
    Same trick scoreboards.dev uses to get tabular layout in an embed.

    Scores are rounded to the nearest integer for display; tie-breaking still
    works because the underlying ORDER BY in process_leaderboard uses the raw
    float value, not this rendered string.
    """
    name_width = max(max(len(e.display_name) for e in top), len("Name"))
    score_width = max(max(len(f"{round(e.score)}") for e in top), len("Points"))
    trophy_width = max(max(len(str(e.trophies)) for e in top), 1)
    rank_col_width = max(max(len(f"{e.rank}.") for e in top), len("#"))
    # Trophy header emoji renders ~1 col wider than a digit, so pad header trophy field one less
    header_trophy_width = max(trophy_width - 1, 1)

    header_inner = (
        f"{'#':<{rank_col_width}} {'Name':<{name_width}}  "
        f"{'Points':>{score_width}}  {'🏆':>{header_trophy_width}}"
    )
    lines = [f"`{header_inner}`"]
    for e in top:
        medal = MEDAL_EMOJIS.get(e.rank)
        if medal is not None:
            # emoji takes ~1 col more than digit-pair in monospace rendering, so pad shorter
            rank = f"{medal:<{rank_col_width - 1}}"
        else:
            rank = f"{e.rank}.".ljust(rank_col_width)
        name = e.display_name.ljust(name_width)
        # Center the integer under the wider 'Points' header — right-bias so
        # single-digit values shift one space rightward and look more centered
        score = _center_right_bias(str(round(e.score)), score_width)
        trophy = f"{e.trophies:>{trophy_width}}"
        inner = f"{rank} {name}  {score}  {trophy}"
        lines.append(f"`{inner}`")
    return "\n".join(lines)


def _center_right_bias(s: str, width: int) -> str:
    """Center s in width chars, putting any leftover padding on the LEFT.

    Python's built-in centering biases right (extra space ends up on the right),
    which makes single-digit values inside wider header columns look offset to
    the left. Right-biasing the padding shifts those values one space rightward
    so they read closer to the column's visual center.
    """
    pad = max(0, width - len(s))
    right = pad // 2
    left = pad - right
    return ' ' * left + s + ' ' * right


def _apply_footer(embed: discord.Embed, data: LeaderboardData) -> None:
    """Two-line footer:

      Row 1: ``N active drafters``
      Row 2: ``Last updated | Today at HH:MM``  (timestamp appended by Discord)

    The clickable site link is on the embed title (via ``embed.url``); the URL
    no longer appears in the footer to avoid redundancy.
    """
    rows: list[str] = []
    if data.drafter_count > 0:
        label = "player" if data.drafter_count == 1 else "players"
        rows.append(f"{data.drafter_count} {label} sharing their stats · /join to add yours")
    if data.last_updated is not None:
        embed.timestamp = data.last_updated
        rows.append("Last updated")
    if rows:
        embed.set_footer(text="\n".join(rows))


def render_embed(data: LeaderboardData) -> discord.Embed:
    """Single leaderboard embed used everywhere — channel posts, DM replies,
    and post-/join previews.

    Personal context (rank, breakdown, /join prompt) lives in a separate
    stats embed sent alongside; collapsing the personalized variant removes
    the two-render-path maintenance cost.
    """
    embed = discord.Embed(
        title=f"🏆 Leaderboard — {data.set_code}",
        url=settings.public_site_url,
        color=discord.Color.gold(),
    )
    if not data.top:
        embed.description = "_No players have scored yet for this set._"
    else:
        embed.description = _format_leaderboard(data.top)
    _apply_footer(embed, data)
    return embed


# Alias kept so external callers asking for the 'public' variant still resolve;
# the personalized variant retired when stats embed took over the per-viewer info
render_public_embed = render_embed


async def _send_personal_followup(
    interaction: discord.Interaction, viewer_discord_id: str, viewer_registered: bool,
) -> None:
    """Ephemeral follow-up to the invoker — rich stats breakdown if signed up,
    /join prompt otherwise. Re-uses the /stats embed so the two commands stay
    visually consistent."""
    from bot.database import SessionLocal
    from bot.commands.stats import process_stats, render_embed as render_stats_embed

    if not viewer_registered:
        await interaction.followup.send(
            content="You're not on the leaderboard — run `/join` to join.",
            ephemeral=(interaction.guild is not None),
        )
        return
    with SessionLocal() as session:
        stats_data = process_stats(session, player_name=None, viewer_discord_id=viewer_discord_id)
    if stats_data is not None:
        await interaction.followup.send(embed=render_stats_embed(stats_data), ephemeral=(interaction.guild is not None))


class LeaderboardView(discord.ui.View):
    """Persistent view for leaderboard messages — buttons keep working across bot restarts.

    The Join button calls back into the Signup cog so it behaves identically to the
    /join slash command (DM-flow signup, reactivation, already-signed-up handling).
    The Stats button is a URL link handled client-side by Discord.
    """

    def __init__(self) -> None:
        super().__init__(timeout=None)
        # URL buttons are exempt from the persistent-view custom_id requirement
        self.add_item(discord.ui.Button(
            label="Stats", url=settings.public_site_url,
            style=discord.ButtonStyle.link,
        ))

    @discord.ui.button(label="Join", style=discord.ButtonStyle.primary, custom_id="leaderboard:join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Already signed-up users clicking Join are usually misclicks or curious
        # — show their personal stats instead of starting the signup flow
        from bot.database import SessionLocal

        user_id = str(interaction.user.id)
        with SessionLocal() as session:
            existing = session.execute(
                select(Player).where(
                    Player.discord_id == user_id, Player.active.is_(True),
                )
            ).scalar_one_or_none()

        if existing is not None:
            stats_cog = interaction.client.get_cog("Stats")
            if stats_cog is not None:
                await stats_cog.stats.callback(stats_cog, interaction)
                return

        signup_cog = interaction.client.get_cog("Signup")
        if signup_cog is None:
            await interaction.response.send_message(
                "Sign-up isn't available right now.", ephemeral=(interaction.guild is not None),
            )
            return
        await signup_cog.signup.callback(signup_cog, interaction)


def render_view() -> discord.ui.View:
    """Per-message instance of the leaderboard view (Join + Stats buttons)."""
    return LeaderboardView()


async def _replace_tracked_message(
    interaction: discord.Interaction,
    channel_id: str,
    set_id: str,
    embed: discord.Embed,
    view: discord.ui.View,
) -> None:
    """Post a fresh leaderboard in the channel and replace any prior tracked one.

    Behavior:
      1. Send the new message via interaction followup (deferred upstream).
      2. Best-effort delete the previously tracked message — if the user buried
         the old one, we want the new one at the bottom of the channel.
      3. Upsert the tracking row to point at the new message id.

    A NotFound on delete is normal (mod or user wiped it); we just move on.
    """
    from bot.database import SessionLocal

    sent = await interaction.followup.send(embed=embed, view=view, wait=True)

    with SessionLocal() as session:
        prior = session.execute(
            select(LeaderboardMessage).where(
                LeaderboardMessage.channel_id == channel_id,
                LeaderboardMessage.set_id == set_id,
            )
        ).scalar_one_or_none()
        prior_message_id = prior.message_id if prior is not None else None

        if prior is None:
            session.add(LeaderboardMessage(
                channel_id=channel_id, set_id=set_id, message_id=str(sent.id),
            ))
        else:
            prior.message_id = str(sent.id)
            prior.last_rendered_at = datetime.now(timezone.utc)
        session.commit()

    if prior_message_id is not None and prior_message_id != str(sent.id):
        try:
            old = await interaction.channel.fetch_message(int(prior_message_id))
            await old.delete()
        except discord.NotFound:
            pass
        except discord.HTTPException as e:
            logger.warning("could not delete prior leaderboard message %s: %s",
                           prior_message_id, e)


async def broadcast_current_set_update(bot: commands.Bot) -> dict:
    """Re-render every tracked leaderboard message for the currently active set.

    Wrapper used by callers (signup flow, !refresh) that just want 'reflect the
    latest data everywhere' without resolving the set themselves.
    """
    from bot.database import SessionLocal
    from bot.sets import ACTIVE_SET_CODE

    with SessionLocal() as session:
        ms = session.execute(
            select(MagicSet).where(MagicSet.code == ACTIVE_SET_CODE)
        ).scalar_one_or_none()
        if ms is None:
            return {"edited": 0, "pruned": 0, "errors": 0}
        return await edit_tracked_messages_for_set(bot, ms)


async def edit_tracked_messages_for_set(bot: commands.Bot, magic_set: MagicSet) -> dict:
    """Refresh the rendered embed of every tracked leaderboard message for ``magic_set``.

    Used by ``!refresh`` (and any future periodic job) to keep posted leaderboards
    live without requiring users to re-invoke ``/leaderboard``. Stale tracking
    rows (message deleted in Discord) get pruned automatically.
    """
    from bot.database import SessionLocal

    summary = {"edited": 0, "pruned": 0, "errors": 0}
    with SessionLocal() as session:
        rows = session.execute(
            select(LeaderboardMessage).where(LeaderboardMessage.set_id == magic_set.id)
        ).scalars().all()
        targets = [(r.id, r.channel_id, r.message_id) for r in rows]

    if not targets:
        return summary

    with SessionLocal() as session:
        data = process_leaderboard(session, viewer_discord_id=None)
    if data is None:
        return summary
    embed = render_public_embed(data)
    view = render_view()

    for row_id, channel_id, message_id in targets:
        try:
            channel = bot.get_channel(int(channel_id)) or await bot.fetch_channel(int(channel_id))
            msg = await channel.fetch_message(int(message_id))
            # Pass content=None to strip any prior message-content variant (transient format)
            await msg.edit(content=None, embed=embed, view=view)
            with SessionLocal() as session:
                tracked = session.get(LeaderboardMessage, row_id)
                if tracked is not None:
                    tracked.last_rendered_at = datetime.now(timezone.utc)
                    session.commit()
            summary["edited"] += 1
        except discord.NotFound:
            with SessionLocal() as session:
                tracked = session.get(LeaderboardMessage, row_id)
                if tracked is not None:
                    session.delete(tracked)
                    session.commit()
            summary["pruned"] += 1
        except discord.HTTPException as e:
            logger.warning("could not edit leaderboard message %s in channel %s: %s",
                           message_id, channel_id, e)
            summary["errors"] += 1
    return summary


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
            magic_set = _current_set(session)

        if data is None or magic_set is None:
            await interaction.response.send_message(
                "No active set is configured. `bot/sets.py::ACTIVE_SET_CODE` doesn't match any registered set.",
                ephemeral=(interaction.guild is not None),
            )
            return

        # In a guild channel: replace any tracked leaderboard message in this channel
        # so the new post lands at the bottom rather than spamming alongside the prior.
        # In a DM: single ephemeral, fully personalized.
        in_guild = interaction.guild is not None
        if in_guild:
            await interaction.response.defer()
            await _replace_tracked_message(
                interaction,
                channel_id=str(interaction.channel_id),
                set_id=magic_set.id,
                embed=render_public_embed(data),
                view=render_view(),
            )
            await _send_personal_followup(
                interaction,
                viewer_discord_id=user_id,
                viewer_registered=data.viewer is not None,
            )
        else:
            # In DM: send leaderboard as the interaction response, then the stats
            # embed (or /join prompt) via dm.send so it doesn't visually thread as
            # a reply under the leaderboard message.
            await interaction.response.send_message(
                embed=render_embed(data), view=render_view(),
            )
            try:
                dm = interaction.channel  # already a DM channel here
                if data.viewer is not None:
                    from bot.commands.stats import process_stats, render_embed as render_stats_embed
                    from bot.database import SessionLocal as _SessionLocal
                    with _SessionLocal() as session:
                        stats_data = process_stats(session, player_name=None, viewer_discord_id=user_id)
                    if stats_data is not None:
                        await dm.send(embed=render_stats_embed(stats_data))
                else:
                    await dm.send("You're not on the leaderboard — run `/join` to join.")
            except Exception:
                logger.warning("/leaderboard DM personal followup failed", exc_info=True)

    @app_commands.command(
        name="leaderboard-full",
        description="DM you the entire leaderboard.",
    )
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def leaderboard_full(self, interaction: discord.Interaction) -> None:
        from bot.database import SessionLocal

        user_id = str(interaction.user.id)
        audit.event("leaderboard_full_invoked", user_id=user_id)

        with SessionLocal() as session:
            data = process_leaderboard(
                session, viewer_discord_id=user_id,
                top_n=10**6, include_zero_scores=True,
            )

        if data is None:
            await interaction.response.send_message(
                "No active set is configured. `bot/sets.py::ACTIVE_SET_CODE` doesn't match any registered set.",
            )
            return

        await interaction.response.send_message(
            embed=render_embed(data), view=render_view(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))
