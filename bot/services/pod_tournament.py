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
from datetime import datetime, timezone
from typing import TYPE_CHECKING, NamedTuple

import discord
from discord import ui
from sqlalchemy import delete, func, select

from bot import emojis
from bot.config import settings
from bot.slug import slugify
from bot.database import SessionLocal
from bot.models import Player as DbPlayer, PodDraftEvent, PodDraftMatch, PodDraftParticipant
from bot.services import pod_swiss
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_deck_color import PAIR_EMOJI_NAME, NotInPodError, SubmitDeckView
from bot.services.pod_replays import fetch_and_persist_replays_for_player
from bot.services.seventeenlands import SeventeenLandsClient
from bot.services.pod_drafts import (
    FinalStanding,
    _normalize_player_name,
    _normalized_column,
    add_pairing,
    finalize_champion as finalize_db,
    get_participant_deck_state,
    participant_dm_info,
    seed_event_participants,
    set_match_result,
    set_participant_deck_colors,
    set_participant_review_choice,
)
from bot.services.pod_swiss import MatchOutcome, Player


if TYPE_CHECKING:
    from bot.services.pod_draft_manager import PodDraftManager


log = logging.getLogger(__name__)

TOTAL_ROUNDS = 3
SELECT_CUSTOM_PREFIX = "podmatchresult"
MAX_MATCHES_PER_ROUND = 5  # Discord caps ActionRows at 5; supports pods up to 10 players
SKIPPED_SENTINEL = "(skipped)"  # winner_name value for "Not played" matches
GRACE_SECONDS = 60  # window after round completion during which edits regenerate the next round
ANNOUNCEMENT_TOP_N = 4  # channel-level announcement shows top performers only; thread keeps full standings

# Test-only result handler hook (set by bot/commands/testlobby.py). Always None in prod.
_test_result_handler = None
_test_handler_prefix: str | None = None


async def _dm_round_pairings(
    bot_client,
    event_id: str,
    round_num: int,
    pending_rows: list[tuple[str, str, str]],
    pairings_url: str,
) -> None:
    """DM each linked participant their opponent for this round."""
    dm_info = await asyncio.to_thread(_load_dm_info_sync, event_id)
    event_name = await asyncio.to_thread(_load_event_name_sync, event_id)
    for _match_id, a_name, b_name in pending_rows:
        a_key = _normalize_player_name(a_name)
        b_key = _normalize_player_name(b_name)
        await _send_pairing_dm(bot_client, dm_info, a_key, b_key, round_num, pairings_url, event_name=event_name)
        await _send_pairing_dm(bot_client, dm_info, b_key, a_key, round_num, pairings_url, event_name=event_name)


def _load_dm_info_sync(event_id: str):
    with SessionLocal() as session:
        return participant_dm_info(session, event_id)


class ParticipantDeckData(NamedTuple):
    colors: str | None
    screenshot_url: str | None
    screenshot_caption: str | None
    draft_log_url: str | None
    wants_draft_review: bool | None = None


def _load_event_deck_data_sync(event_id: str) -> dict[str, ParticipantDeckData]:
    """Return normalized_name → deck colors + screenshot URL + caption + MPT URL + review opt-in for every participant."""
    with SessionLocal() as session:
        rows = session.execute(
            select(
                PodDraftParticipant.draftmancer_name,
                PodDraftParticipant.display_name,
                PodDraftParticipant.deck_colors,
                PodDraftParticipant.deck_screenshot_url,
                PodDraftParticipant.deck_screenshot_caption,
                PodDraftParticipant.draft_log_url,
                PodDraftParticipant.wants_draft_review,
            )
            .where(PodDraftParticipant.event_id == event_id)
        ).all()
    out: dict[str, ParticipantDeckData] = {}
    for dm, dn, dc, ds, dcap, dlog, dreview in rows:
        data = ParticipantDeckData(
            colors=dc, screenshot_url=ds, screenshot_caption=dcap, draft_log_url=dlog,
            wants_draft_review=dreview,
        )
        for src in (dm, dn):
            if src:
                out[_normalize_player_name(src)] = data
    return out


def _colors_only(deck_data: dict[str, ParticipantDeckData]) -> dict[str, str | None]:
    return {k: v.colors for k, v in deck_data.items()}


def _load_event_name_sync(event_id: str) -> str:
    with SessionLocal() as session:
        return session.execute(
            select(PodDraftEvent.name).where(PodDraftEvent.id == event_id)
        ).scalar_one_or_none() or "Pod Draft"


def _load_event_started_at_sync(event_id: str) -> datetime | None:
    with SessionLocal() as session:
        return session.execute(
            select(PodDraftEvent.event_time).where(PodDraftEvent.id == event_id)
        ).scalar_one_or_none()


def _short_event_name(event_name: str | None) -> str | None:
    """Drops anything after the first ' - '."""
    if not event_name:
        return None
    return event_name.split(" - ", 1)[0].strip()


_RANK_MEDALS: dict[int, str] = {1: "🥇", 2: "🥈", 3: "🥉"}


def _build_standings_row(
    s: pod_swiss.Standing,
    *,
    displays: dict[str, dict],
    player_colors: dict[str, str | None],
    deck_data: dict[str, ParticipantDeckData],
    site_root: str | None,
    show_review_flag: bool = False,
    inline_caption: bool = False,
) -> str:
    """One standings row used by both the V2 announcement and the thread-side classic embed:
    `{rank}. {medal} {name}  {wins}-{losses}  {colors}  [Draft Log]({url}) 📜`.
    Set show_review_flag for the in-thread variant to append 🙋 for review opt-ins. Set
    inline_caption to splice an italicized caption between the W-L record and the color glyph."""
    key = _normalize_player_name(s.player_name)
    info = displays.get(key, {})
    name = info.get("display_name") or s.player_name
    slug = info.get("slug")
    data = deck_data.get(key)
    prefix = f"{s.rank}. {_RANK_MEDALS[s.rank]} " if s.rank in _RANK_MEDALS else f"{s.rank}. "
    rendered = (
        f"[{name}]({site_root}/player/{slug})"
        if slug and site_root else name
    )
    color_glyph = _format_deck_color_emojis(player_colors.get(key))
    color_suffix = f"  {color_glyph}" if color_glyph else ""
    log_suffix = (
        f"  [Draft Log]({data.draft_log_url}) 📜"
        if data is not None and data.draft_log_url else ""
    )
    review_suffix = " 🙋" if show_review_flag and data is not None and data.wants_draft_review else ""
    caption_inline = (
        f"  _{_escape_italics(data.screenshot_caption.strip())}_"
        if inline_caption and data is not None and data.screenshot_caption else ""
    )
    return (
        f"{prefix}{rendered}  {s.wins}-{s.losses}"
        f"{caption_inline}{color_suffix}{log_suffix}{review_suffix}"
    )


def build_pairing_dm_embed(
    *,
    round_num: int,
    opponent_label: str,
    opponent_arena: str | None,
    pairings_url: str | None,
    event_name: str | None = None,
    updated: bool = False,
) -> discord.Embed:
    """Single source of truth for round-start + pairings-updated DMs.

    `opponent_label` is the pre-formatted opponent string — `<@id>` mention in production,
    or `**Bold Name**` for testlobby (no real Discord ID). Both call sites prepare this and
    pass it in, so every other string in the embed lives here.
    """
    short = _short_event_name(event_name)
    suffix = "Updated" if updated else "Started"
    title_round = f"Round {round_num} {suffix}"
    title = f"{short} · {title_round}" if short else title_round

    mtga = emojis.get("mtga")
    arena_part = f" {mtga} `{opponent_arena}`" if opponent_arena else ""
    body_lines = [f"Opponent: {opponent_label}{arena_part}"]
    if pairings_url:
        link_prefix = emojis.get("manat") or "↳"
        body_lines.append(f"{link_prefix} [View pairings]({pairings_url})")

    return discord.Embed(
        title=title,
        description="\n".join(body_lines),
        color=discord.Color.yellow() if updated else discord.Color.green(),
    )


async def _send_pairing_dm(
    bot_client,
    dm_info: dict,
    recipient_key: str,
    opponent_key: str,
    round_num: int,
    pairings_url: str,
    event_name: str | None = None,
    updated: bool = False,
) -> None:
    recipient = dm_info.get(recipient_key)
    if recipient is None or not recipient.discord_id:
        return
    opponent = dm_info.get(opponent_key)
    opp_label = (
        f"<@{opponent.discord_id}>" if opponent and opponent.discord_id
        else f"**{opponent.display_name if opponent else opponent_key}**"
    )
    opp_arena = opponent.arena_name if opponent else None
    embed = build_pairing_dm_embed(
        round_num=round_num,
        opponent_label=opp_label,
        opponent_arena=opp_arena,
        pairings_url=pairings_url,
        event_name=event_name,
        updated=updated,
    )
    try:
        user = bot_client.get_user(int(recipient.discord_id)) or await bot_client.fetch_user(int(recipient.discord_id))
        await user.send(embed=embed)
    except discord.Forbidden:
        log.info("pairing DM blocked for user %s", recipient.discord_id)
    except discord.HTTPException:
        log.warning("pairing DM failed", exc_info=True)


async def live_deck_state_lookup(interaction: discord.Interaction) -> tuple[str | None, bool | None]:
    """Resolve the participant by (thread, user); raise NotInPodError if the user isn't in this pod.
    Returns (deck_colors, wants_draft_review)."""
    thread_id = str(interaction.channel_id)
    discord_id = str(interaction.user.id)

    def _do() -> tuple[bool, str | None, bool | None]:
        with SessionLocal() as session:
            return get_participant_deck_state(session, thread_id, discord_id)

    in_pod, color, wants_review = await asyncio.to_thread(_do)
    if not in_pod:
        raise NotInPodError()
    return color or None, wants_review


async def live_deck_color_submit(interaction: discord.Interaction, color: str) -> None:
    thread_id = str(interaction.channel_id)
    discord_id = str(interaction.user.id)

    def _do() -> tuple[bool, str | None]:
        with SessionLocal() as session:
            ok = set_participant_deck_colors(session, thread_id, discord_id, color)
            if not ok:
                return False, None
            event_id = session.execute(
                select(PodDraftEvent.id).where(PodDraftEvent.discord_thread_id == thread_id)
            ).scalar_one_or_none()
            session.commit()
            return True, event_id

    ok, event_id = await asyncio.to_thread(_do)
    if not ok:
        raise NotInPodError()

    if event_id is None:
        return
    manager = ACTIVE_POD_MANAGERS.get(event_id)
    if manager is not None:
        await _post_or_update_live_standings(manager)
        # Color submit edits an existing announcement but never triggers the first post —
        # screenshot upload (or grace expiry) is the only thing that creates it.
        if manager.champion_announced:
            await _announce_or_update_champion(manager)


async def live_review_choice_submit(interaction: discord.Interaction, wants_review: bool) -> None:
    thread_id = str(interaction.channel_id)
    discord_id = str(interaction.user.id)

    def _do() -> tuple[bool, str | None]:
        with SessionLocal() as session:
            ok = set_participant_review_choice(session, thread_id, discord_id, wants_review)
            if not ok:
                return False, None
            event_id = session.execute(
                select(PodDraftEvent.id).where(PodDraftEvent.discord_thread_id == thread_id)
            ).scalar_one_or_none()
            session.commit()
            return True, event_id

    ok, event_id = await asyncio.to_thread(_do)
    if not ok:
        raise NotInPodError()

    if event_id is None:
        return
    manager = ACTIVE_POD_MANAGERS.get(event_id)
    if manager is not None:
        await _post_or_update_live_standings(manager)


def build_live_submit_deck_view() -> SubmitDeckView:
    return SubmitDeckView(live_deck_color_submit, live_deck_state_lookup, live_review_choice_submit)


def register_test_result_handler(prefix: str, handler) -> None:
    """Plug a test handler into the result-submission dispatch (testlobby preview only)."""
    global _test_result_handler, _test_handler_prefix
    _test_handler_prefix = prefix
    _test_result_handler = handler


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
    # Idempotent re-seed — _start_draft already seeded at draft-start time. Kept as a safety net
    # in case that call didn't fire cleanly (bot restart mid-draft, etc).
    await asyncio.to_thread(_seed_participants_sync, manager.event_id, roster)
    await advance_to_round(manager, 1)


def _seed_participants_sync(event_id: str, roster: list[str]) -> None:
    with SessionLocal() as session:
        seed_event_participants(session, event_id, roster)
        session.commit()


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
    displays = await asyncio.to_thread(_load_participant_displays, manager.event_id)
    match_states = [_state_for_pending(match_id, a, b, standings_by_id, displays) for match_id, a, b in pending_rows]
    _mark_trophy_match(match_states, round_num)
    embed = _round_embed(round_num, match_states)
    view = RoundResultsView(match_states)
    posted: discord.Message | None = None
    try:
        posted = await thread.send(embed=embed, view=view)
    except Exception:
        log.warning("could not post round %d message", round_num, exc_info=True)

    if posted is not None:
        manager.round_messages[round_num] = posted
        await _dm_round_pairings(manager.bot, manager.event_id, round_num, pending_rows, posted.jump_url)


class MatchResultSelect(ui.Select):
    """Per-match dropdown; placeholder + labels use Discord display names. Option values still encode
    the draftmancer_name (DB primary key) so result commits resolve correctly."""

    def __init__(self, slot: int, match_id: str = "", a_name: str = "", b_name: str = "",
                 a_display: str = "", b_display: str = "",
                 selected_value: str | None = None, winner_name: str | None = None,
                 is_trophy_match: bool = False):
        if match_id and a_name and b_name:
            a_disp = a_display or a_name
            b_disp = b_display or b_name
            base = f"🏆 {a_disp} vs {b_disp} 🏆" if is_trophy_match else f"{a_disp} vs {b_disp}"
            placeholder = base if selected_value else f"⚔️ {base}"
            values = [
                (f"{a_disp} wins: 2-0", f"{match_id}|{a_name}|2-0", True),
                (f"{a_disp} wins: 2-1", f"{match_id}|{a_name}|2-1", True),
                (f"{b_disp} wins: 2-1", f"{match_id}|{b_name}|2-1", True),
                (f"{b_disp} wins: 2-0", f"{match_id}|{b_name}|2-0", True),
                ("No Match Played", f"{match_id}|{SKIPPED_SENTINEL}|0-0", False),
            ]
            options = [
                discord.SelectOption(
                    label=f"🏆 {label}" if (is_trophy_match and trophy_eligible) else label,
                    value=val,
                    default=(val == selected_value),
                )
                for label, val, trophy_eligible in values
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
                    a_display=m.get("a_display") or m["a_name"],
                    b_display=m.get("b_display") or m["b_name"],
                    selected_value=selected,
                    is_trophy_match=bool(m.get("is_trophy_match")),
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

    if (_test_result_handler is not None and _test_handler_prefix
            and match_id.startswith(_test_handler_prefix)):
        await _test_result_handler(interaction, match_id, winner_name, score)
        return

    result = await asyncio.to_thread(_commit_result, match_id, winner_name, score)
    if result == "not_found":
        try:
            await interaction.response.defer()
        except discord.HTTPException:
            pass
        return

    round_num = result["round"]
    event_id = result["event_id"]
    match_states = await asyncio.to_thread(_load_round_states, event_id, round_num)
    _mark_trophy_match(match_states, round_num)
    embed = _round_embed(round_num, match_states)
    view = RoundResultsView(match_states)
    try:
        await interaction.response.edit_message(content=None, embed=embed, view=view)
    except Exception:
        log.warning("could not edit round message", exc_info=True)
    await _maybe_advance(interaction.client, event_id, round_num)
    if round_num >= TOTAL_ROUNDS:
        asyncio.create_task(_fetch_replays_for_match_players(
            event_id, result["a_name"], result["b_name"],
        ))


def _load_round_states(event_id: str, round_num: int) -> list[dict]:
    """Re-read all matches for a round + each player's standings-to-date so the embed reflects live state."""
    with SessionLocal() as session:
        rows = session.execute(
            select(PodDraftMatch)
            .where(PodDraftMatch.event_id == event_id, PodDraftMatch.round == round_num)
            .order_by(PodDraftMatch.pairing_index)
        ).scalars().all()
    prior = _load_matches(event_id)
    # Build standings as of the start of this round (use only earlier-round results)
    pre_round = [m for m in prior if m.round_num < round_num]
    distinct_names = {n for r in rows for n in (r.player_a_name, r.player_b_name)}
    players = [Player(id=n, name=n) for n in sorted(distinct_names)]
    standings_by_id = {s.player_id: s for s in pod_swiss.compute_standings(players, pre_round)}
    displays = _load_participant_displays(event_id)
    states = []
    for r in rows:
        a_s = standings_by_id.get(r.player_a_name)
        b_s = standings_by_id.get(r.player_b_name)
        a_info = displays.get(_normalize_player_name(r.player_a_name), {})
        b_info = displays.get(_normalize_player_name(r.player_b_name), {})
        states.append({
            "match_id": r.id,
            "a_name": r.player_a_name,
            "b_name": r.player_b_name,
            "a_display": a_info.get("display_name") or r.player_a_name,
            "b_display": b_info.get("display_name") or r.player_b_name,
            "a_record": f"{a_s.wins}-{a_s.losses}" if a_s else "0-0",
            "b_record": f"{b_s.wins}-{b_s.losses}" if b_s else "0-0",
            "winner_name": r.winner_name,
            "score": r.score,
        })
    return states


def _commit_result(match_id: str, winner_name: str, score: str):
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


async def _fetch_replays_for_match_players(event_id: str, a_name: str, b_name: str) -> None:
    pairs = await asyncio.to_thread(_resolve_match_player_tokens_sync, event_id, a_name, b_name)
    if not pairs:
        return
    client = SeventeenLandsClient()
    for player_id, seat_name, token in pairs:
        await fetch_and_persist_replays_for_player(client, event_id, player_id, seat_name, token)


def _resolve_match_player_tokens_sync(
    event_id: str, a_name: str, b_name: str,
) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    with SessionLocal() as session:
        for seat_name in (a_name, b_name):
            row = session.execute(
                select(PodDraftParticipant.player_id, DbPlayer.seventeenlands_token)
                .join(DbPlayer, DbPlayer.id == PodDraftParticipant.player_id)
                .where(
                    PodDraftParticipant.event_id == event_id,
                    PodDraftParticipant.draftmancer_name == seat_name,
                )
            ).first()
            if row is None:
                continue
            player_id, token = row
            if not token:
                continue
            out.append((player_id, seat_name, token))
    return out


async def _maybe_advance(bot_client, event_id: str, round_num: int) -> None:
    """Advance, finalize, or regenerate-on-edit, depending on round state.

    First time a round completes → advance to N+1 (or for R3 start the finalize grace).
    Edit during the grace window → regenerate N+1 (or refresh standings for R3) and reset the timer.
    Once the grace timer expires → lock the round-N view and (for R3) finalize.
    """
    manager = ACTIVE_POD_MANAGERS.get(event_id)

    if round_num == TOTAL_ROUNDS and manager is not None:
        await _post_or_update_live_standings(manager)

    pending_remaining = await asyncio.to_thread(_count_pending_in_round, event_id, round_num)
    if pending_remaining > 0:
        return

    if manager is None:
        log.warning("round %d complete for %s but no active manager — re-run !testbracket",
                    round_num, event_id)
        return

    is_edit_during_grace = (manager.grace_round == round_num and manager.grace_task is not None)

    if is_edit_during_grace:
        if round_num < TOTAL_ROUNDS:
            await _regenerate_next_round(manager, round_num + 1)
        _schedule_grace(manager, round_num)
        return

    if round_num >= TOTAL_ROUNDS:
        _schedule_grace(manager, round_num)
        return

    next_exists = await asyncio.to_thread(_round_has_rows, event_id, round_num + 1)
    if not next_exists:
        await advance_to_round(manager, round_num + 1)
    _schedule_grace(manager, round_num)


def _count_pending_in_round(event_id: str, round_num: int) -> int:
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
        with SessionLocal() as session:
            finalize_db(session, manager.event_id, final_standings)
            session.commit()
    await asyncio.to_thread(_do_write)

    # The standings embed was already posted (and live-edited) by _post_or_update_live_standings
    # once the trophy matches resolved. Final pass to make sure it reflects the very last result.
    await _post_or_update_live_standings(manager)

    if hasattr(manager, "share_draft_log"):
        await manager.share_draft_log()

    champion_mention = await _resolve_discord_mention(manager.event_id, standings[0].player_name)
    thread = await manager._fetch_thread()
    if thread is not None and champion_mention:
        try:
            await thread.send(
                content=f"Congrats {champion_mention}! 🏆",
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except Exception:
            log.warning("could not send champion ping", exc_info=True)

    if hasattr(manager, "disconnect_safely"):
        await manager.disconnect_safely()


def _load_participant_slugs(event_id: str) -> dict[str, str]:
    """Map normalized draftmancer_name → Player.slug for participants linked to a Player."""
    with SessionLocal() as session:
        rows = session.execute(
            select(PodDraftParticipant.draftmancer_name, DbPlayer.slug)
            .join(DbPlayer, DbPlayer.id == PodDraftParticipant.player_id)
            .where(PodDraftParticipant.event_id == event_id)
        ).all()
    return {_normalize_player_name(name): slug for name, slug in rows if name}


def _load_participant_displays(event_id: str) -> dict[str, dict]:
    """Map normalized name → {'display_name', 'slug'}.

    Indexed by both draftmancer_name and the participant's display_name so pre-draft and post-draft
    participants both resolve. The display_name we *expose* prefers Player.display_name (the Discord
    display) over the participant row's display_name, which can carry stale Arena-style handles when
    the participant was created from a test/debug roster.
    """
    with SessionLocal() as session:
        rows = session.execute(
            select(
                PodDraftParticipant.draftmancer_name,
                PodDraftParticipant.display_name,
                DbPlayer.display_name,
                DbPlayer.slug,
            )
            .outerjoin(DbPlayer, DbPlayer.id == PodDraftParticipant.player_id)
            .where(PodDraftParticipant.event_id == event_id)
        ).all()
    out: dict[str, dict] = {}
    for dm, participant_dn, player_dn, slug in rows:
        info = {"display_name": player_dn or participant_dn, "slug": slug}
        if dm:
            out[_normalize_player_name(dm)] = info
        if participant_dn:
            out.setdefault(_normalize_player_name(participant_dn), info)
    return out


async def _resolve_discord_mention(event_id: str, draftmancer_name: str) -> str | None:
    def _query() -> str | None:
        with SessionLocal() as session:
            participant = session.execute(
                select(PodDraftParticipant).where(
                    PodDraftParticipant.event_id == event_id,
                    _normalized_column(PodDraftParticipant.draftmancer_name) == _normalize_player_name(draftmancer_name),
                )
            ).scalar_one_or_none()
            if participant is None or participant.player_id is None:
                return None
            player = session.get(DbPlayer, participant.player_id)
            if player is None or not player.discord_id:
                return None
            return f"<@{player.discord_id}>"
    return await asyncio.to_thread(_query)


def register_persistent_views(bot) -> None:
    """Register persistent views so component clicks dispatch after restart."""
    bot.add_view(RoundResultsView())
    bot.add_view(build_live_submit_deck_view())


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
        self.standings_message = None
        self.round_messages: dict[int, "discord.Message"] = {}
        self.grace_task = None
        self.grace_round: int | None = None
        self.champion_announced = False
        self.champion_announcement_message = None

    async def _fetch_thread(self):
        try:
            return await self.bot.fetch_channel(self.thread_id)
        except Exception:
            log.warning("could not fetch thread %s", self.thread_id, exc_info=True)
            return None

    async def disconnect_safely(self) -> None:
        ACTIVE_POD_MANAGERS.pop(self.event_id, None)


async def reset_event_matches(event_id: str) -> int:
    """Delete all pod_draft_matches rows for an event. Returns number deleted."""
    def _do() -> int:
        with SessionLocal() as session:
            result = session.execute(
                delete(PodDraftMatch).where(PodDraftMatch.event_id == event_id)
            )
            session.commit()
            return result.rowcount or 0
    return await asyncio.to_thread(_do)


def _standings_header_text(pending_count: int) -> str:
    """`'Final Standings'` when no matches pending, `'Live Standings - N match(es) pending ⏳'` otherwise."""
    if pending_count == 0:
        return "Final Standings"
    word = "match" if pending_count == 1 else "matches"
    return f"Live Standings - {pending_count} {word} pending ⏳"


def _format_deck_color_emojis(code: str | None) -> str:
    """Render deck color string as Mana font application emojis.

    - 2 distinct colors → single guild-pair emoji (`:manarw:` for WR, `:managu:` for UG, etc.)
    - 5 colors → single `:manawubrg:` emoji
    - 1, 3, or 4 colors → individual mana emojis in WUBRG order
    - Splash letters (lowercase) are promoted to full colors so a write-in like 'URGbw' shows every
      involved color equally.
    - Falls back to bare uppercase letters when the application emoji isn't loaded.
    """
    if not code:
        return ""
    seen: set[str] = set()
    for c in code.upper():
        if c in "WUBRG":
            seen.add(c)
    if not seen:
        return ""

    if len(seen) == 2:
        emoji_name = PAIR_EMOJI_NAME.get(frozenset(seen))
        if emoji_name:
            glyph = emojis.get(emoji_name)
            if glyph:
                return glyph

    if len(seen) == 5:
        glyph = emojis.get("manawubrg")
        if glyph:
            return glyph

    out = []
    for c in "WUBRG":
        if c in seen:
            glyph = emojis.get(f"mana{c.lower()}") or c
            out.append(glyph)
    return "".join(out)


def _format_champion_title(names_with_colors: list[tuple[str, str | None]], short_event: str) -> str:
    """Headline-style title — single: `Name takes {event} with {colors}`; multi: `A {colors} and B {colors} share {event}`."""
    if not names_with_colors:
        return f"🏆 {short_event}"

    if len(names_with_colors) == 1:
        name, color = names_with_colors[0]
        emoji_run = _format_deck_color_emojis(color)
        suffix = f" with {emoji_run}" if emoji_run else ""
        return f"🏆 {name} takes {short_event}{suffix}"

    chunks = []
    for name, color in names_with_colors:
        emoji_run = _format_deck_color_emojis(color)
        chunks.append(f"{name} {emoji_run}" if emoji_run else name)
    if len(chunks) == 2:
        joined = f"{chunks[0]} and {chunks[1]}"
    else:
        joined = ", ".join(chunks[:-1]) + f", and {chunks[-1]}"
    return f"🏆 {joined} share {short_event}"


def build_champion_announcement_view(
    standings: list[pod_swiss.Standing],
    *,
    event_name: str,
    displays: dict[str, dict] | None = None,
    player_colors: dict[str, str | None] | None = None,
    site_root: str | None = None,
    pending_count: int = 0,
    deck_data: dict[str, "ParticipantDeckData"] | None = None,
    guild_id: int | None = None,
    thread_id: int | None = None,
    event_started_at: datetime | None = None,
    subtitle_override: str | None = None,
) -> ui.LayoutView:
    """One-shot 'champion crowned' Components V2 layout for the pod-draft channel (not the thread).

    Layout: Container (green accent) holds the headline + localized timestamp, then the top
    ANNOUNCEMENT_TOP_N standings rows. Every player who finished with zero losses (champion) is
    rendered with an optional italicized caption line and a full-size deck shot. Everyone else in
    the top-N collapses into a single compact text block, with their deck screenshots batched
    into one MediaGallery beneath. Full standings stay in the thread embed. Thread-link button
    sits OUTSIDE the container at LayoutView top level.
    """
    displays = displays or {}
    player_colors = player_colors or {}
    deck_data = deck_data or {}

    champs_named: list[tuple[str, str | None]] = []
    for s in standings:
        if s.losses != 0:
            continue
        key = _normalize_player_name(s.player_name)
        info = displays.get(key, {})
        display = info.get("display_name") or s.player_name
        champs_named.append((display, player_colors.get(key)))

    short = _short_event_name(event_name) or event_name
    title = _format_champion_title(champs_named, short)

    view = ui.LayoutView()
    container = ui.Container(accent_colour=discord.Color.green())

    started_at = event_started_at or datetime.now(timezone.utc)
    ts = int(started_at.timestamp())
    subtitle = subtitle_override or f"**Drafted on** <t:{ts}:F>"
    container.add_item(ui.TextDisplay(f"## {title}\n{subtitle}"))
    container.add_item(ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

    # Hide rows whose record isn't yet final; the announcement re-edits when later R3 results land
    top_standings = [
        s for s in standings[:ANNOUNCEMENT_TOP_N]
        if s.wins + s.losses >= TOTAL_ROUNDS
    ]
    pending_lines: list[str] = []
    runners_up_items: list[discord.MediaGalleryItem] = []

    for s in top_standings:
        row_text = _build_standings_row(
            s, displays=displays, player_colors=player_colors,
            deck_data=deck_data, site_root=site_root,
            inline_caption=True,
        )
        key = _normalize_player_name(s.player_name)
        data = deck_data.get(key)
        info = displays.get(key, {})
        name = info.get("display_name") or s.player_name
        is_champion = s.rank == 1 and s.losses == 0
        has_screenshot = data is not None and data.screenshot_url

        if is_champion and has_screenshot:
            # Champion gets its own TextDisplay so the full image is visually anchored to it.
            # Flush anything we've accumulated so far (e.g. a co-champion without a screenshot).
            if pending_lines:
                container.add_item(ui.TextDisplay("\n".join(pending_lines)))
                pending_lines = []
            container.add_item(ui.TextDisplay(row_text))
            container.add_item(ui.MediaGallery(
                discord.MediaGalleryItem(media=data.screenshot_url, description=f"{name}'s deck"),
            ))
        else:
            pending_lines.append(row_text)
            if has_screenshot:
                runners_up_items.append(
                    discord.MediaGalleryItem(media=data.screenshot_url, description=f"{name}'s deck"),
                )

    if pending_lines:
        container.add_item(ui.TextDisplay("\n".join(pending_lines)))
    if runners_up_items:
        container.add_item(ui.MediaGallery(*runners_up_items))

    view.add_item(container)

    actions = ui.ActionRow()
    if guild_id and thread_id:
        actions.add_item(ui.Button(
            label="Thread",
            style=discord.ButtonStyle.link,
            url=f"https://discord.com/channels/{guild_id}/{thread_id}",
            emoji=emojis.get_emoji("manat"),
        ))
    actions.add_item(ui.Button(
        label="Replays",
        style=discord.ButtonStyle.link,
        url=f"{settings.public_site_url.rstrip('/')}/pod/{slugify(event_name)}",
        emoji="🎬",
    ))
    view.add_item(actions)

    return view


def _round_header(round_num: int, complete: bool) -> str:
    if complete:
        return f"✅ Round {round_num} complete!"
    return f"⚔️ Round {round_num} Pairings ⚔️"


def _escape_italics(text: str) -> str:
    return text.replace("_", "\\_").replace("*", "\\*")


def build_champion_embed(
    standings: list[pod_swiss.Standing],
    *,
    event_name: str = "Pod Draft",
    displays: dict[str, dict] | None = None,
    player_colors: dict[str, str | None] | None = None,
    site_root: str | None = None,
    champion_locked: bool = True,
    pending_count: int = 0,
    deck_data: dict[str, "ParticipantDeckData"] | None = None,
) -> discord.Embed:
    """Thread-side standings embed. `player_colors` adds a mana-emoji glyph after each player's record.
    `deck_data` appends an inline Draft Log link per row when the participant has a MPT URL."""
    displays = displays or {}
    player_colors = player_colors or {}
    deck_data = deck_data or {}
    lines = [
        _build_standings_row(
            s, displays=displays, player_colors=player_colors,
            deck_data=deck_data, site_root=site_root,
            show_review_flag=True,
        )
        for s in standings
    ]

    title = f"🏆 {event_name}" if champion_locked else f"🟢 {event_name}"

    header = f"**{_standings_header_text(pending_count)}**"

    chordo_love = emojis.get("chordo_love")
    description = (
        f"{header}\n"
        + "\n".join(lines)
        + f"\n\n**🎨 Submit Deck** and share a screenshot below!\nThank you for playing! {chordo_love}"
    )

    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.green(),
    )


def _schedule_grace(manager, round_num: int) -> None:
    """(Re)start the grace timer for round_num. Cancels any pending grace on the same manager."""
    if manager.grace_task is not None and not manager.grace_task.done():
        manager.grace_task.cancel()
    manager.grace_round = round_num
    manager.grace_task = asyncio.create_task(_grace_expire(manager, round_num))


async def _grace_expire(manager, round_num: int) -> None:
    try:
        await asyncio.sleep(GRACE_SECONDS)
    except asyncio.CancelledError:
        return

    msg = manager.round_messages.get(round_num)
    if msg is not None:
        try:
            await msg.edit(view=None)
        except Exception:
            log.warning("could not lock round %d view", round_num, exc_info=True)

    if round_num >= TOTAL_ROUNDS and not manager.finalized:
        await finalize_tournament(manager)
        # Fallback: if nobody submitted deck colors during the window, post the announcement anyway
        if not manager.champion_announced:
            await _announce_or_update_champion(manager)

    manager.grace_round = None
    manager.grace_task = None


async def _regenerate_next_round(manager, next_round: int) -> None:
    """A previous-round edit landed during grace — re-pair `next_round` and edit its message in place.

    Deletes existing next_round rows, re-pairs via Swiss using updated prior results, posts an edited
    message + DMs any participant whose opponent changed.
    """
    event_id = manager.event_id
    prev_pairings = await asyncio.to_thread(_load_pairings_for_round, event_id, next_round)
    await asyncio.to_thread(_delete_round_rows, event_id, next_round)

    prior = await asyncio.to_thread(_load_matches, event_id)
    try:
        pairings = pod_swiss.pair_round(manager.tournament_players, prior, next_round)
    except ValueError as e:
        log.error("regenerate pairings for round %d failed for %s: %s", next_round, event_id, e)
        return

    pending_rows = await asyncio.to_thread(_insert_pending_matches, event_id, next_round, pairings)
    standings_by_id = {s.player_id: s for s in pod_swiss.compute_standings(manager.tournament_players, prior)}
    displays = await asyncio.to_thread(_load_participant_displays, event_id)
    match_states = [_state_for_pending(match_id, a, b, standings_by_id, displays) for match_id, a, b in pending_rows]
    _mark_trophy_match(match_states, next_round)
    embed = _round_embed(next_round, match_states)
    view = RoundResultsView(match_states)

    posted = manager.round_messages.get(next_round)
    if posted is not None:
        try:
            await posted.edit(embed=embed, view=view)
        except Exception:
            log.warning("could not edit round %d message during regenerate", next_round, exc_info=True)

    new_opponent_pairs = _changed_opponent_pairs(prev_pairings, pairings)
    if new_opponent_pairs and posted is not None:
        await _dm_changed_opponents(manager.bot, event_id, next_round, new_opponent_pairs, posted.jump_url)


def _load_pairings_for_round(event_id: str, round_num: int) -> list[tuple[str, str]]:
    with SessionLocal() as session:
        rows = session.execute(
            select(PodDraftMatch.player_a_name, PodDraftMatch.player_b_name)
            .where(PodDraftMatch.event_id == event_id, PodDraftMatch.round == round_num)
            .order_by(PodDraftMatch.pairing_index)
        ).all()
    return [(a, b) for a, b in rows]


def _delete_round_rows(event_id: str, round_num: int) -> None:
    with SessionLocal() as session:
        session.execute(
            delete(PodDraftMatch).where(PodDraftMatch.event_id == event_id, PodDraftMatch.round == round_num)
        )
        session.commit()


def _changed_opponent_pairs(
    prev: list[tuple[str, str]],
    new: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Return (player, new_opponent) tuples for every player whose opponent changed between prev and new."""
    def _by_player(pairs):
        out: dict[str, str] = {}
        for a, b in pairs:
            out[_normalize_player_name(a)] = b
            out[_normalize_player_name(b)] = a
        return out
    prev_map = _by_player(prev)
    new_map = _by_player(new)
    changed: list[tuple[str, str]] = []
    for player_key, new_opp in new_map.items():
        prev_opp = prev_map.get(player_key)
        if prev_opp is None or _normalize_player_name(prev_opp) != _normalize_player_name(new_opp):
            for a, b in new:
                if _normalize_player_name(a) == player_key:
                    changed.append((a, b))
                    break
                if _normalize_player_name(b) == player_key:
                    changed.append((b, a))
                    break
    return changed


async def _dm_changed_opponents(
    bot_client,
    event_id: str,
    round_num: int,
    changed: list[tuple[str, str]],
    pairings_url: str,
) -> None:
    dm_info = await asyncio.to_thread(_load_dm_info_sync, event_id)
    event_name = await asyncio.to_thread(_load_event_name_sync, event_id)
    seen: set[str] = set()
    for player_name, new_opp in changed:
        key = _normalize_player_name(player_name)
        if key in seen:
            continue
        seen.add(key)
        info = dm_info.get(key)
        if info is None or not info.discord_id:
            continue
        opp_info = dm_info.get(_normalize_player_name(new_opp))
        opp_label = (
            f"<@{opp_info.discord_id}>" if opp_info and opp_info.discord_id
            else f"**{opp_info.display_name if opp_info else new_opp}**"
        )
        opp_arena = opp_info.arena_name if opp_info else None
        embed = build_pairing_dm_embed(
            round_num=round_num,
            opponent_label=opp_label,
            opponent_arena=opp_arena,
            pairings_url=pairings_url,
            event_name=event_name,
            updated=True,
        )
        try:
            user = bot_client.get_user(int(info.discord_id)) or await bot_client.fetch_user(int(info.discord_id))
            await user.send(embed=embed)
        except discord.Forbidden:
            log.info("re-pair DM blocked for %s", info.discord_id)
        except discord.HTTPException:
            log.warning("re-pair DM failed", exc_info=True)


async def _resolve_announcement_target(manager):
    """Return the parent channel for the pod-draft thread; falls back to fetching by parent_id when
    the cache doesn't have it, then to the thread itself if no parent exists at all.
    """
    thread = await manager._fetch_thread()
    if thread is None:
        return None
    parent = getattr(thread, "parent", None)
    if parent is None:
        parent_id = getattr(thread, "parent_id", None)
        if parent_id:
            try:
                parent = await manager.bot.fetch_channel(parent_id)
            except Exception:
                log.warning("could not fetch parent for thread %s", thread.id, exc_info=True)
    return parent or thread


async def _announce_or_update_champion(manager) -> None:
    """Post the channel-level champion announcement when champion is locked AND the rank-1
    screenshot lands, OR when the grace window expires. Edits the announcement in place when
    later submissions (colors, more screenshots) come in.
    """
    event_id = manager.event_id
    match_states = await asyncio.to_thread(_load_round_states, event_id, TOTAL_ROUNDS)
    if not match_states:
        return
    _mark_trophy_match(match_states, TOTAL_ROUNDS)
    trophy = [m for m in match_states if m.get("is_trophy_match")]
    if not trophy or not all(m.get("winner_name") for m in trophy):
        return

    prior = await asyncio.to_thread(_load_matches, event_id)
    standings = pod_swiss.compute_standings(manager.tournament_players, prior)
    champions = [s for s in standings if s.losses == 0]
    if not champions:
        return

    displays = await asyncio.to_thread(_load_participant_displays, event_id)
    deck_data = await asyncio.to_thread(_load_event_deck_data_sync, event_id)
    player_colors = _colors_only(deck_data)
    champion_keys = [_normalize_player_name(c.player_name) for c in champions]
    dm_info = await asyncio.to_thread(_load_dm_info_sync, event_id)
    manager.champion_discord_ids = {
        info.discord_id for key, info in dm_info.items()
        if key in set(champion_keys) and info.discord_id
    }
    rank1_data = deck_data.get(_normalize_player_name(champions[0].player_name))
    rank1_screenshot_in = bool(rank1_data and rank1_data.screenshot_url)

    # First-time post waits for the rank-1 screenshot (the trigger), OR for the grace window to
    # expire. Colors are not gating — they edit the message in place after the announcement is up.
    grace_expired = manager.grace_task is None or manager.grace_task.done()
    if not manager.champion_announced and not rank1_screenshot_in and not grace_expired:
        return

    pending_count = sum(1 for m in match_states if not m.get("winner_name"))
    thread_id = int(manager.thread_id) if isinstance(manager.thread_id, (int, str)) else None
    target = await _resolve_announcement_target(manager) if manager.champion_announcement_message is None else None
    guild_id = (
        getattr(getattr(target, "guild", None), "id", None) if target is not None
        else getattr(getattr(manager.champion_announcement_message, "guild", None), "id", None)
    )

    view = build_champion_announcement_view(
        standings,
        event_name=await asyncio.to_thread(_load_event_name_sync, event_id),
        displays=displays,
        player_colors=player_colors,
        site_root=settings.public_site_url.rstrip("/"),
        pending_count=pending_count,
        deck_data=deck_data,
        event_started_at=await asyncio.to_thread(_load_event_started_at_sync, event_id),
        guild_id=guild_id,
        thread_id=thread_id,
    )

    existing = manager.champion_announcement_message
    if existing is None:
        if target is None:
            return
        try:
            manager.champion_announcement_message = await target.send(view=view)
            manager.champion_announced = True
        except Exception:
            log.warning("could not post champion announcement", exc_info=True)
        return

    try:
        await existing.edit(view=view)
    except Exception:
        log.warning("could not edit champion announcement", exc_info=True)


async def _post_or_update_live_standings(manager) -> None:
    """Post or edit the standings embed as R3 results land."""
    event_id = manager.event_id
    match_states = await asyncio.to_thread(_load_round_states, event_id, TOTAL_ROUNDS)
    if not match_states:
        return
    _mark_trophy_match(match_states, TOTAL_ROUNDS)
    if not any(m.get("winner_name") for m in match_states):
        return

    trophy = [m for m in match_states if m.get("is_trophy_match")]
    champion_locked = bool(trophy) and all(m.get("winner_name") for m in trophy)
    pending_count = sum(1 for m in match_states if not m.get("winner_name"))

    prior = await asyncio.to_thread(_load_matches, event_id)
    standings = pod_swiss.compute_standings(manager.tournament_players, prior)
    displays = await asyncio.to_thread(_load_participant_displays, event_id)
    event_name = await asyncio.to_thread(_load_event_name_sync, event_id)
    deck_data = await asyncio.to_thread(_load_event_deck_data_sync, event_id)
    player_colors = _colors_only(deck_data)
    embed = build_champion_embed(
        standings,
        event_name=event_name,
        displays=displays,
        player_colors=player_colors,
        site_root=settings.public_site_url.rstrip("/"),
        champion_locked=champion_locked,
        pending_count=pending_count,
        deck_data=deck_data,
    )

    if manager.standings_message is None:
        thread = await manager._fetch_thread()
        if thread is None:
            return
        try:
            manager.standings_message = await thread.send(
                embed=embed,
                view=build_live_submit_deck_view(),
            )
        except Exception:
            log.warning("could not post live standings", exc_info=True)
            return
        await _pin_only_this_bot_message(manager.standings_message)
    else:
        try:
            await manager.standings_message.edit(embed=embed)
        except Exception:
            log.warning("could not edit live standings", exc_info=True)

    if manager.champion_announced:
        await _announce_or_update_champion(manager)


async def _pin_only_this_bot_message(message: discord.Message) -> None:
    """Pin `message`, first unpinning any prior pins authored by the same bot in this channel.
    Keeps only one bot pin live so subsequent standings posts (or testlobby reruns) replace the
    prior one cleanly. Silent on Forbidden / HTTPException."""
    bot_user_id = message.author.id
    try:
        pins = await message.channel.pins()
    except discord.HTTPException:
        log.warning("could not fetch pins for %s", message.channel.id, exc_info=True)
        return
    for pin in pins:
        if pin.author.id == bot_user_id and pin.id != message.id:
            try:
                await pin.unpin(reason="rotating pod-draft standings pin")
            except discord.HTTPException:
                log.info("could not unpin %s", pin.id, exc_info=True)
    try:
        await message.pin(reason="latest pod-draft standings")
    except discord.HTTPException:
        log.warning("could not pin standings message %s", message.id, exc_info=True)


def _mark_trophy_match(match_states: list[dict], round_num: int) -> None:
    """Stamp is_trophy_match on every final-round pairing where at least one player can still go X-0.

    In 8-player pods that's exactly one match (2-0 vs 2-0). In 10-player pods with cross-bracket
    pairings it can be several (e.g. 2-0 vs 2-0 plus 2-0 vs 1-1).
    """
    if round_num != TOTAL_ROUNDS:
        return

    def _losses(record: str | None) -> int | None:
        if not record or "-" not in record:
            return None
        try:
            return int(record.split("-", 1)[1])
        except ValueError:
            return None

    for m in match_states:
        a_l = _losses(m.get("a_record"))
        b_l = _losses(m.get("b_record"))
        if a_l == 0 or b_l == 0:
            m["is_trophy_match"] = True


def _state_for_pending(match_id: str, a_name: str, b_name: str, standings_by_id,
                       displays: dict[str, dict] | None = None) -> dict:
    a_s = standings_by_id.get(a_name)
    b_s = standings_by_id.get(b_name)
    displays = displays or {}
    a_info = displays.get(_normalize_player_name(a_name), {})
    b_info = displays.get(_normalize_player_name(b_name), {})
    return {
        "match_id": match_id,
        "a_name": a_name,
        "b_name": b_name,
        "a_display": a_info.get("display_name") or a_name,
        "b_display": b_info.get("display_name") or b_name,
        "a_record": f"{a_s.wins}-{a_s.losses}" if a_s else "0-0",
        "b_record": f"{b_s.wins}-{b_s.losses}" if b_s else "0-0",
        "winner_name": None,
        "score": None,
    }


def _round_embed(round_num: int, match_states: list[dict]) -> discord.Embed:
    all_done = all(m["winner_name"] for m in match_states)
    title = _round_header(round_num, all_done)
    lines: list[str] = []
    for m in match_states:
        a_disp = m.get("a_display") or m["a_name"]
        b_disp = m.get("b_display") or m["b_name"]
        winner = m["winner_name"]
        if winner == SKIPPED_SENTINEL:
            lines.append(f"🚫 Not played: {a_disp} vs {b_disp}")
        elif winner:
            if winner.lower() == m["a_name"].lower():
                winner_disp, loser_disp = a_disp, b_disp
            else:
                winner_disp, loser_disp = b_disp, a_disp
            icon = "▫️"
            lines.append(f"{icon} {winner_disp} wins {m['score']} vs {loser_disp}")
        elif round_num > 1:
            lines.append(f"⚔️ {a_disp} ({m['a_record']})  vs  {b_disp} ({m['b_record']})")
        else:
            lines.append(f"⚔️ {a_disp}  vs  {b_disp}")
    return discord.Embed(
        title=title,
        description="\n".join(lines),
        color=discord.Color.green(),
    )


def _load_matches(event_id: str) -> list[MatchOutcome]:
    """Loads played matches only — skipped/no-match-played rows are excluded from standings."""
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
    out: list[tuple[str, str, str]] = []
    with SessionLocal() as session:
        for idx, (a_name, b_name) in enumerate(pairings):
            row = add_pairing(session, event_id, round_num, a_name, b_name, pairing_index=idx)
            out.append((row.id, a_name, b_name))
        session.commit()
    return out
