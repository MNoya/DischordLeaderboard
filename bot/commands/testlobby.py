"""Owner-only `!testlobby` — sandbox for previewing the pod-draft lobby embed and bracket UI.

This entire module is throwaway scaffolding for design iteration. To remove it:
  1. Delete this file.
  2. Drop the `setup` call from bot/main.py setup_hook.
  3. Drop the `register_test_result_handler` hook + sentinel check in
     bot/services/pod_tournament.py (~6 lines).
"""
from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from bot.services import pod_swiss
from bot.services.lobby_embed import LobbyReadyButtonView, render as render_lobby_embed
from bot.services.pod_deck_color import SubmitDeckView
from bot.services.pod_tournament import (
    GRACE_SECONDS,
    ParticipantDeckData,
    RoundResultsView,
    TOTAL_ROUNDS,
    SKIPPED_SENTINEL,
    _mark_trophy_match,
    _round_embed,
    build_champion_announcement_view,
    build_champion_embed,
    build_pairing_dm_embed,
    register_test_result_handler,
)


log = logging.getLogger(__name__)

TESTLOBBY_MATCH_PREFIX = "testlobby-"

# In testlobby the invoker plays this seat in the fake roster so the round-DM preview
# is realistic — one DM per round, addressed to the human who ran the command.
_INVOKER_SEAT = "Noya"

# Module-level scratch store for the SubmitDeck POC; cleared on bot restart.
_TEST_DECK_COLORS: dict[int, str] = {}


def _test_arena_for(seat: str) -> str | None:
    for arena_name, discord_name in _LINKED_EIGHT:
        if discord_name == seat:
            return arena_name
    return None


def _find_invoker_match(matches: list[dict], invoker_seat: str) -> tuple[str, str] | None:
    """Return (own_seat, opponent_seat) for the invoker's pairing in this round, if any."""
    for m in matches:
        if m["a_name"] == invoker_seat:
            return invoker_seat, m["b_name"]
        if m["b_name"] == invoker_seat:
            return invoker_seat, m["a_name"]
    return None


async def _dm_invoker_pairing(user: discord.User | discord.Member, round_num: int,
                               opponent: str, opponent_arena: str | None,
                               pairings_url: str | None = None) -> None:
    embed = build_pairing_dm_embed(
        round_num=round_num,
        opponent_label=f"**{opponent}**",
        opponent_arena=opponent_arena,
        pairings_url=pairings_url,
        event_name=_THREAD_NAME,
        updated=False,
    )
    try:
        await user.send(embed=embed)
    except discord.Forbidden:
        log.info("testlobby DM blocked for user %s", user.id)
    except discord.HTTPException:
        log.warning("testlobby DM failed", exc_info=True)


async def _test_submit_deck_color(interaction: discord.Interaction, color: str) -> None:
    _TEST_DECK_COLORS[interaction.user.id] = color
    log.info("testlobby deck color saved: user=%s color=%s", interaction.user.id, color)


async def _test_lookup_deck_color(interaction: discord.Interaction) -> str | None:
    return _TEST_DECK_COLORS.get(interaction.user.id)


def _submit_deck_view(state: dict | None = None) -> SubmitDeckView:
    """Build a SubmitDeckView. When `state` is provided, the submit callback attributes the color to
    the invoker's seat in the bracket and re-evaluates the champion announcement.
    """
    if state is None:
        return SubmitDeckView(_test_submit_deck_color, _test_lookup_deck_color)

    from bot.services.pod_drafts import _normalize_player_name as _norm

    async def submit(interaction: discord.Interaction, color: str) -> None:
        _TEST_DECK_COLORS[interaction.user.id] = color
        state.setdefault("player_colors", {})[_norm(_INVOKER_SEAT)] = color
        await _maybe_post_or_update_test_standings(state, interaction.channel)
        # Color submit edits an existing announcement but never triggers the first post —
        # screenshot upload (or grace expiry) is the only thing that creates it.
        if state.get("champion_announced"):
            await _maybe_announce_or_update_test_champion(state, interaction.channel)

    return SubmitDeckView(submit, _test_lookup_deck_color)

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
    "empty", "partial", "linked", "unlinked", "ready", "notready", "cancelled",
    "drafting", "complete", "round1", "round3",
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


def _build(state: str) -> tuple[discord.Embed, discord.ui.View | None, dict | None]:
    """Returns (embed, view, bracket_state). bracket_state is non-None for bracket states (round1, round3)."""
    if state == "round1":
        match_states = _round1_match_states()
        embed = _round_embed(1, match_states)
        view = RoundResultsView(match_states)
        bracket = {
            "players": [pod_swiss.Player(id=dn, name=dn) for _, dn in _LINKED_EIGHT],
            "round": 1,
            "matches_by_round": {1: list(match_states)},
            "outcomes": [],
        }
        return embed, view, bracket

    if state == "round3":
        players = [pod_swiss.Player(id=dn, name=dn) for _, dn in _LINKED_EIGHT]
        # Seed: top of each pairing wins, except the bot owner's seat always wins so it's 2-0 in R3
        def _seed(round_num: int, a: str, b: str) -> pod_swiss.MatchOutcome:
            winner = _INVOKER_SEAT if _INVOKER_SEAT in (a, b) else a
            return pod_swiss.MatchOutcome(round_num=round_num, player_a_id=a, player_b_id=b,
                                          winner_id=winner, score="2-1")
        r1_pairings = pod_swiss.pair_round(players, [], 1)
        r1 = [_seed(1, a, b) for a, b in r1_pairings]
        r2_pairings = pod_swiss.pair_round(players, r1, 2)
        r2 = [_seed(2, a, b) for a, b in r2_pairings]
        all_outcomes = r1 + r2
        r3_pairings = pod_swiss.pair_round(players, all_outcomes, 3)
        r3_states = _next_round_match_states(3, r3_pairings, all_outcomes, players)
        _mark_trophy_match(r3_states, 3)
        embed = _round_embed(3, r3_states)
        view = RoundResultsView(r3_states)
        bracket = {
            "players": players,
            "round": 3,
            "matches_by_round": {3: r3_states},
            "outcomes": all_outcomes,
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
    render_state = "notready" if state == "cancelled" else state
    cancel_reason = "Player list changed" if state == "cancelled" else None
    embed = render_lobby_embed(
        _THREAD_NAME, _RSVPS_YES, _RSVPS_MAYBE, in_session,
        state=render_state, draftmancer_url=_DRAFTMANCER_URL,
        ready_count=ready_count, cancel_reason=cancel_reason,
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
    return build_champion_embed(standings, event_name=_THREAD_NAME)


async def _maybe_post_or_update_test_standings(state: dict, channel) -> None:
    """Mirror pod_tournament._post_or_update_live_standings for the in-memory testlobby bracket."""
    matches = state["matches_by_round"].get(TOTAL_ROUNDS, [])
    if not matches:
        return
    _mark_trophy_match(matches, TOTAL_ROUNDS)
    if not any(m.get("winner_name") for m in matches):
        return

    trophy = [m for m in matches if m.get("is_trophy_match")]
    champion_locked = bool(trophy) and all(m.get("winner_name") for m in trophy)
    pending_count = sum(1 for m in matches if not m.get("winner_name"))

    embed = build_champion_embed(
        pod_swiss.compute_standings(state["players"], state["outcomes"]),
        event_name=_THREAD_NAME,
        player_colors=state.get("player_colors", {}),
        champion_locked=champion_locked,
        pending_count=pending_count,
    )
    existing = state.get("standings_message")
    if existing is None:
        try:
            state["standings_message"] = await channel.send(embed=embed, view=_submit_deck_view(state))
        except discord.HTTPException:
            log.warning("could not post testlobby standings", exc_info=True)
    else:
        try:
            await existing.edit(embed=embed)
        except discord.HTTPException:
            log.warning("could not edit testlobby standings", exc_info=True)

    if state.get("champion_announced"):
        await _maybe_announce_or_update_test_champion(state, channel)


async def _maybe_announce_or_update_test_champion(state: dict, channel) -> None:
    """Mirror of pod_tournament._announce_or_update_champion for in-memory testlobby state.

    Trigger: champion locked AND (all champion colors submitted OR grace expired).
    Fallback: post without colors if grace expires without submissions.
    """
    from bot.services.pod_drafts import _normalize_player_name as _norm

    matches = state["matches_by_round"].get(TOTAL_ROUNDS, [])
    if not matches:
        return
    _mark_trophy_match(matches, TOTAL_ROUNDS)
    trophy = [m for m in matches if m.get("is_trophy_match")]
    if not trophy or not all(m.get("winner_name") for m in trophy):
        return

    standings = pod_swiss.compute_standings(state["players"], state["outcomes"])
    champions = [s for s in standings if s.losses == 0]
    if not champions:
        return

    player_colors = state.get("player_colors", {})
    rank1_key = _norm(champions[0].player_name)
    screenshots = state.get("screenshots", {})
    captions = state.get("screenshot_captions", {})
    rank1_screenshot_in = bool(screenshots.get(rank1_key))
    grace_task = state.get("grace_task")
    grace_expired = grace_task is None or grace_task.done()

    if not state.get("champion_announced") and not rank1_screenshot_in and not grace_expired:
        return

    pending_count = sum(1 for m in matches if not m.get("winner_name"))
    standings_msg = state.get("standings_message")
    deck_data = {
        _norm(p.name): ParticipantDeckData(
            colors=player_colors.get(_norm(p.name)),
            screenshot_url=screenshots.get(_norm(p.name)),
            screenshot_caption=captions.get(_norm(p.name)),
        )
        for p in state["players"]
    }

    target = channel
    if state.get("champion_announcement_message") is None and isinstance(channel, discord.Thread):
        parent = channel.parent
        if parent is None and getattr(channel, "parent_id", None):
            try:
                parent = await channel.guild.fetch_channel(channel.parent_id)
            except discord.HTTPException:
                log.warning("could not fetch parent for testlobby thread", exc_info=True)
        if parent is not None:
            target = parent
    guild_id = getattr(getattr(target, "guild", None), "id", None)
    thread_id = standings_msg.channel.id if standings_msg is not None else None

    view = build_champion_announcement_view(
        standings,
        event_name=_THREAD_NAME,
        player_colors=player_colors,
        pending_count=pending_count,
        deck_data=deck_data,
        guild_id=guild_id,
        thread_id=thread_id,
    )

    existing = state.get("champion_announcement_message")
    if existing is None:
        try:
            state["champion_announcement_message"] = await target.send(view=view)
            state["champion_announced"] = True
        except discord.HTTPException:
            log.warning("could not post testlobby champion announcement", exc_info=True)
        return

    try:
        await existing.edit(view=view)
    except discord.HTTPException:
        log.warning("could not edit testlobby champion announcement", exc_info=True)


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

    _mark_trophy_match(matches, round_num)
    embed = _round_embed(round_num, matches)
    view = RoundResultsView(matches)
    try:
        await interaction.response.edit_message(content=None, embed=embed, view=view)
    except discord.HTTPException:
        log.warning("could not edit testlobby round message", exc_info=True)

    if round_num == TOTAL_ROUNDS:
        await _maybe_post_or_update_test_standings(state, interaction.channel)

    if not all(mm["winner_name"] for mm in matches):
        return

    is_edit_during_grace = (state.get("grace_round") == round_num and state.get("grace_task") is not None)

    if is_edit_during_grace:
        if round_num < TOTAL_ROUNDS:
            await _regenerate_test_next_round(state, round_num + 1, interaction.channel)
        _schedule_test_grace(state, round_num)
        return

    if round_num >= TOTAL_ROUNDS:
        _schedule_test_grace(state, round_num)
        return

    try:
        pairings = pod_swiss.pair_round(state["players"], state["outcomes"], round_num + 1)
    except ValueError:
        await interaction.followup.send("Could not pair next round (test).", ephemeral=True)
        return
    next_matches = _next_round_match_states(round_num + 1, pairings,
                                              state["outcomes"], state["players"])
    _mark_trophy_match(next_matches, round_num + 1)
    state["matches_by_round"][round_num + 1] = next_matches
    state["round"] = round_num + 1
    try:
        new_msg = await interaction.followup.send(
            embed=_round_embed(round_num + 1, next_matches),
            view=RoundResultsView(next_matches),
        )
        _BRACKETS[new_msg.id] = state
        state.setdefault("round_messages", {})[round_num + 1] = new_msg
    except discord.HTTPException:
        log.warning("could not post next testlobby round", exc_info=True)
        return

    _schedule_test_grace(state, round_num)

    invoker = state.get("invoker")
    if invoker is not None:
        pairing = _find_invoker_match(next_matches, _INVOKER_SEAT)
        if pairing is not None:
            _, opp = pairing
            await _dm_invoker_pairing(
                invoker, round_num + 1, opp, _test_arena_for(opp),
                pairings_url=new_msg.jump_url,
            )


def _schedule_test_grace(state: dict, round_num: int) -> None:
    existing = state.get("grace_task")
    if existing is not None and not existing.done():
        existing.cancel()
    state["grace_round"] = round_num
    state["grace_task"] = asyncio.create_task(_test_grace_expire(state, round_num))


async def _test_grace_expire(state: dict, round_num: int) -> None:
    try:
        await asyncio.sleep(GRACE_SECONDS)
    except asyncio.CancelledError:
        return
    msg = state.get("round_messages", {}).get(round_num)
    if msg is not None:
        try:
            await msg.edit(view=None)
        except discord.HTTPException:
            log.warning("could not lock testlobby round %d view", round_num, exc_info=True)
    state["grace_round"] = None
    state["grace_task"] = None

    if round_num >= TOTAL_ROUNDS and not state.get("champion_announced"):
        standings_msg = state.get("standings_message")
        if standings_msg is not None:
            await _maybe_announce_or_update_test_champion(state, standings_msg.channel)


async def _regenerate_test_next_round(state: dict, next_round: int, channel) -> None:
    prev_matches = state["matches_by_round"].get(next_round, [])
    prev_pairings = [(m["a_name"], m["b_name"]) for m in prev_matches]
    try:
        pairings = pod_swiss.pair_round(state["players"], state["outcomes"], next_round)
    except ValueError:
        log.warning("testlobby regenerate failed for round %d", next_round)
        return
    next_matches = _next_round_match_states(next_round, pairings,
                                              state["outcomes"], state["players"])
    _mark_trophy_match(next_matches, next_round)
    state["matches_by_round"][next_round] = next_matches

    msg = state.get("round_messages", {}).get(next_round)
    if msg is not None:
        try:
            await msg.edit(embed=_round_embed(next_round, next_matches),
                            view=RoundResultsView(next_matches))
        except discord.HTTPException:
            log.warning("could not edit testlobby round %d during regenerate", next_round, exc_info=True)

    invoker = state.get("invoker")
    if invoker is None or msg is None:
        return

    def _opp_in(pairings_list, seat):
        for a, b in pairings_list:
            if a == seat:
                return b
            if b == seat:
                return a
        return None

    prev_opp = _opp_in(prev_pairings, _INVOKER_SEAT)
    new_opp = _opp_in(pairings, _INVOKER_SEAT)
    if new_opp is not None and new_opp != prev_opp:
        await _dm_invoker_changed_opponent(invoker, next_round, new_opp,
                                            _test_arena_for(new_opp), msg.jump_url)


async def _dm_invoker_changed_opponent(user: discord.User | discord.Member, round_num: int,
                                        opponent: str, opponent_arena: str | None,
                                        pairings_url: str) -> None:
    embed = build_pairing_dm_embed(
        round_num=round_num,
        opponent_label=f"**{opponent}**",
        opponent_arena=opponent_arena,
        pairings_url=pairings_url,
        event_name=_THREAD_NAME,
        updated=True,
    )
    try:
        await user.send(embed=embed)
    except discord.Forbidden:
        log.info("testlobby re-pair DM blocked for user %s", user.id)
    except discord.HTTPException:
        log.warning("testlobby re-pair DM failed", exc_info=True)


class _TestlobbyScreenshotListener(commands.Cog):
    """Mirror of PodScreenshotListener: bot owner's image becomes their seat's screenshot in the test embed."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        image_url = next(
            (att.url for att in message.attachments if (att.content_type or "").lower().startswith("image/")),
            None,
        )
        if image_url is None:
            return
        from bot.services.pod_drafts import _normalize_player_name as _norm

        for state in _BRACKETS.values():
            invoker = state.get("invoker")
            if invoker is None or invoker.id != message.author.id:
                continue
            standings_msg = state.get("standings_message")
            announcement = state.get("champion_announcement_message")
            channel_ids = {
                getattr(getattr(m, "channel", None), "id", None)
                for m in (standings_msg, announcement)
                if m is not None
            }
            channel_ids.discard(None)
            if message.channel.id not in channel_ids:
                continue
            key = _norm(_INVOKER_SEAT)
            state.setdefault("screenshots", {})[key] = image_url
            caption = (message.content or "").strip() or None
            state.setdefault("screenshot_captions", {})[key] = caption
            await _maybe_announce_or_update_test_champion(state, message.channel)
            standings = pod_swiss.compute_standings(state["players"], state["outcomes"])
            if any(s.losses == 0 and _norm(s.player_name) == key for s in standings):
                try:
                    await message.add_reaction("🏆")
                except discord.HTTPException:
                    log.info("could not add 🏆 reaction in testlobby", exc_info=True)
            break


async def setup(bot: commands.Bot) -> None:
    """Wire the `!testlobby` command and register the test bracket handler."""
    register_test_result_handler(TESTLOBBY_MATCH_PREFIX, _handle_test_result)
    await bot.add_cog(_TestlobbyScreenshotListener(bot))

    @bot.command(name="testlobby")
    @commands.is_owner()
    async def test_lobby(ctx: commands.Context, state: str = "") -> None:
        """Owner-only. Render the pod-draft lobby embed in this channel.

        `state` ∈ empty | partial | linked | unlinked | ready | notready | drafting | complete | round1.
        No arg → posts every state in sequence. A specific state → edits the last in place."""
        if state and state not in _VALID_STATES:
            await ctx.send(f"unknown state `{state}`; pick one of: {', '.join(_VALID_STATES)}")
            return

        async def _register_bracket(msg: discord.Message, bracket: dict) -> None:
            prior = _BRACKETS.get(msg.id)
            if prior is not None:
                task = prior.get("grace_task")
                if task is not None and not task.done():
                    task.cancel()
                old_standings = prior.get("standings_message")
                if old_standings is not None:
                    try:
                        await old_standings.delete()
                    except discord.HTTPException:
                        pass
                old_announcement = prior.get("champion_announcement_message")
                if old_announcement is not None:
                    try:
                        await old_announcement.delete()
                    except discord.HTTPException:
                        pass

            current_round = bracket["round"]
            current_matches = bracket["matches_by_round"][current_round]
            _BRACKETS[msg.id] = {
                "players": bracket["players"],
                "round": current_round,
                "matches_by_round": dict(bracket["matches_by_round"]),
                "outcomes": list(bracket["outcomes"]),
                "invoker": ctx.author,
                "round_messages": {current_round: msg},
                "grace_task": None,
                "grace_round": None,
                "player_colors": {},
                "screenshots": {},
                "screenshot_captions": {},
                "champion_announced": False,
                "champion_announcement_message": None,
            }
            pairing = _find_invoker_match(current_matches, _INVOKER_SEAT)
            if pairing is not None:
                _, opp = pairing
                await _dm_invoker_pairing(
                    ctx.author, current_round, opp, _test_arena_for(opp),
                    pairings_url=msg.jump_url,
                )

        if state == "":
            for s in _VALID_STATES:
                embed, view, bracket = _build(s)
                msg = await ctx.send(embed=embed, view=view)
                if bracket is not None:
                    await _register_bracket(msg, bracket)
            return

        embed, view, bracket = _build(state)
        last = _LAST_MESSAGE.get(ctx.channel.id)
        if last is not None:
            try:
                await last.edit(embed=embed, view=view, attachments=[])
                if bracket is not None:
                    await _register_bracket(last, bracket)
                return
            except discord.HTTPException:
                _LAST_MESSAGE.pop(ctx.channel.id, None)
        msg = await ctx.send(embed=embed, view=view)
        _LAST_MESSAGE[ctx.channel.id] = msg
        if bracket is not None:
            await _register_bracket(msg, bracket)
