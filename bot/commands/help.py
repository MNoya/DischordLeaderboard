from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import audit
from bot.commands import descriptions as desc

logger = logging.getLogger(__name__)


HELP_TITLE = "❔ Commands"

# (section_label, [(command, description), ...])
HELP_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("🏆 Leaderboard", [
        ("/leaderboard", desc.LEADERBOARD),
        ("/stats", desc.STATS),
        ("/join", desc.JOIN),
        ("/opt-out", desc.OPT_OUT),
        ("/retire", desc.RETIRE),
        ("/exile", desc.EXILE),
        ("/help", desc.HELP),
    ]),
    ("🔗 Integration", [
        ("/link-17lands", desc.LINK_17LANDS),
        ("/link-arena", desc.LINK_ARENA),
    ]),
]


# command → blockquote usage examples, each kept to one line
HELP_EXAMPLES: dict[str, list[list[str]]] = {
    "/leaderboard": [
        ["/leaderboard", "format: Premier"],
        ["/leaderboard", "color: Boros", "set: FIN"],
        ["/leaderboard", "set: ALL"],
    ],
}


FEEDBACK_CHANNEL_ID = 1504825374188507156


class HelpView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=600)

    @discord.ui.button(label="Dismiss", style=discord.ButtonStyle.secondary)
    async def dismiss(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        await interaction.delete_original_response()


def render_help_embed() -> discord.Embed:
    embed = discord.Embed(title=HELP_TITLE, color=discord.Color.blurple())
    for section_label, items in HELP_SECTIONS:
        lines = []
        for cmd, desc in items:
            lines.append(f"`{cmd}`: {desc}")
            for example in HELP_EXAMPLES.get(cmd, []):
                lines.append("> " + " ".join(f"`{chip}`" for chip in example))
        embed.add_field(name=section_label, value="\n".join(lines), inline=False)
    embed.add_field(
        name="💬 Found a bug or have any ideas?",
        value=f"Post in <#{FEEDBACK_CHANNEL_ID}>",
        inline=False,
    )
    return embed


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description=desc.HELP)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def help(self, interaction: discord.Interaction) -> None:
        audit.event("help_invoked", user_id=str(interaction.user.id))
        await interaction.response.send_message(embed=render_help_embed(), view=HelpView(), ephemeral=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
