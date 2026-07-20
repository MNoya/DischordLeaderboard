"""Owner-only `!test thread-intro` — preview the team-room intro message.

Renders the real TEAM_THREAD_INTRO template for both teams so its Discord markdown (masked link,
bold + underline on "shared thread") can be eyeballed without running a full team draft.
"""
from __future__ import annotations

from discord.ext import commands

from bot.commands.test_group import test_group
from bot.services import pod_team
from bot.services.pod_team_flow import TEAM_THREAD_INTRO


async def setup(bot: commands.Bot) -> None:
    @test_group.command(name="thread-intro")
    @commands.is_owner()
    async def test_thread_intro(ctx: commands.Context) -> None:
        """Owner-only. Post the team-room intro for both teams in this channel."""
        for team in (pod_team.TEAM_A, pod_team.TEAM_B):
            await ctx.send(TEAM_THREAD_INTRO.format(
                emoji=pod_team.team_emoji(team),
                label=pod_team.team_label(team),
                board_url=ctx.channel.jump_url,
            ).rstrip())
