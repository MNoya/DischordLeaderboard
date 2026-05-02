from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm import Session

from bot import audit
from bot.models import Player
from bot.services.refresh import refresh_one_player_for_current_set
from bot.services.seventeenlands import SeventeenLandsClient, extract_token

logger = logging.getLogger(__name__)

DM_TIMEOUT_S = 10 * 60

INSTRUCTIONS = (
    "**Welcome to the MTGA Community Leaderboard!**\n"
    "Get started by sharing your **17lands profile token**. Here's how:\n"
    "1. Go to [17lands.com](https://17lands.com) and log in.\n"
    "2. Click your username → **User History**.\n"
    "3. Copy the URL — it looks like:\n"
    "   `https://www.17lands.com/user_history/10c0f8918a2b4fa7b230448caee0b2ca`\n"
    "4. Reply to this message with the full URL or just the token.\n"
    "\n"
    "*Your token is stored securely and only used to fetch your game stats for the leaderboard.*"
)

MSG_DM_SENT = "📬 Check your DMs for signup instructions!"
MSG_ALREADY_SIGNED_UP = (
    "You're already on the leaderboard. Use `/relink` (in DM with the bot) to change your 17lands link."
)
MSG_WELCOME_BACK = "👋 Welcome back! Stats refreshed — you're on the leaderboard again."
MSG_INVALID_FORMAT = "That doesn't look like a valid 17lands token. Please check the URL and try again."
MSG_REJECTED = "That token couldn't be verified with 17lands. Please double-check your URL and try again."
MSG_DMS_DISABLED = (
    "⚠️ DMs are blocked. Please enable DMs from server members in your privacy settings and try again."
)
MSG_TIMEOUT = "⏱️ Signup timed out. Run `/join` whenever you're ready to try again."
MSG_SUCCESS = "✅ Signed up — your latest stats are now on the leaderboard. Check `/leaderboard`."
# Not in spec — flagged in handoff. Sent when the supplied 17lands token already
# belongs to a different Discord account
MSG_TOKEN_IN_USE = "That 17lands token is already linked to another Discord account."


SignupKind = Literal[
    "created",
    "linked",
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


def _seventeenlands_url(token: str) -> str:
    return f"https://www.17lands.com/user_history/{token}"


def check_signup_eligibility(session: Session, discord_id: str) -> SignupCheck:
    """Decide whether the caller needs the full DM flow, a reactivation, or nothing.

    A signed-out player (active=False) gets flipped back to active=True and
    returns "reactivated" — no DM dance needed since their token is still good.
    """
    existing = session.execute(
        select(Player).where(Player.discord_id == discord_id)
    ).scalar_one_or_none()
    if existing is None:
        return SignupCheck(kind="fresh")
    if not existing.active:
        existing.active = True
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
        player = Player(
            discord_id=discord_id,
            discord_username=discord_username,
            display_name=display_name,
            seventeenlands_token=token,
            seventeenlands_url=_seventeenlands_url(token),
            active=True,
        )
        session.add(player)
        session.commit()
        return SignupResult(kind="created", player_id=player.id)

    if by_token.discord_id is None:
        by_token.discord_id = discord_id
        by_token.discord_username = discord_username
        by_token.seventeenlands_url = _seventeenlands_url(token)
        by_token.token_invalid = False
        by_token.active = True
        session.commit()
        return SignupResult(kind="linked", player_id=by_token.id)

    if by_token.discord_id == discord_id:
        # Defensive — should have been caught by the first lookup
        return SignupResult(kind="already_signed_up", player_id=by_token.id)

    return SignupResult(kind="token_in_use", player_id=by_token.id)


class Signup(commands.Cog):
    def __init__(self, bot: commands.Bot, client: SeventeenLandsClient | None = None) -> None:
        self.bot = bot
        self.client = client or SeventeenLandsClient()

    @app_commands.command(name="join", description="Sign up for the MTGA leaderboard.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def signup(self, interaction: discord.Interaction) -> None:
        from bot.database import SessionLocal

        user_id = str(interaction.user.id)
        username = str(interaction.user)
        audit.event("signup_invoked", user_id=user_id, username=username)

        with SessionLocal() as session:
            check = check_signup_eligibility(session, user_id)
        if check.kind == "reactivated":
            audit.event("signup_reactivated", user_id=user_id, player_id=check.player_id)
            # Defer because the refresh may take a second or two on a cold rate limiter
            await interaction.response.defer(ephemeral=True, thinking=True)
            with SessionLocal() as session:
                refresh_one_player_for_current_set(session, self.client, check.player_id)
                session.commit()
            await interaction.followup.send(MSG_WELCOME_BACK, ephemeral=True)
            return
        if check.kind == "already_signed_up":
            audit.event("signup_short_circuit", user_id=user_id, reason="already_signed_up")
            await interaction.response.send_message(MSG_ALREADY_SIGNED_UP, ephemeral=True)
            return

        try:
            dm = await interaction.user.create_dm()
            await dm.send(INSTRUCTIONS)
        except discord.Forbidden:
            audit.event("signup_dms_disabled", user_id=user_id)
            await interaction.response.send_message(MSG_DMS_DISABLED, ephemeral=True)
            return

        await interaction.response.send_message(MSG_DM_SENT, ephemeral=True)
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

        # created or linked — pull fresh stats so they show up immediately
        with SessionLocal() as session:
            refresh_one_player_for_current_set(session, self.client, result.player_id)
            session.commit()
        await dm.send(MSG_SUCCESS)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Signup(bot))
