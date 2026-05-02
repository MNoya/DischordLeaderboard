from __future__ import annotations

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

MSG_SIGNED_OUT = (
    "✅ You've retired from the leaderboard. Your stats are saved — run `/join` anytime to return.\n"
    "If you'd rather have your data permanently deleted, run `/exile` (in DM with the bot)."
)
MSG_NOT_REGISTERED = "You're not on the leaderboard."
MSG_ALREADY_INACTIVE = "You're already retired. Run `/join` to return."


SignoutKind = Literal["signed_out", "not_registered", "already_inactive"]


@dataclass
class SignoutResult:
    kind: SignoutKind
    player_id: str | None = None


def process_signout(session: Session, discord_id: str) -> SignoutResult:
    player = session.execute(
        select(Player).where(Player.discord_id == discord_id)
    ).scalar_one_or_none()
    if player is None:
        return SignoutResult(kind="not_registered")
    if not player.active:
        return SignoutResult(kind="already_inactive", player_id=player.id)
    player.active = False
    session.commit()
    return SignoutResult(kind="signed_out", player_id=player.id)


class Signout(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="retire", description="Pause your participation on the leaderboard.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def signout(self, interaction: discord.Interaction) -> None:
        from bot.database import SessionLocal

        user_id = str(interaction.user.id)
        audit.event("signout_invoked", user_id=user_id, username=str(interaction.user))

        with SessionLocal() as session:
            result = process_signout(session, user_id)

        audit.event("signout_result", user_id=user_id, kind=result.kind, player_id=result.player_id)

        if result.kind == "signed_out":
            await interaction.response.send_message(MSG_SIGNED_OUT, ephemeral=True)
        elif result.kind == "already_inactive":
            await interaction.response.send_message(MSG_ALREADY_INACTIVE, ephemeral=True)
        else:
            await interaction.response.send_message(MSG_NOT_REGISTERED, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Signout(bot))
