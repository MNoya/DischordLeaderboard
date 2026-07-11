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
from bot.services import pod_swiss
from bot.services.player_stats import rank_players_for_set
from bot.services.pod_registration_embed import build_registered_embed
from bot.services.pod_swiss import MatchOutcome
from bot.services.pod_tournament import (
    TOTAL_ROUNDS,
    build_champion_embed,
    build_deck_ping,
    build_live_submit_deck_button,
    mark_trophy_match,
    pod_page_url,
)
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

    @test_group.command(name="tiebreakers")
    @commands.is_owner()
    async def test_tiebreakers(ctx: commands.Context) -> None:
        """Owner-only. Preview the Final Standings tiebreaker table that surfaces when a placement is
        decided on tiebreakers (a trophy-match loser bumped below 2nd)."""
        standings, match_states = _tiebreaker_preview_scenario()
        embed = build_champion_embed(
            standings, event_name="Tiebreaker Preview Pod",
            pending_count=0, champion_locked=True, match_states=match_states,
        )
        await ctx.send(embed=embed)

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


def _tiebreaker_preview_scenario():
    """An 8-player Swiss pod where the trophy-match loser (Cyrus) finishes 3rd on OGW% behind a 2-1
    peer, so the tiebreaker table renders. Fictional names over the match graph that produces the tie."""
    seats = {"Aria": 0, "Bex": 1, "Cyrus": 2, "Dot": 3, "Enzo": 4, "Fern": 5, "Gus": 6, "Hana": 7}
    players = [pod_swiss.Player(id=name, name=name, seat=seat) for name, seat in seats.items()]
    raw = [
        (1, "Aria", "Enzo", "Aria", "2-0"),
        (1, "Bex", "Fern", "Bex", "2-0"),
        (1, "Cyrus", "Gus", "Cyrus", "2-1"),
        (1, "Dot", "Hana", "Hana", "2-1"),
        (2, "Aria", "Bex", "Aria", "2-1"),
        (2, "Enzo", "Fern", "Fern", "2-1"),
        (2, "Hana", "Cyrus", "Cyrus", "2-0"),
        (2, "Dot", "Gus", "Dot", "2-0"),
        (3, "Aria", "Cyrus", "Aria", "2-1"),
        (3, "Bex", "Hana", "Bex", "2-1"),
        (3, "Fern", "Dot", "Dot", "2-1"),
        (3, "Enzo", "Gus", "Enzo", "2-1"),
    ]
    matches = [MatchOutcome(r, a, b, w, s) for r, a, b, w, s in raw]
    standings = pod_swiss.compute_standings(players, matches)
    match_states = [
        {"a_name": "Aria", "b_name": "Cyrus", "winner_name": "Aria", "a_record": "2-0", "b_record": "2-0"},
        {"a_name": "Bex", "b_name": "Hana", "winner_name": "Bex", "a_record": "1-1", "b_record": "1-1"},
        {"a_name": "Fern", "b_name": "Dot", "winner_name": "Dot", "a_record": "1-1", "b_record": "1-1"},
        {"a_name": "Enzo", "b_name": "Gus", "winner_name": "Enzo", "a_record": "0-2", "b_record": "0-2"},
    ]
    mark_trophy_match(match_states, TOTAL_ROUNDS)
    return standings, match_states


def _top_player_names_sync(limit: int) -> list[str]:
    with SessionLocal() as session:
        set_id = session.execute(
            select(MagicSet.id).where(MagicSet.code == active_set_code())
        ).scalar_one_or_none()
        if set_id is None:
            return []
        return [p.display_name for p in rank_players_for_set(session, set_id)[:limit]]
