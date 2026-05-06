from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import audit

logger = logging.getLogger(__name__)


HELP_TITLE = "🃏 DisChord Leaderboard — Commands"

# (section_label, [(command, description), ...])
HELP_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("🃏 Anywhere", [
        ("/leaderboard", "Show the current set leaderboard"),
        ("/stats", "See your stats breakdown (or someone else's)"),
        ("/join", "Join the leaderboard"),
        ("/retire", "Pause your participation (your stats are kept)"),
        ("/relink", "Update your 17lands token"),
        ("/help", "Show this message"),
    ]),
    ("✉️ DM with the bot", [
        ("/leaderboard-full", "See the entire leaderboard"),
        ("/exile", "Permanently remove yourself from the leaderboard"),
    ]),
]


def render_help_embed() -> discord.Embed:
    embed = discord.Embed(title=HELP_TITLE, color=discord.Color.blurple())
    for section_label, items in HELP_SECTIONS:
        value = "\n".join(f"`{cmd}` — {desc}" for cmd, desc in items)
        embed.add_field(name=section_label, value=value, inline=False)
    return embed


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description="List the bot's commands.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def help(self, interaction: discord.Interaction) -> None:
        audit.event("help_invoked", user_id=str(interaction.user.id))
        await interaction.response.send_message(embed=render_help_embed(), ephemeral=(interaction.guild is not None))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
