"""Discord-driven Swiss bracket for the pod-draft post-draft phase.

After endDraft, the manager hands control here. We snapshot the roster, run pod_swiss for pairings,
persist pending pod_draft_matches rows, and post ONE message per round: a single embed listing all
pairings + one Select dropdown per match (placeholder "Report A vs B"). Players pick results; the
embed updates in place as each match is reported. When the round is fully reported, the next round
is paired and posted. Round 3 completion triggers champion finalization and the standings post.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import discord
from discord import ui

from bot.services import pod_swiss
from bot.services.pod_swiss import MatchOutcome, Player


if TYPE_CHECKING:
    from bot.services.pod_draft_manager import PodDraftManager


log = logging.getLogger(__name__)

TOTAL_ROUNDS = 3
SELECT_CUSTOM_PREFIX = "podmatchresult"
MAX_MATCHES_PER_ROUND = 5  # Discord caps ActionRows at 5; supports pods up to 10 players
SKIPPED_SENTINEL = "(skipped)"  # winner_name value for "Not played" matches


async def start_tournament(manager: "PodDraftManager") -> None:
    """Snapshot the Draftmancer roster, post Round 1 pairings + result dropdowns in the thread."""
    roster = list(manager.tournament_roster)
    if len(roster) < 2:
        log.warning("not enough players in roster for %s: %s", manager.event_id, roster)
        return
    if len(roster) % 2 != 0:
        log.warning("odd-numbered roster (%d players) for %s — Swiss not supported", len(roster), manager.event_id)
        return

    manager.tournament_players = [Player(id=name, name=name) for name in roster]
    await advance_to_round(manager, 1)


async def advance_to_round(manager: "PodDraftManager", round_num: int) -> None:
    """Compute pairings for round_num via pod_swiss, persist pending rows, post pairings + views."""
    players = manager.tournament_players
    prior = await asyncio.to_thread(_load_matches, manager.event_id)
    try:
        pairings = pod_swiss.pair_round(players, prior, round_num)
    except ValueError as e:
        log.error("pairing for round %d failed for %s: %s", round_num, manager.event_id, e)
        return

    pending_rows = await asyncio.to_thread(_insert_pending_matches, manager.event_id, round_num, pairings)
    manager.current_round = round_num

    thread = await manager._fetch_thread()
    if thread is None:
        return

    standings_by_id = {s.player_id: s for s in pod_swiss.compute_standings(players, prior)}
    match_states = [_state_for_pending(match_id, a, b, standings_by_id) for match_id, a, b in pending_rows]
    embed = _round_embed(round_num, match_states)
    view = RoundResultsView(match_states)
    try:
        await thread.send(embed=embed, view=view)
    except Exception:
        log.warning("could not post round %d message", round_num, exc_info=True)


def _state_for_pending(match_id: str, a_name: str, b_name: str, standings_by_id) -> dict:
    a_s = standings_by_id.get(a_name)
    b_s = standings_by_id.get(b_name)
    return {
        "match_id": match_id,
        "a_name": a_name,
        "b_name": b_name,
        "a_record": f"{a_s.wins}-{a_s.losses}" if a_s else "0-0",
        "b_record": f"{b_s.wins}-{b_s.losses}" if b_s else "0-0",
        "winner_name": None,
        "score": None,
    }


def _round_embed(round_num: int, match_states: list[dict]) -> discord.Embed:
    all_done = all(m["winner_name"] for m in match_states)
    title = (
        f"✅ Round {round_num} complete!" if all_done else f"━━━ Round {round_num} Pairings ━━━"
    )
    lines: list[str] = []
    for m in match_states:
        winner = m["winner_name"]
        if winner == SKIPPED_SENTINEL:
            lines.append(f"🚫 No match played: {m['a_name']} vs {m['b_name']}")
        elif winner:
            loser = m["b_name"] if winner.lower() == m["a_name"].lower() else m["a_name"]
            lines.append(f"🎮 {winner} wins {m['score']} vs {loser}")
        elif round_num > 1:
            lines.append(f"⚔️ {m['a_name']} ({m['a_record']})  vs  {m['b_name']} ({m['b_record']})")
        else:
            lines.append(f"⚔️ {m['a_name']}  vs  {m['b_name']}")
    return discord.Embed(
        title=title,
        description="\n".join(lines),
        color=discord.Color.green(),
    )


def _load_matches(event_id: str) -> list[MatchOutcome]:
    """Loads played matches only — skipped/no-match-played rows are excluded from standings."""
    from bot.database import SessionLocal
    from bot.models import PodDraftMatch
    from sqlalchemy import select
    with SessionLocal() as session:
        rows = session.execute(
            select(PodDraftMatch)
            .where(
                PodDraftMatch.event_id == event_id,
                PodDraftMatch.winner_name.is_not(None),
                PodDraftMatch.winner_name != SKIPPED_SENTINEL,
            )
            .order_by(PodDraftMatch.round, PodDraftMatch.reported_at)
        ).scalars().all()
        return [
            MatchOutcome(
                round_num=r.round,
                player_a_id=r.player_a_name,
                player_b_id=r.player_b_name,
                winner_id=r.winner_name,
                score=r.score or "2-0",
            )
            for r in rows
        ]


def _insert_pending_matches(event_id: str, round_num: int, pairings: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    from bot.database import SessionLocal
    from bot.services.pod_drafts import add_pairing
    out: list[tuple[str, str, str]] = []
    with SessionLocal() as session:
        for a_name, b_name in pairings:
            row = add_pairing(session, event_id, round_num, a_name, b_name)
            out.append((row.id, a_name, b_name))
        session.commit()
    return out


class MatchResultSelect(ui.Select):
    """Per-match dropdown; placeholder reads 'Report A vs B'. Match_id is encoded in option values."""

    def __init__(self, slot: int, match_id: str = "", a_name: str = "", b_name: str = "",
                 selected_value: str | None = None, winner_name: str | None = None):
        if match_id and a_name and b_name:
            placeholder = f"{a_name} vs {b_name}"
            values = [
                (f"{a_name} wins: 2-0", f"{match_id}|{a_name}|2-0"),
                (f"{a_name} wins: 2-1", f"{match_id}|{a_name}|2-1"),
                (f"{b_name} wins: 2-1", f"{match_id}|{b_name}|2-1"),
                (f"{b_name} wins: 2-0", f"{match_id}|{b_name}|2-0"),
                ("No Match Played", f"{match_id}|{SKIPPED_SENTINEL}|0-0"),
            ]
            options = [
                discord.SelectOption(label=label, value=val, default=(val == selected_value))
                for label, val in values
            ]
        else:
            placeholder = "Result"
            options = [discord.SelectOption(label="—", value="placeholder")]
        super().__init__(
            custom_id=f"{SELECT_CUSTOM_PREFIX}:{slot}",
            placeholder=placeholder,
            options=options,
            min_values=1,
            max_values=1,
            row=slot,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await _handle_result_submission(interaction, self.values[0])


class RoundResultsView(ui.View):
    """One View per round; holds up to MAX_MATCHES_PER_ROUND Selects, one per match."""

    def __init__(self, match_states: list[dict] | None = None):
        super().__init__(timeout=None)
        if match_states:
            for slot, m in enumerate(match_states):
                selected = None
                if m.get("winner_name") and m.get("score"):
                    selected = f"{m['match_id']}|{m['winner_name']}|{m['score']}"
                self.add_item(MatchResultSelect(
                    slot=slot,
                    match_id=m["match_id"],
                    a_name=m["a_name"],
                    b_name=m["b_name"],
                    selected_value=selected,
                ))
        else:
            # Persistent template covering all possible slots; real messages will only render the slots they need
            for slot in range(MAX_MATCHES_PER_ROUND):
                self.add_item(MatchResultSelect(slot=slot))


async def _handle_result_submission(interaction: discord.Interaction, value: str) -> None:
    if value == "placeholder":
        await interaction.response.send_message("This dropdown isn't bound to a match yet.", ephemeral=True)
        return
    try:
        match_id, winner_name, score = value.split("|", 2)
    except ValueError:
        await interaction.response.send_message("Malformed result option.", ephemeral=True)
        return

    result = await asyncio.to_thread(_commit_result, match_id, winner_name, score)
    if result == "not_found":
        await interaction.response.send_message("Could not find this match in the database.", ephemeral=True)
        return

    round_num = result["round"]
    event_id = result["event_id"]
    match_states = await asyncio.to_thread(_load_round_states, event_id, round_num)
    embed = _round_embed(round_num, match_states)
    view = RoundResultsView(match_states)
    try:
        await interaction.response.edit_message(content=None, embed=embed, view=view)
    except Exception:
        log.warning("could not edit round message", exc_info=True)
    await _maybe_advance(interaction.client, event_id, round_num)


def _load_round_states(event_id: str, round_num: int) -> list[dict]:
    """Re-read all matches for a round + each player's standings-to-date so the embed reflects live state."""
    from bot.database import SessionLocal
    from bot.models import PodDraftMatch
    from sqlalchemy import select
    with SessionLocal() as session:
        rows = session.execute(
            select(PodDraftMatch)
            .where(PodDraftMatch.event_id == event_id, PodDraftMatch.round == round_num)
            .order_by(PodDraftMatch.id)
        ).scalars().all()
    prior = _load_matches(event_id)
    # Build standings as of the start of this round (use only earlier-round results)
    pre_round = [m for m in prior if m.round_num < round_num]
    distinct_names = {n for r in rows for n in (r.player_a_name, r.player_b_name)}
    players = [Player(id=n, name=n) for n in sorted(distinct_names)]
    standings_by_id = {s.player_id: s for s in pod_swiss.compute_standings(players, pre_round)}
    states = []
    for r in rows:
        a_s = standings_by_id.get(r.player_a_name)
        b_s = standings_by_id.get(r.player_b_name)
        states.append({
            "match_id": r.id,
            "a_name": r.player_a_name,
            "b_name": r.player_b_name,
            "a_record": f"{a_s.wins}-{a_s.losses}" if a_s else "0-0",
            "b_record": f"{b_s.wins}-{b_s.losses}" if b_s else "0-0",
            "winner_name": r.winner_name,
            "score": r.score,
        })
    return states


def _commit_result(match_id: str, winner_name: str, score: str):
    from bot.database import SessionLocal
    from bot.models import PodDraftMatch
    from bot.services.pod_drafts import set_match_result
    with SessionLocal() as session:
        match = session.get(PodDraftMatch, match_id)
        if match is None:
            return "not_found"
        # Allow editing — overwrite winner/score on each submission
        set_match_result(session, match_id, winner_name, score)
        session.commit()
        loser = match.player_b_name if winner_name.lower() == match.player_a_name.lower() else match.player_a_name
        return {
            "loser_name": loser,
            "a_name": match.player_a_name,
            "b_name": match.player_b_name,
            "round": match.round,
            "event_id": match.event_id,
        }


async def _maybe_advance(bot_client, event_id: str, round_num: int) -> None:
    """If all matches in round_num have been reported, advance to next round or finalize."""
    from bot.services.pod_draft_manager import ACTIVE_POD_MANAGERS

    pending_remaining = await asyncio.to_thread(_count_pending_in_round, event_id, round_num)
    if pending_remaining > 0:
        return

    manager = ACTIVE_POD_MANAGERS.get(event_id)
    if manager is None:
        log.warning("round %d complete for %s but no active manager — re-run !testbracket",
                    round_num, event_id)
        return

    if round_num >= TOTAL_ROUNDS:
        if not manager.finalized:
            await finalize_tournament(manager)
        return
    next_exists = await asyncio.to_thread(_round_has_rows, event_id, round_num + 1)
    if not next_exists:
        await advance_to_round(manager, round_num + 1)


def _count_pending_in_round(event_id: str, round_num: int) -> int:
    from bot.database import SessionLocal
    from bot.models import PodDraftMatch
    from sqlalchemy import func, select
    with SessionLocal() as session:
        return session.execute(
            select(func.count(PodDraftMatch.id))
            .where(
                PodDraftMatch.event_id == event_id,
                PodDraftMatch.round == round_num,
                PodDraftMatch.winner_name.is_(None),
            )
        ).scalar_one() or 0


def _round_has_rows(event_id: str, round_num: int) -> bool:
    from bot.database import SessionLocal
    from bot.models import PodDraftMatch
    from sqlalchemy import func, select
    with SessionLocal() as session:
        count = session.execute(
            select(func.count(PodDraftMatch.id))
            .where(PodDraftMatch.event_id == event_id, PodDraftMatch.round == round_num)
        ).scalar_one() or 0
        return count > 0


async def finalize_tournament(manager: "PodDraftManager") -> None:
    if manager.finalized:
        return
    manager.finalized = True
    prior = await asyncio.to_thread(_load_matches, manager.event_id)
    players = manager.tournament_players
    standings = pod_swiss.compute_standings(players, prior)

    from bot.services.pod_drafts import FinalStanding, finalize_champion as finalize_db

    final_standings = [
        FinalStanding(
            draftmancer_name=s.player_name,
            placement=s.rank,
            record=f"{s.wins}-{s.losses}",
            eliminated_round=None if s.rank == 1 else TOTAL_ROUNDS,
            draft_log_url=None,
        )
        for s in standings
    ]

    def _do_write() -> None:
        from bot.database import SessionLocal
        with SessionLocal() as session:
            finalize_db(session, manager.event_id, final_standings)
            session.commit()
    await asyncio.to_thread(_do_write)

    champion = standings[0]
    champion_mention = await _resolve_discord_mention(manager.event_id, champion.player_name)
    champ_display = champion_mention or f"**{champion.player_name}**"
    medals = ["🥇", "🥈", "🥉"]
    standings_lines = []
    for s in standings:
        prefix = medals[s.rank - 1] if s.rank - 1 < len(medals) else "   "
        standings_lines.append(f"{prefix} {s.player_name}  {s.wins}-{s.losses}")
    embed = discord.Embed(
        title=f"🏆 Pod Draft Champion: {champion.player_name}",
        description=(
            f"{champ_display} wins {champion.wins}-{champion.losses}!\n\n"
            f"**Final standings:**\n" + "\n".join(standings_lines)
            + "\n\nPost your final decklist screenshot in this thread! 🎴"
        ),
        color=discord.Color.green(),
    )

    if hasattr(manager, "share_draft_log"):
        await manager.share_draft_log()

    thread = await manager._fetch_thread()
    if thread is not None:
        try:
            await thread.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        except Exception:
            log.warning("could not post standings", exc_info=True)
    await manager.disconnect_safely()


async def _resolve_discord_mention(event_id: str, draftmancer_name: str) -> str | None:
    def _query() -> str | None:
        from bot.database import SessionLocal
        from bot.models import Player, PodDraftParticipant
        from sqlalchemy import func, select
        with SessionLocal() as session:
            participant = session.execute(
                select(PodDraftParticipant).where(
                    PodDraftParticipant.event_id == event_id,
                    func.lower(PodDraftParticipant.draftmancer_name) == draftmancer_name.lower(),
                )
            ).scalar_one_or_none()
            if participant is None or participant.player_id is None:
                return None
            player = session.get(Player, participant.player_id)
            if player is None or not player.discord_id:
                return None
            return f"<@{player.discord_id}>"
    return await asyncio.to_thread(_query)


def register_persistent_views(bot) -> None:
    """Register a template RoundResultsView so dropdown interactions dispatch after restart."""
    bot.add_view(RoundResultsView())


class HollowManager:
    """Manager-shaped stand-in for !testbracket — no socket, just enough state for the bracket flow."""

    def __init__(self, bot, event_id: str, thread_id: int, roster: list[str]) -> None:
        self.bot = bot
        self.event_id = event_id
        self.thread_id = thread_id
        self.tournament_roster = roster
        self.tournament_players: list = []
        self.current_round = 0
        self.finalized = False

    async def _fetch_thread(self):
        try:
            return await self.bot.fetch_channel(self.thread_id)
        except Exception:
            log.warning("could not fetch thread %s", self.thread_id, exc_info=True)
            return None

    async def disconnect_safely(self) -> None:
        from bot.services.pod_draft_manager import ACTIVE_POD_MANAGERS
        ACTIVE_POD_MANAGERS.pop(self.event_id, None)


async def reset_event_matches(event_id: str) -> int:
    """Delete all pod_draft_matches rows for an event. Returns number deleted."""
    def _do() -> int:
        from bot.database import SessionLocal
        from bot.models import PodDraftMatch
        from sqlalchemy import delete
        with SessionLocal() as session:
            result = session.execute(
                delete(PodDraftMatch).where(PodDraftMatch.event_id == event_id)
            )
            session.commit()
            return result.rowcount or 0
    return await asyncio.to_thread(_do)
