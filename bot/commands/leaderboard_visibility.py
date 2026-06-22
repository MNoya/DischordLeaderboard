from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from sqlalchemy import select

from bot import audit
from bot.commands import descriptions as desc
from bot.commands.leaderboard import broadcast_current_set_safely
from bot.commands.messages import MSG_ALREADY_HIDDEN, MSG_NOT_REGISTERED, MSG_NOW_HIDDEN
from bot.database import SessionLocal
from bot.discord_helpers import player_url
from bot.models import Player


class LeaderboardVisibility(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="opt-out", description=desc.OPT_OUT)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def opt_out(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        ephemeral = interaction.guild is not None
        with SessionLocal() as session:
            player = session.execute(
                select(Player).where(Player.discord_id == user_id)
            ).scalar_one_or_none()
            ranked = player is not None and player.active and player.seventeenlands_token is not None
            if not ranked:
                audit.event("leaderboard_opt_out", user_id=user_id, registered=False)
                await interaction.response.send_message(MSG_NOT_REGISTERED, ephemeral=ephemeral)
                return
            if not player.leaderboard_opt_in:
                audit.event("leaderboard_opt_out", user_id=user_id, registered=True, already_hidden=True)
                await interaction.response.send_message(MSG_ALREADY_HIDDEN, ephemeral=ephemeral)
                return
            player.leaderboard_opt_in = False
            slug = player.slug
            session.commit()
        audit.event("leaderboard_opt_out", user_id=user_id, registered=True)
        message = MSG_NOW_HIDDEN.format(profile_url=player_url(slug))
        await interaction.response.send_message(message, ephemeral=ephemeral)
        await broadcast_current_set_safely(self.bot)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaderboardVisibility(bot))
