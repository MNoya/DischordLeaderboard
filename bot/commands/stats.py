from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import audit
from bot.commands import descriptions as desc
from bot.commands.leaderboard import broadcast_current_set_safely
from bot.database import SessionLocal
from bot.services.leaderboard_visibility import set_opt_in
from bot.services.player_stats import process_stats, render_embed

logger = logging.getLogger(__name__)


class LeaderboardVisibilityView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: str, opted_in: bool) -> None:
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.opted_in = opted_in
        self._render_button()

    def _render_button(self) -> None:
        self.clear_items()
        label = "Hide my rank" if self.opted_in else "Show my rank"
        style = discord.ButtonStyle.secondary if self.opted_in else discord.ButtonStyle.success
        button = discord.ui.Button(label=label, style=style)
        button.callback = self._toggle
        self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def _toggle(self, interaction: discord.Interaction) -> None:
        self.opted_in = not self.opted_in
        with SessionLocal() as session:
            set_opt_in(session, self.user_id, self.opted_in)
            data = process_stats(session, player_name=None, viewer_discord_id=self.user_id)
        audit.event("leaderboard_visibility_button", user_id=self.user_id, opt_in=self.opted_in)
        self._render_button()
        if data is not None:
            await interaction.response.edit_message(embed=render_embed(data), view=self)
        else:
            await interaction.response.edit_message(view=self)
        await broadcast_current_set_safely(self.bot)


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="stats", description=desc.STATS)
    @app_commands.describe(player="Player display name to look up (defaults to you)")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def stats(
        self, interaction: discord.Interaction, player: str | None = None
    ) -> None:
        user_id = str(interaction.user.id)
        username = str(interaction.user)
        audit.event("stats_invoked", user_id=user_id, player=player)
        target = player or "self"
        logger.info(f"stats: {username} looked up {target!r}")

        with SessionLocal() as session:
            data = process_stats(session, player_name=player, viewer_discord_id=user_id)

        if data is None:
            logger.info(f"stats: not found for {target!r}")
            if player:
                msg = f"No active player found with display name `{player}`."
            else:
                msg = "You're not on the leaderboard. Run `/join` to get started."
            await interaction.response.send_message(msg, ephemeral=(interaction.guild is not None))
            return

        logger.info(f"stats: {data.player_name} rank={data.rank} score={data.total_score:.1f}")
        kwargs = {"embed": render_embed(data), "ephemeral": (interaction.guild is not None)}
        if player is None and data.has_token:
            kwargs["view"] = LeaderboardVisibilityView(self.bot, user_id, opted_in=not data.opted_out)
        await interaction.response.send_message(**kwargs)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Stats(bot))
