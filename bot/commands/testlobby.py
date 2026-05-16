"""Owner-only `!testlobby` — sandbox for previewing the pod-draft lobby embed and bracket UI.

This entire module is throwaway scaffolding for design iteration. To remove it:
  1. Delete this file.
  2. Drop the `setup` call from bot/main.py setup_hook.
  3. Drop the `register_test_result_handler` hook + sentinel check in
     bot/services/pod_tournament.py (~6 lines).
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from bot import emojis
from bot.services import pod_swiss
from bot.services.lobby_embed import LobbyReadyButtonView, render as render_lobby_embed
from bot.services.pod_tournament import (
    RoundResultsView,
    TOTAL_ROUNDS,
    SKIPPED_SENTINEL,
    _round_embed,
    register_test_result_handler,
)


log = logging.getLogger(__name__)

TESTLOBBY_MATCH_PREFIX = "testlobby-"

_THREAD_NAME = "SOS Pod Draft #3 - May 15"
_DRAFTMANCER_URL = "https://draftmancer.com/?session=LLUT-SOS-May-15-D"
_RSVPS_YES = [
    "Noya", "Arcyl", "Doctormagi", "Oophies", "Chonce", "Elfandor",
    "flutterdev", "whalematron", "springbok7", "jonnietang",
]
_RSVPS_MAYBE = ["Bacchus", "NiamhIsTired", "Waveofshadow"]
_LINKED_EIGHT: list[tuple[str, str]] = [
    ("Noya#1234", "Noya"),
    ("Aristeo#15552", "Arcyl"),
    ("Doctormagi#47646", "Doctormagi"),
    ("Oophies#11360", "Oophies"),
    ("DongSlinger420#4573", "Chonce"),
    ("Elfandor#43425", "Elfandor"),
    ("fullerene60#49190", "flutterdev"),
    ("whalematron#89523", "whalematron"),
]
_VALID_STATES = (
    "empty", "partial", "linked", "unlinked", "ready", "notready",
    "drafting", "complete", "round1",
)

_LAST_MESSAGE: dict[int, discord.Message] = {}
_BRACKETS: dict[int, dict] = {}


def _make_match_id(round_num: int, idx: int) -> str:
    return f"{TESTLOBBY_MATCH_PREFIX}r{round_num}-m{idx}"


def _round1_match_states() -> list[dict]:
    pairings = [
        ("Noya", "Arcyl"),
        ("Doctormagi", "Oophies"),
        ("Chonce", "Elfandor"),
        ("flutterdev", "whalematron"),
    ]
    return [
        {
            "match_id": _make_match_id(1, i),
            "a_name": a, "b_name": b,
            "a_record": "0-0", "b_record": "0-0",
            "winner_name": None, "score": None,
        }
        for i, (a, b) in enumerate(pairings)
    ]


def _round1_embed() -> discord.Embed:
    pairings = [(m["a_name"], m["b_name"]) for m in _round1_match_states()]
    description = (
        f"{emojis.get('mtga')} Get your decks ready, then challenge your opponent below\n\n"
        + "\n".join(f"⚔️ {a}  vs  {b}" for a, b in pairings)
    )
    return discord.Embed(
        title="━━━ Round 1 Pairings ━━━",
        description=description,
        color=discord.Color.green(),
    )


def _build(state: str) -> tuple[discord.Embed, discord.ui.View | None, dict | None]:
    """Returns (embed, view, bracket_state). bracket_state is non-None for round1."""
    if state == "round1":
        match_states = _round1_match_states()
        embed = _round1_embed()
        view = RoundResultsView(match_states)
        bracket = {
            "players": [pod_swiss.Player(id=dn, name=dn) for _, dn in _LINKED_EIGHT],
            "match_states": match_states,
        }
        return embed, view, bracket

    if state == "empty":
        in_session: list[tuple[str, str | None]] = []
    elif state == "partial":
        in_session = list(_LINKED_EIGHT[:2])
    elif state == "unlinked":
        in_session = list(_LINKED_EIGHT[:7]) + [("Stranger#12345", None)]
    else:
        in_session = list(_LINKED_EIGHT)

    ready_count = 3 if state in ("ready", "notready") else None
    embed = render_lobby_embed(
        _THREAD_NAME, _RSVPS_YES, _RSVPS_MAYBE, in_session,
        state=state, draftmancer_url=_DRAFTMANCER_URL, ready_count=ready_count,
    )
    has_unrecognized = any(dn is None for _, dn in in_session)
    view: discord.ui.View | None = (
        None if state in ("drafting", "complete")
        else LobbyReadyButtonView(
            draftmancer_url=_DRAFTMANCER_URL,
            ready_disabled=(state == "ready" or has_unrecognized),
        )
    )
    return embed, view, None


def _final_embed(state: dict) -> discord.Embed:
    standings = pod_swiss.compute_standings(state["players"], state["outcomes"])
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for s in standings:
        medal = f"{medals[s.rank - 1]} " if s.rank - 1 < len(medals) else ""
        lines.append(f"{s.rank}. {medal}{s.player_name}  {s.wins}-{s.losses}")
    champion = standings[0] if standings else None
    title = f"🏆 Pod Draft Champion: {champion.player_name}" if champion else "Final standings"
    return discord.Embed(
        title=title,
        description="**Final standings:**\n" + "\n".join(lines),
        color=discord.Color.green(),
    )


def _next_round_match_states(round_num: int, pairings: list[tuple[str, str]],
                              outcomes: list[pod_swiss.MatchOutcome],
                              players: list[pod_swiss.Player]) -> list[dict]:
    prior = [m for m in outcomes if m.round_num < round_num]
    distinct = {pid for p in pairings for pid in p}
    pool = [p for p in players if p.id in distinct]
    standings_by_id = {s.player_id: s for s in pod_swiss.compute_standings(pool, prior)}
    states = []
    for idx, (a, b) in enumerate(pairings):
        a_s = standings_by_id.get(a)
        b_s = standings_by_id.get(b)
        states.append({
            "match_id": _make_match_id(round_num, idx),
            "a_name": a, "b_name": b,
            "a_record": f"{a_s.wins}-{a_s.losses}" if a_s else "0-0",
            "b_record": f"{b_s.wins}-{b_s.losses}" if b_s else "0-0",
            "winner_name": None, "score": None,
        })
    return states


async def _handle_test_result(interaction: discord.Interaction, match_id: str,
                               winner_name: str, score: str) -> None:
    message = interaction.message
    state = _BRACKETS.get(message.id) if message else None
    if state is None:
        try:
            await interaction.response.defer()
        except discord.HTTPException:
            pass
        return
    try:
        _, r_token, m_token = match_id.split("-", 2)
        round_num = int(r_token[1:])
        idx = int(m_token[1:])
    except (ValueError, IndexError):
        await interaction.response.send_message("Malformed test match id.", ephemeral=True)
        return

    matches = state["matches_by_round"].get(round_num)
    if matches is None or idx >= len(matches):
        await interaction.response.defer()
        return

    m = matches[idx]
    state["outcomes"] = [
        o for o in state["outcomes"]
        if not (o.round_num == round_num
                and {o.player_a_id, o.player_b_id} == {m["a_name"], m["b_name"]})
    ]
    if winner_name != SKIPPED_SENTINEL:
        state["outcomes"].append(pod_swiss.MatchOutcome(
            round_num=round_num,
            player_a_id=m["a_name"], player_b_id=m["b_name"],
            winner_id=winner_name, score=score,
        ))
    m["winner_name"] = winner_name
    m["score"] = score

    embed = _round_embed(round_num, matches)
    view = RoundResultsView(matches)
    try:
        await interaction.response.edit_message(content=None, embed=embed, view=view)
    except discord.HTTPException:
        log.warning("could not edit testlobby round message", exc_info=True)

    if not all(mm["winner_name"] for mm in matches):
        return

    if round_num >= TOTAL_ROUNDS:
        final = _final_embed(state)
        try:
            await interaction.followup.send(embed=final)
        except discord.HTTPException:
            log.warning("could not post testlobby final standings", exc_info=True)
        _BRACKETS.pop(message.id, None)
        return

    try:
        pairings = pod_swiss.pair_round(state["players"], state["outcomes"], round_num + 1)
    except ValueError:
        await interaction.followup.send("Could not pair next round (test).", ephemeral=True)
        return
    next_matches = _next_round_match_states(round_num + 1, pairings,
                                              state["outcomes"], state["players"])
    state["matches_by_round"][round_num + 1] = next_matches
    state["round"] = round_num + 1
    try:
        new_msg = await interaction.followup.send(
            embed=_round_embed(round_num + 1, next_matches),
            view=RoundResultsView(next_matches),
        )
        _BRACKETS[new_msg.id] = state
        _BRACKETS.pop(message.id, None)
    except discord.HTTPException:
        log.warning("could not post next testlobby round", exc_info=True)


async def setup(bot: commands.Bot) -> None:
    """Wire the `!testlobby` command and register the test bracket handler."""
    register_test_result_handler(TESTLOBBY_MATCH_PREFIX, _handle_test_result)

    @bot.command(name="testlobby")
    @commands.is_owner()
    async def test_lobby(ctx: commands.Context, state: str = "") -> None:
        """Owner-only. Render the pod-draft lobby embed in this channel.

        `state` ∈ empty | partial | linked | unlinked | ready | notready | drafting | complete | round1.
        No arg → posts every state in sequence. A specific state → edits the last in place."""
        if state and state not in _VALID_STATES:
            await ctx.send(f"unknown state `{state}`; pick one of: {', '.join(_VALID_STATES)}")
            return

        if state == "":
            for s in _VALID_STATES:
                embed, view, bracket = _build(s)
                msg = await ctx.send(embed=embed, view=view)
                if bracket is not None:
                    _BRACKETS[msg.id] = {
                        "players": bracket["players"],
                        "round": 1,
                        "matches_by_round": {1: list(bracket["match_states"])},
                        "outcomes": [],
                    }
            return

        embed, view, bracket = _build(state)
        last = _LAST_MESSAGE.get(ctx.channel.id)
        if last is not None:
            try:
                await last.edit(embed=embed, view=view, attachments=[])
                if bracket is not None:
                    _BRACKETS[last.id] = {
                        "players": bracket["players"],
                        "round": 1,
                        "matches_by_round": {1: list(bracket["match_states"])},
                        "outcomes": [],
                    }
                return
            except discord.HTTPException:
                _LAST_MESSAGE.pop(ctx.channel.id, None)
        msg = await ctx.send(embed=embed, view=view)
        _LAST_MESSAGE[ctx.channel.id] = msg
        if bracket is not None:
            _BRACKETS[msg.id] = {
                "players": bracket["players"],
                "round": 1,
                "matches_by_round": {1: list(bracket["match_states"])},
                "outcomes": [],
            }
