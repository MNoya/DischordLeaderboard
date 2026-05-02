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

logger = logging.getLogger(__name__)

CONFIRM_TIMEOUT_S = 5 * 60

MSG_CONFIRM = (
    "⚠️ This will permanently delete your account and all your stats. "
    "This cannot be undone. Reply with `YES` to confirm."
)
MSG_DELETED = "🗑️ Your account has been permanently deleted. You're welcome to run `/join` in the server again anytime."
MSG_CANCELLED = "Deletion cancelled. Your account is unchanged."
MSG_NOT_REGISTERED = "You don't have an account to delete."


DeleteAccountKind = Literal["deleted", "not_registered"]


@dataclass
class DeleteAccountResult:
    kind: DeleteAccountKind
    deleted_player_id: str | None = None


def process_delete_account(session: Session, discord_id: str) -> DeleteAccountResult:
    player = session.execute(
        select(Player).where(Player.discord_id == discord_id)
    ).scalar_one_or_none()
    if player is None:
        return DeleteAccountResult(kind="not_registered")
    player_id = player.id
    session.delete(player)
    session.commit()
    return DeleteAccountResult(kind="deleted", deleted_player_id=player_id)


class DeleteAccount(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # DM-only — registered globally with allowed_contexts so it doesn't appear in any guild slash menu
    @app_commands.command(name="exile", description="Permanently delete your leaderboard account.")
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def delete_account(self, interaction: discord.Interaction) -> None:
        from bot.database import SessionLocal

        user_id = str(interaction.user.id)
        audit.event("delete_account_invoked", user_id=user_id, username=str(interaction.user))

        with SessionLocal() as session:
            existing = session.execute(
                select(Player).where(Player.discord_id == user_id)
            ).scalar_one_or_none()
        if existing is None:
            audit.event("delete_account_short_circuit", user_id=user_id, reason="not_registered")
            await interaction.response.send_message(MSG_NOT_REGISTERED, ephemeral=True)
            return

        await interaction.response.send_message(MSG_CONFIRM, ephemeral=True)

        def is_user_dm(m: discord.Message) -> bool:
            return m.author.id == interaction.user.id and m.guild is None

        try:
            reply = await self.bot.wait_for("message", check=is_user_dm, timeout=CONFIRM_TIMEOUT_S)
        except asyncio.TimeoutError:
            audit.event("delete_account_timeout", user_id=user_id)
            await interaction.followup.send(MSG_CANCELLED, ephemeral=True)
            return

        if reply.content.strip().upper() != "YES":
            audit.event("delete_account_declined", user_id=user_id)
            await interaction.followup.send(MSG_CANCELLED, ephemeral=True)
            return

        with SessionLocal() as session:
            result = process_delete_account(session, user_id)

        audit.event("delete_account_result", user_id=user_id, kind=result.kind, deleted_player_id=result.deleted_player_id)
        await interaction.followup.send(MSG_DELETED, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DeleteAccount(bot))
