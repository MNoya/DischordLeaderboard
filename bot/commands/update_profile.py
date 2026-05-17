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
from bot.database import SessionLocal
from bot.discord_helpers import extract_avatar_hash
from bot.models import Player
from bot.services.refresh import refresh_one_player_for_all_sets
from bot.services.seventeenlands import SeventeenLandsClient, extract_token

logger = logging.getLogger(__name__)

DM_TIMEOUT_S = 10 * 60

INSTRUCTIONS = (
    "**Update your 17lands profile**\n"
    "Reply with your updated **17lands profile URL or token**, e.g.\n"
    "`https://www.17lands.com/user_history/10c0f8918a2b4fa7b230448caee0b2ca`\n"
    "\n"
    "*Your token is stored securely and only used to fetch your game stats for the leaderboard.*"
)

MSG_DM_SENT = "📬 Check your DMs to finish updating your profile."
MSG_NOT_REGISTERED = "You're not on the leaderboard. Run `/join` in the server first."
MSG_INVALID_FORMAT = "That doesn't look like a valid 17lands token. Please check the URL and try again."
MSG_REJECTED = "That token couldn't be verified with 17lands. Please double-check your URL and try again."
MSG_DMS_DISABLED = "⚠️ DMs are blocked. Please enable DMs from server members in your privacy settings and try again."
MSG_TIMEOUT = "⏱️ Update timed out. Run `/relink` whenever you're ready to try again."
MSG_TOKEN_IN_USE = "That 17lands token is already linked to another Discord account."
MSG_SUCCESS = "✅ Profile updated — your latest stats are now on the leaderboard. Check `/leaderboard`."


UpdateProfileKind = Literal[
    "updated",
    "not_registered",
    "invalid_format",
    "rejected_by_17lands",
    "token_in_use",
]


@dataclass
class UpdateProfileResult:
    kind: UpdateProfileKind
    player_id: str | None = None


def process_update_profile(
    session: Session,
    client: SeventeenLandsClient,
    discord_id: str,
    token_input: str,
    avatar_hash: str | None = None,
) -> UpdateProfileResult:
    player = session.execute(
        select(Player).where(Player.discord_id == discord_id)
    ).scalar_one_or_none()
    if player is None:
        return UpdateProfileResult(kind="not_registered")

    try:
        token = extract_token(token_input)
    except ValueError:
        return UpdateProfileResult(kind="invalid_format", player_id=player.id)

    if not client.verify_token(token):
        return UpdateProfileResult(kind="rejected_by_17lands", player_id=player.id)

    other = session.execute(
        select(Player).where(
            Player.seventeenlands_token == token,
            Player.id != player.id,
        )
    ).scalar_one_or_none()
    if other is not None:
        return UpdateProfileResult(kind="token_in_use", player_id=player.id)

    player.seventeenlands_token = token
    player.token_invalid = False
    if avatar_hash is not None and player.avatar_hash != avatar_hash:
        player.avatar_hash = avatar_hash
    session.commit()
    return UpdateProfileResult(kind="updated", player_id=player.id)


class UpdateProfile(commands.Cog):
    def __init__(self, bot: commands.Bot, client: SeventeenLandsClient | None = None) -> None:
        self.bot = bot
        self.client = client or SeventeenLandsClient()

    @app_commands.command(name="relink", description="Update your 17lands token")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def update_profile(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        audit.event("update_profile_invoked", user_id=user_id, username=str(interaction.user))

        with SessionLocal() as session:
            existing = session.execute(
                select(Player).where(Player.discord_id == user_id)
            ).scalar_one_or_none()
        if existing is None:
            audit.event("update_profile_short_circuit", user_id=user_id, reason="not_registered")
            await interaction.response.send_message(MSG_NOT_REGISTERED, ephemeral=(interaction.guild is not None))
            return

        # Token entry always happens via DM regardless of where /relink was invoked
        try:
            dm = await interaction.user.create_dm()
            await dm.send(INSTRUCTIONS)
        except discord.Forbidden:
            audit.event("update_profile_dms_disabled", user_id=user_id)
            await interaction.response.send_message(MSG_DMS_DISABLED, ephemeral=(interaction.guild is not None))
            return

        await interaction.response.send_message(MSG_DM_SENT, ephemeral=(interaction.guild is not None))
        audit.event("update_profile_dm_sent", user_id=user_id)

        def is_user_dm(m: discord.Message) -> bool:
            return m.author.id == interaction.user.id and m.guild is None

        try:
            reply = await self.bot.wait_for("message", check=is_user_dm, timeout=DM_TIMEOUT_S)
        except asyncio.TimeoutError:
            audit.event("update_profile_timeout", user_id=user_id)
            await dm.send(MSG_TIMEOUT)
            return

        audit.event("update_profile_dm_reply_received", user_id=user_id, reply_length=len(reply.content))

        with SessionLocal() as session:
            result = process_update_profile(
                session=session,
                client=self.client,
                discord_id=user_id,
                token_input=reply.content,
                avatar_hash=extract_avatar_hash(interaction.user),
            )

        audit.event("update_profile_result", user_id=user_id, kind=result.kind, player_id=result.player_id)

        if result.kind == "invalid_format":
            await dm.send(MSG_INVALID_FORMAT)
            return
        if result.kind == "rejected_by_17lands":
            await dm.send(MSG_REJECTED)
            return
        if result.kind == "token_in_use":
            await dm.send(MSG_TOKEN_IN_USE)
            return
        if result.kind == "not_registered":
            await dm.send(MSG_NOT_REGISTERED)
            return

        # updated — pull fresh stats with the new token
        with SessionLocal() as session:
            refresh_one_player_for_all_sets(session, self.client, result.player_id)
            session.commit()
        await dm.send(MSG_SUCCESS)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UpdateProfile(bot))
