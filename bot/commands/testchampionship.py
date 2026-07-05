"""Owner-only `!test championship` — preview the championship copy in Discord.

Renders the crown registration embed and the seeding embed in both phases (projected from standings, then
live-from-Draftmancer) against the current leaderboard's top names, so the headlines and the 8-cut can be
eyeballed before a real event. Shares the production embed builders — this owns only the roster it feeds in.
The full announcement promo is a manual paste-ready file (prompts/championship-announcement.md), not here.
"""
from __future__ import annotations

import asyncio

import discord
from discord import ui
from discord.ext import commands
from sqlalchemy import select

from bot.commands.pod_draft import (
    CHAMPIONSHIP_CUT,
    SEEDING_CUT_ALTERNATES,
    SEEDING_CUT_OVER_CAP,
    SEEDING_PHASE_LIVE,
    build_seeding_image_message_from_names,
    seeding_phase_projected,
)
from bot.commands.test_group import test_group
from bot.database import SessionLocal
from bot.models import MagicSet
from bot.services.player_stats import rank_players_for_set
from bot.services.pod_registration_embed import build_registered_embed
from bot.services.pod_tournament import build_deck_ping, build_live_submit_deck_button, pod_page_url
from bot.sets import active_set_code

PREVIEW_ROSTER_SIZE = 10
MSG_NO_PLAYERS = "No ranked players on the active set yet — seed some locally to preview the seeding cut."


async def setup(bot: commands.Bot) -> None:
    @test_group.command(name="championship")
    @commands.is_owner()
    async def test_championship(ctx: commands.Context) -> None:
        """Owner-only. Preview the crown registration embed and both seeding phases."""
        names = await asyncio.to_thread(_top_player_names_sync, PREVIEW_ROSTER_SIZE)
        await ctx.send(embed=build_registered_embed(
            active_set_code(), "swiss", "leaderboard", championship=True))
        if not names:
            await ctx.send(MSG_NO_PLAYERS)
            return

        projected_file, projected_embed = await asyncio.to_thread(
            build_seeding_image_message_from_names, names, None,
            seat_cap=CHAMPIONSHIP_CUT, header=seeding_phase_projected(), cut_label=SEEDING_CUT_ALTERNATES,
        )
        live_file, live_embed = await asyncio.to_thread(
            build_seeding_image_message_from_names, names, None,
            seat_cap=CHAMPIONSHIP_CUT, header=SEEDING_PHASE_LIVE, cut_label=SEEDING_CUT_OVER_CAP,
        )
        await _send(ctx, projected_file, projected_embed)
        await _send(ctx, live_file, live_embed)

    @test_group.command(name="deckping")
    @commands.is_owner()
    async def test_deckping(ctx: commands.Context) -> None:
        """Owner-only. Preview the R3 deck-chase ping: one action line each, trailed by pings."""
        me = ctx.author.id
        view = ui.View(timeout=None)
        view.add_item(build_live_submit_deck_button())
        await ctx.send(
            build_deck_ping(([me, me], [me, me]), ([me], [me, me]), pod_page_url("Sample Pod 7")),
            allowed_mentions=discord.AllowedMentions(users=True),
            view=view,
        )


async def _send(ctx: commands.Context, file, embed) -> None:
    await ctx.send(embed=embed, file=file) if file else await ctx.send(embed=embed)


def _top_player_names_sync(limit: int) -> list[str]:
    with SessionLocal() as session:
        set_id = session.execute(
            select(MagicSet.id).where(MagicSet.code == active_set_code())
        ).scalar_one_or_none()
        if set_id is None:
            return []
        return [p.display_name for p in rank_players_for_set(session, set_id)[:limit]]
