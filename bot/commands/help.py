from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import audit
from bot.commands import descriptions as desc
from bot.discord_helpers import command_line, in_pod_coordination

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
    ("🚀 Pod Drafts", [
        ("/pod-guide", desc.POD_GUIDE),
    ]),
]

POD_HELP_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("🚀 Pod Drafts", [
        ("/pod-seeding", desc.POD_SEEDING),
        ("/pod-ready", desc.POD_READY),
        ("/pod-start", desc.POD_START),
        ("/pod-settings", desc.POD_SETTINGS),
        ("/pod-takeover", desc.POD_TAKEOVER),
        ("/pod-standings", desc.POD_STANDINGS),
        ("/help", desc.HELP),
    ]),
    ("🔗 Integration", [
        ("/link-17lands", desc.LINK_17LANDS),
        ("/link-arena", desc.LINK_ARENA),
    ]),
    ("⚙️ Admin", [
        ("/pod-champion", desc.POD_CHAMPION.removeprefix("[Admin] ")),
        ("/pod-backfill", desc.POD_BACKFILL.removeprefix("[Admin] ")),
        ("/pod-schedule", desc.POD_SCHEDULE.removeprefix("[Admin] ")),
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


def render_help_embed(sections: list[tuple[str, list[tuple[str, str]]]] = HELP_SECTIONS) -> discord.Embed:
    embed = discord.Embed(title=HELP_TITLE, color=discord.Color.blurple())
    for section_label, items in sections:
        lines = []
        for cmd, blurb in items:
            lines.append(command_line(cmd, blurb))
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
        sections = POD_HELP_SECTIONS if in_pod_coordination(interaction.channel) else HELP_SECTIONS
        audit.event("help_invoked", user_id=str(interaction.user.id))
        await interaction.response.send_message(embed=render_help_embed(sections), view=HelpView(), ephemeral=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
