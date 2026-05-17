from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm import Session

from bot import audit
from bot.commands.leaderboard import (
    broadcast_current_set_update,
    process_leaderboard,
    render_embed as render_lb,
    render_view as render_lb_view,
)
from bot.commands.stats import process_stats, render_embed as render_stats_embed
from bot.database import SessionLocal
from bot.discord_helpers import extract_avatar_hash
from bot.models import Player
from bot.services.refresh import refresh_one_player_for_all_sets
from bot.services.seventeenlands import SeventeenLandsClient, extract_token
from bot.slug import disambiguate_slug, slugify

logger = logging.getLogger(__name__)

DM_TIMEOUT_S = 10 * 60

# Optional walkthrough image attached to the signup DM. Drop a screenshot at
# this path (highlighting the 'event history' link on 17lands.com/history/events)
# and the bot will include it; if the file is missing the DM is text-only.
INSTRUCTIONS_IMAGE = Path(__file__).resolve().parents[2] / "bot" / "assets" / "signup_event_history.png"

INSTRUCTIONS = (
    "**Welcome to the LLU Community Leaderboard!**\n"
    "Join by sharing your **17lands profile link**.\n"
    "1. Go to [17lands.com/history/events](https://www.17lands.com/history/events)\n"
    "2. Click the *event history* link.\n"
    "3. Copy the URL from your browser's address bar. It looks like:\n"
    "`https://www.17lands.com/user_history/abc123...` (any `?...` extras at the end are fine)\n"
    "4. Reply to this message with the full URL or just the token.\n"
    "\n"
    "*Your token is stored securely and only used to fetch your game stats for the leaderboard.*"
)

MSG_DM_SENT = "📬 Check your DMs to join!"
MSG_ALREADY_IN_PROGRESS = "Your /join is already in progress — check your DMs and reply there."
MSG_ALREADY_SIGNED_UP = (
    "You're already in! 🎉 Use `/relink` if you ever need to change your 17lands link."
)
MSG_WELCOME_BACK = "👋 Welcome back! Stats refreshed — you're on the leaderboard again."
MSG_INVALID_FORMAT = "That doesn't look like a valid 17lands token. Please check the URL and try again."
MSG_REJECTED = "That token couldn't be verified with 17lands. Please double-check your URL and try again."
MSG_DMS_DISABLED = (
    "⚠️ DMs are blocked. Please enable DMs from server members in your privacy settings and try again."
)
MSG_TIMEOUT = "⏱️ /join timed out. Run `/join` whenever you're ready to try again."
MSG_SUCCESS = "✅ Joined! Your latest stats are now on the leaderboard."
# Not in spec — flagged in handoff. Sent when the supplied 17lands token already
# belongs to a different Discord account
MSG_TOKEN_IN_USE = "That 17lands token is already linked to another Discord account."


SignupKind = Literal[
    "created",
    "already_signed_up",
    "invalid_format",
    "rejected_by_17lands",
    "token_in_use",
]

SignupCheckKind = Literal["fresh", "reactivated", "already_signed_up"]


@dataclass
class SignupResult:
    kind: SignupKind
    player_id: str | None = None


@dataclass
class SignupCheck:
    kind: SignupCheckKind
    player_id: str | None = None


def check_signup_eligibility(
    session: Session,
    discord_id: str,
    avatar_hash: str | None = None,
) -> SignupCheck:
    """Decide whether the caller needs the full DM flow, a reactivation, or nothing.

    A signed-out player (active=False) gets flipped back to active=True and
    returns "reactivated" — no DM dance needed since their token is still good.
    Avatar hash is refreshed on every reactivation so a long-absent player gets
    their current avatar picked up automatically.
    """
    existing = session.execute(
        select(Player).where(Player.discord_id == discord_id)
    ).scalar_one_or_none()
    if existing is None:
        return SignupCheck(kind="fresh")
    if not existing.active:
        existing.active = True
        if avatar_hash is not None and existing.avatar_hash != avatar_hash:
            existing.avatar_hash = avatar_hash
        session.commit()
        return SignupCheck(kind="reactivated", player_id=existing.id)
    return SignupCheck(kind="already_signed_up", player_id=existing.id)


def process_signup(
    session: Session,
    client: SeventeenLandsClient,
    discord_id: str,
    discord_username: str,
    display_name: str,
    token_input: str,
    avatar_hash: str | None = None,
) -> SignupResult:
    existing_by_discord = session.execute(
        select(Player).where(Player.discord_id == discord_id)
    ).scalar_one_or_none()
    if existing_by_discord is not None:
        return SignupResult(kind="already_signed_up", player_id=existing_by_discord.id)

    try:
        token = extract_token(token_input)
    except ValueError:
        return SignupResult(kind="invalid_format")

    if not client.verify_token(token):
        return SignupResult(kind="rejected_by_17lands")

    by_token = session.execute(
        select(Player).where(Player.seventeenlands_token == token)
    ).scalar_one_or_none()

    if by_token is None:
        slug = _next_available_slug(session, display_name)
        player = Player(
            slug=slug,
            discord_id=discord_id,
            discord_username=discord_username,
            display_name=display_name,
            avatar_hash=avatar_hash,
            seventeenlands_token=token,
            active=True,
        )
        session.add(player)
        session.commit()
        return SignupResult(kind="created", player_id=player.id)

    return SignupResult(kind="token_in_use", player_id=by_token.id)


class Signup(commands.Cog):
    def __init__(self, bot: commands.Bot, client: SeventeenLandsClient | None = None) -> None:
        self.bot = bot
        self.client = client or SeventeenLandsClient()
        # Per-user in-flight signup tracker. Prevents a second /join (or Join button
        # click) from kicking off a parallel flow while the first is still waiting
        # on a DM reply — that race produced contradictory 'already signed up' +
        # 'signed up' messages on the same paste
        self._active_signups: set[str] = set()

    @app_commands.command(name="join", description="Join the LLU Community Leaderboard")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def signup(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        username = str(interaction.user)
        audit.event("signup_invoked", user_id=user_id, username=username)

        if user_id in self._active_signups:
            audit.event("signup_concurrent_invocation", user_id=user_id)
            await interaction.response.send_message(MSG_ALREADY_IN_PROGRESS, ephemeral=(interaction.guild is not None))
            return
        self._active_signups.add(user_id)
        try:
            await self._run_signup_flow(interaction, user_id, username)
        finally:
            self._active_signups.discard(user_id)

    async def _run_signup_flow(
        self, interaction: discord.Interaction, user_id: str, username: str,
    ) -> None:
        avatar_hash = extract_avatar_hash(interaction.user)

        with SessionLocal() as session:
            check = check_signup_eligibility(session, user_id, avatar_hash=avatar_hash)
        if check.kind == "reactivated":
            audit.event("signup_reactivated", user_id=user_id, player_id=check.player_id)
            # Defer because the refresh may take a second or two on a cold rate limiter
            await interaction.response.defer(ephemeral=(interaction.guild is not None), thinking=True)
            with SessionLocal() as session:
                refresh_one_player_for_all_sets(session, self.client, check.player_id)
                session.commit()
            await _broadcast_current_set_safely(self.bot)
            # Welcome-back text uses the followup so the deferred interaction resolves;
            # leaderboard + stats go via dm.send so they render as plain bot messages
            # rather than threaded replies under the welcome-back message.
            await interaction.followup.send(MSG_WELCOME_BACK, ephemeral=(interaction.guild is not None))
            try:
                dm = await interaction.user.create_dm()
                lb_embed, lb_view, stats_embed = await _build_join_preview(user_id)
                if lb_embed is not None:
                    await dm.send(embed=lb_embed, view=lb_view)
                if stats_embed is not None:
                    await dm.send(embed=stats_embed)
            except Exception:
                logger.warning("post-reactivation preview failed", exc_info=True)
            return
        if check.kind == "already_signed_up":
            audit.event("signup_short_circuit", user_id=user_id, reason="already_signed_up")
            await interaction.response.send_message(MSG_ALREADY_SIGNED_UP, ephemeral=(interaction.guild is not None))
            return

        # Defer first — uploading the walkthrough image attachment can blow past
        # the 3s interaction-response deadline, which produced the
        # 'Unknown interaction (10062)' crash users hit on /join after retire
        await interaction.response.defer(ephemeral=(interaction.guild is not None), thinking=True)
        try:
            dm = await interaction.user.create_dm()
            kwargs: dict = {"content": INSTRUCTIONS}
            if INSTRUCTIONS_IMAGE.exists():
                kwargs["file"] = discord.File(INSTRUCTIONS_IMAGE)
            await dm.send(**kwargs)
        except discord.Forbidden:
            audit.event("signup_dms_disabled", user_id=user_id)
            await interaction.followup.send(MSG_DMS_DISABLED, ephemeral=(interaction.guild is not None))
            return

        await interaction.followup.send(MSG_DM_SENT, ephemeral=(interaction.guild is not None))
        audit.event("signup_dm_sent", user_id=user_id)

        def is_user_dm(m: discord.Message) -> bool:
            return m.author.id == interaction.user.id and m.guild is None

        try:
            reply = await self.bot.wait_for("message", check=is_user_dm, timeout=DM_TIMEOUT_S)
        except asyncio.TimeoutError:
            audit.event("signup_timeout", user_id=user_id)
            await dm.send(MSG_TIMEOUT)
            return

        # Length only — never log the raw token content
        audit.event("signup_dm_reply_received", user_id=user_id, reply_length=len(reply.content))

        with SessionLocal() as session:
            result = process_signup(
                session=session,
                client=self.client,
                discord_id=user_id,
                discord_username=username,
                display_name=interaction.user.display_name,
                token_input=reply.content,
                avatar_hash=avatar_hash,
            )

        audit.event(
            "signup_result",
            user_id=user_id,
            kind=result.kind,
            player_id=result.player_id,
        )

        if result.kind == "invalid_format":
            await dm.send(MSG_INVALID_FORMAT)
            return
        if result.kind == "rejected_by_17lands":
            await dm.send(MSG_REJECTED)
            return
        if result.kind == "token_in_use":
            await dm.send(MSG_TOKEN_IN_USE)
            return
        if result.kind == "already_signed_up":
            await dm.send(MSG_ALREADY_SIGNED_UP)
            return

        # created — pull fresh stats so they show up immediately
        with SessionLocal() as session:
            refresh_one_player_for_all_sets(session, self.client, result.player_id)
            session.commit()
        await _broadcast_current_set_safely(self.bot)
        await dm.send(MSG_SUCCESS)

        # Show the leaderboard right here in DM, plus the personal stats
        # breakdown — same pair the /leaderboard command sends to its invoker
        try:
            lb_embed, lb_view, stats_embed = await _build_join_preview(user_id)
            if lb_embed is not None:
                await dm.send(embed=lb_embed, view=lb_view)
            if stats_embed is not None:
                await dm.send(embed=stats_embed)
        except Exception:
            logger.warning("post-join leaderboard/stats preview failed", exc_info=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Signup(bot))


async def _broadcast_current_set_safely(bot) -> None:
    """Trigger a live edit of every tracked leaderboard message for the current set.

    Wrapped in a broad except so a Discord-side hiccup during the broadcast can't
    sink the signup flow itself — the join already succeeded by this point.
    """
    try:
        await broadcast_current_set_update(bot)
    except Exception:
        logger.warning("post-signup leaderboard broadcast failed", exc_info=True)


async def _build_join_preview(user_id: str):
    """Fetch the leaderboard + stats data for a freshly-joined or reactivated user.

    Returns (leaderboard_embed, leaderboard_view, stats_embed). Any element may
    be None if there's nothing to show (no current set, no stats yet).
    """
    with SessionLocal() as session:
        lb_data = process_leaderboard(session, viewer_discord_id=user_id)
    lb_embed = render_lb(lb_data) if lb_data is not None else None

    with SessionLocal() as session:
        stats_data = process_stats(session, player_name=None, viewer_discord_id=user_id)
    stats_embed = render_stats_embed(stats_data) if stats_data is not None else None

    return lb_embed, render_lb_view(), stats_embed


def _next_available_slug(session: Session, display_name: str) -> str:
    """Return a unique slug for `display_name`, suffixed -2/-3/... if taken.

    Race-prone in theory (no advisory lock), but signups are rare and the unique
    constraint will fail-loud if two slugs collide at insert time.
    """
    base = slugify(display_name)
    taken = set(session.execute(
        select(Player.slug).where(Player.slug.like(f"{base}%"))
    ).scalars().all())
    return disambiguate_slug(base, taken)
