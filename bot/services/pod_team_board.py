"""Team-draft board: the match surface a team pod plays on, posted in the pod thread at endDraft.

Two-part surface: a classic embed heads it with both rosters side by side (V2 has no column
primitive) and the running Wins folded into a team's column header, then a Components V2 message
holds every cross-team match of all three rounds, each with its own report button. Pairings are a
fixed rotation, so every button is live from the start — rounds are the presented cadence, not a
gate. Buttons carry the result once reported: green for a Green Team win, blurple for Blue, with the
score as the label. Each report rebuilds the whole surface from committed match rows, so concurrent
edits self-heal. Buttons are DynamicItems (match id in the custom_id), so they keep dispatching
after a bot restart.

Discord caps a V2 message at 40 components and every match Section costs three, so 3v3 and 4v4 fit
one rounds message; a 5v5 paginates into whole-round pages, and every report re-renders all of them
together along with the summary embed.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import NamedTuple

import discord
from discord import ui
from sqlalchemy import select

from bot.database import SessionLocal
from bot.discord_helpers import NBSP, ZWSP
from bot.models import PodDraftEvent, PodDraftMatch, PodDraftParticipant
from bot.services import pod_team
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_drafts import load_event_name_sync, normalize_player_name
from bot.services.pod_tournament import (
    CLEAR_SENTINEL,
    SKIPPED_SENTINEL,
    actor_label,
    commit_result,
    deck_recovery_scan,
    format_match_result_log,
    format_reported_result,
    format_round_announcement,
    load_participant_displays,
    match_was_played,
    send_final_submit_deck_dms,
)


log = logging.getLogger(__name__)

REPORT_BUTTON_PREFIX = "podteamreport"


class TeamBoardMember(NamedTuple):
    display: str
    arena: str | None


class TeamBoardData(NamedTuple):
    event_id: str
    rosters: dict[str, list[TeamBoardMember]]
    wins: dict[str, int]
    rounds: list[tuple[int, list[dict]]]
    pending: int
    finalized: bool


def build_board_data(
    event_id: str,
    team_rows: list[tuple[str, str]],
    matches: list[dict],
    displays: dict[str, dict],
    finalized: bool,
) -> TeamBoardData:
    """Assemble the board model from raw rows. `team_rows` is (name, team) in seat order; `matches`
    carries match_id / round / a_name / b_name / winner_name / score in round + pairing order."""
    teams: dict[str, str] = {}
    rosters: dict[str, list[TeamBoardMember]] = {pod_team.TEAM_A: [], pod_team.TEAM_B: []}
    for name, team in team_rows:
        key = normalize_player_name(name)
        teams[key] = team
        info = displays.get(key, {})
        rosters[team].append(TeamBoardMember(
            display=info.get("display_name") or name,
            arena=info.get("arena"),
        ))

    for m in matches:
        a_info = displays.get(normalize_player_name(m["a_name"]), {})
        b_info = displays.get(normalize_player_name(m["b_name"]), {})
        m["a_display"] = a_info.get("display_name") or m["a_name"]
        m["b_display"] = b_info.get("display_name") or m["b_name"]
        if match_was_played(m):
            m["winner_team"] = teams.get(normalize_player_name(m["winner_name"]))
        else:
            m["winner_team"] = None

    reported = [
        (normalize_player_name(m["winner_name"]), m["score"]) for m in matches if match_was_played(m)
    ]
    a_wins, b_wins = pod_team.team_match_wins(reported, teams)
    round_nums = sorted({m["round"] for m in matches})
    rounds = [(r, [m for m in matches if m["round"] == r]) for r in round_nums]
    pending = sum(1 for m in matches if not m["winner_name"])
    return TeamBoardData(
        event_id=event_id,
        rosters=rosters,
        wins={pod_team.TEAM_A: a_wins, pod_team.TEAM_B: b_wins},
        rounds=rounds,
        pending=pending,
        finalized=finalized,
    )


def load_team_board_data(event_id: str) -> TeamBoardData:
    with SessionLocal() as session:
        team_rows = [
            (dm_name or display_name, team)
            for dm_name, display_name, team in session.execute(
                select(
                    PodDraftParticipant.draftmancer_name,
                    PodDraftParticipant.display_name,
                    PodDraftParticipant.team,
                )
                .where(PodDraftParticipant.event_id == event_id, PodDraftParticipant.team.is_not(None))
                .order_by(PodDraftParticipant.seat_index)
            ).all()
        ]
        matches = [
            {
                "match_id": row.id,
                "round": row.round,
                "a_name": row.player_a_name,
                "b_name": row.player_b_name,
                "winner_name": row.winner_name,
                "score": row.score,
            }
            for row in session.execute(
                select(PodDraftMatch)
                .where(PodDraftMatch.event_id == event_id)
                .order_by(PodDraftMatch.round, PodDraftMatch.pairing_index)
            ).scalars().all()
        ]
        finalized_at = session.execute(
            select(PodDraftEvent.finalized_at).where(PodDraftEvent.id == event_id)
        ).scalar_one_or_none()
    displays = load_participant_displays(event_id)
    return build_board_data(event_id, team_rows, matches, displays, finalized_at is not None)


MAX_VIEW_CHILDREN = 40
PAGE_BASE = 3     # container + the divider and progress-bar footer
ROUND_COST = 1    # round header
SECTION_COST = 3  # section + its text + accessory button

# Invisible run folded into every page's first match line: it holds the shrink-to-fit container
# open, pushing the report buttons to a fixed right edge, and gives every page the same width
# driver. The ZWSP anchor keeps Discord's trailing-whitespace trim off the NBSPs; tune to taste
BOARD_WIDTH_PAD = NBSP * 45 + ZWSP

PROGRESS_GAP = NBSP * 2
PROGRESS_PENDING = "🔳"
PROGRESS_SKIPPED = "⬜"


def plan_board_pages(rounds: list[tuple[int, list[dict]]]) -> list[list[tuple[int, list[dict]]]]:
    """Pack whole rounds into per-message pages under the 40-component cap; a round never splits
    across pages. A 3v3 is a single message; 4v4 and 5v5 split their final round off."""
    pages: list[list[tuple[int, list[dict]]]] = []
    current: list[tuple[int, list[dict]]] = []
    used = PAGE_BASE
    for round_num, matches in rounds:
        cost = ROUND_COST + SECTION_COST * len(matches)
        if current and used + cost > MAX_VIEW_CHILDREN:
            pages.append(current)
            current = []
            used = PAGE_BASE
        current.append((round_num, matches))
        used += cost
    pages.append(current)
    return pages


def build_team_board_views(data: TeamBoardData) -> list["TeamBoardView"]:
    pages = plan_board_pages(data.rounds)
    return [
        TeamBoardView(data, page, include_footer=index == len(pages) - 1)
        for index, page in enumerate(pages)
    ]


class TeamBoardView(ui.LayoutView):
    """One rounds message: each round's matches as Sections whose accessory button reports (and
    later recolors to) that match's result. The last page closes with a divider + the match progress
    bar and running score; every page folds the same invisible pad into its first match line, so all
    pages share one width driver. The rosters + Wins live in the summary embed above. Build via
    build_team_board_views, which splits the rounds across pages under the component cap."""

    def __init__(self, data: TeamBoardData, page_rounds: list[tuple[int, list[dict]]],
                 *, include_footer: bool = True) -> None:
        super().__init__(timeout=None)
        self.report_custom_ids: set[str] = set()
        container = ui.Container(accent_colour=discord.Color.green())
        for round_index, (round_num, matches) in enumerate(page_rounds):
            container.add_item(ui.TextDisplay(f"### Round {round_num}"))
            for match_index, m in enumerate(matches):
                text = match_line(m)
                if round_index == 0 and match_index == 0:
                    text = f"{text}{BOARD_WIDTH_PAD}"
                button = TeamReportButton.for_match(m, disabled=data.finalized)
                self.report_custom_ids.add(button.custom_id)
                container.add_item(ui.Section(text, accessory=button))
        if include_footer:
            container.add_item(ui.Separator())
            container.add_item(ui.TextDisplay(match_progress_bar(data)))
        self.add_item(container)


def match_progress_bar(data: TeamBoardData) -> str:
    """One square per match in board order, pipe-joined like the Set Awards hype meter — the winning
    team's emoji, pending and skipped squares otherwise — then the running score, leader first, and
    who leads (or won, once every match is in)."""
    icons = []
    for _, matches in data.rounds:
        for m in matches:
            icon = pod_team.TEAM_EMOJI.get(m.get("winner_team"))
            if icon is None:
                icon = PROGRESS_SKIPPED if m.get("winner_name") == SKIPPED_SENTINEL else PROGRESS_PENDING
            icons.append(icon)
    a_wins = data.wins.get(pod_team.TEAM_A, 0)
    b_wins = data.wins.get(pod_team.TEAM_B, 0)
    tail = f"{max(a_wins, b_wins)}-{min(a_wins, b_wins)}"
    status = _score_status(a_wins, b_wins, done=data.pending == 0)
    if status:
        tail = f"{tail}{PROGRESS_GAP}{status}"
    return f"{'|'.join(icons)}{PROGRESS_GAP}**{tail}**"


def _score_status(a_wins: int, b_wins: int, *, done: bool) -> str | None:
    if done:
        winner = pod_team.team_winner(a_wins, b_wins)
        return f"{pod_team.team_label(winner)} wins!" if winner else "Teams are tied"
    if a_wins == b_wins:
        return "Teams are tied" if a_wins else None
    leader = pod_team.TEAM_A if a_wins > b_wins else pod_team.TEAM_B
    return f"{pod_team.team_label(leader)} lead"


def team_summary_embed(data: TeamBoardData) -> discord.Embed:
    """The board's header message: both rosters side by side, posted once and never edited. A
    classic embed because V2 has no column primitive; the running score lives on the board's
    progress bar, not here."""
    embed = discord.Embed(color=discord.Color.green())
    add_team_roster_fields(embed, data.rosters)
    return embed


def add_team_roster_fields(embed: discord.Embed, rosters: dict[str, list[TeamBoardMember]]) -> None:
    """Both team columns (name + Arena handle) as two inline fields, shared by the board's summary
    header and the team-draft lobby card so the rosters render identically on both surfaces."""
    for team in (pod_team.TEAM_A, pod_team.TEAM_B):
        embed.add_field(
            name=f"{pod_team.team_emoji(team)} {pod_team.team_label(team)}",
            value=team_field_value(rosters.get(team, [])) or "—",
            inline=True,
        )


def team_field_value(members: list[TeamBoardMember]) -> str:
    """One team's roster column, the Arena handle beside each name, blockquoted so Discord draws the
    lobby embed's vertical bar. The ZWSP-anchored trailing run keeps the two team columns from
    sitting shoulder to shoulder. Shared with the reveal embed so the two surfaces can't drift."""
    column_gap = NBSP * 6 + ZWSP
    lines = [
        f"{member.display}  `{member.arena}`" if member.arena else member.display
        for member in members
    ]
    return "\n".join(f"> {line}{column_gap}" for line in lines)


def match_line(m: dict) -> str:
    """One match, Discord display names only — Arena handles live once in the summary embed above.
    A reported match leads with the winning team's emoji, matching the progress bar."""
    if match_was_played(m):
        marker = pod_team.TEAM_EMOJI.get(m.get("winner_team"), "▫️")
        return f"{marker} {format_reported_result(m)}"
    if m.get("winner_name") == SKIPPED_SENTINEL:
        return f"🚫 Not played: {m['a_display']} vs {m['b_display']}"
    return f"⚔️ {m['a_display']} vs {m['b_display']}"


class TeamReportButton(
    ui.DynamicItem[ui.Button], template=rf"{REPORT_BUTTON_PREFIX}:(?P<match_id>.+)",
):
    """A match's report button. Grey `Report` while pending; the score on green (Green Team won) or
    blurple (Blue Team won) once reported — the colour carries the result. Clicking opens the report
    modal, which overlays wherever the clicker is instead of dropping an ephemeral at the bottom of
    the chat."""

    def __init__(self, match_id: str, *, style: discord.ButtonStyle = discord.ButtonStyle.secondary,
                 label: str = "Report", disabled: bool = False) -> None:
        super().__init__(ui.Button(
            style=style, label=label, disabled=disabled,
            custom_id=f"{REPORT_BUTTON_PREFIX}:{match_id}",
        ))
        self.match_id = match_id

    @classmethod
    def for_match(cls, m: dict, *, disabled: bool) -> "TeamReportButton":
        if m.get("winner_team") == pod_team.TEAM_A:
            style, label = discord.ButtonStyle.success, m.get("score") or "won"
        elif m.get("winner_team") == pod_team.TEAM_B:
            style, label = discord.ButtonStyle.primary, m.get("score") or "won"
        elif m.get("winner_name") == SKIPPED_SENTINEL:
            style, label = discord.ButtonStyle.secondary, "Not played"
        else:
            style, label = discord.ButtonStyle.secondary, "Report"
        return cls(m["match_id"], style=style, label=label, disabled=disabled)

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: ui.Button, match: re.Match,
    ) -> "TeamReportButton":
        return cls(match["match_id"])

    async def callback(self, interaction: discord.Interaction) -> None:
        state = await asyncio.to_thread(load_match_report_state, self.match_id)
        if state is None:
            await interaction.response.send_message(
                "This match no longer exists.", ephemeral=(interaction.guild is not None),
            )
            return
        await interaction.response.send_modal(
            TeamReportModal(state, board_message=interaction.message),
        )


def load_match_report_state(match_id: str) -> dict | None:
    with SessionLocal() as session:
        row = session.get(PodDraftMatch, match_id)
        if row is None:
            return None
        state = {
            "match_id": row.id,
            "event_id": row.event_id,
            "round": row.round,
            "pairing_index": row.pairing_index,
            "a_name": row.player_a_name,
            "b_name": row.player_b_name,
            "winner_name": row.winner_name,
            "score": row.score,
        }
    displays = load_participant_displays(state["event_id"])
    a_info = displays.get(normalize_player_name(state["a_name"]), {})
    b_info = displays.get(normalize_player_name(state["b_name"]), {})
    state["a_display"] = a_info.get("display_name") or state["a_name"]
    state["b_display"] = b_info.get("display_name") or state["b_name"]
    return state


class TeamReportModal(ui.Modal):
    """Report modal behind a board button — an overlay, so it works no matter how far the chat has
    scrolled past the board. Option values encode `match_id|winner|score` with draftmancer names
    (DB keys), same shape as the Swiss round dropdowns."""

    def __init__(self, state: dict, board_message: discord.Message) -> None:
        super().__init__(title=f"Report Round {state['round']} Match {state['pairing_index'] + 1}"[:45])
        self.board_message = board_message
        match_id = state["match_id"]
        a_disp, b_disp = state["a_display"], state["b_display"]
        a_name, b_name = state["a_name"], state["b_name"]
        values = [
            (f"{a_disp} wins: 2-0", f"{match_id}|{a_name}|2-0"),
            (f"{a_disp} wins: 2-1", f"{match_id}|{a_name}|2-1"),
            (f"{b_disp} wins: 2-1", f"{match_id}|{b_name}|2-1"),
            (f"{b_disp} wins: 2-0", f"{match_id}|{b_name}|2-0"),
            ("No Match Played", f"{match_id}|{SKIPPED_SENTINEL}|0-0"),
        ]
        if state.get("winner_name"):
            values.insert(0, ("Clear Result", f"{match_id}|{CLEAR_SENTINEL}|0-0"))
        selected = None
        if state.get("winner_name") and state.get("score"):
            selected = f"{match_id}|{state['winner_name']}|{state['score']}"
        options = [
            discord.SelectOption(label=label[:100], value=value, default=value == selected)
            for label, value in values
        ]
        self.result = ui.Select(placeholder=f"{a_disp} vs {b_disp}"[:150], options=options,
                                min_values=1, max_values=1)
        self.add_item(ui.Label(text="Result", component=self.result))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await handle_team_report(interaction, self.result.values[0], self.board_message)


async def handle_team_report(
    interaction: discord.Interaction, value: str, board_message: discord.Message,
) -> None:
    """Commit a board report, then rebuild the board in place. The defer ack closes the report
    modal; the public result line is the confirmation. The last outstanding result also finalizes
    the tournament (records → pod points, winner announcement) under the manager's advance lock so
    two closing reports can't double-finalize."""
    try:
        match_id, winner_name, score = value.split("|", 2)
    except ValueError:
        await interaction.response.send_message("Malformed result option.", ephemeral=True)
        return
    try:
        await interaction.response.defer()
    except discord.HTTPException:
        log.warning("could not defer team report interaction", exc_info=True)

    result = await asyncio.to_thread(commit_result, match_id, winner_name, score)
    if result == "not_found":
        return
    event_id = result["event_id"]
    round_num = result["round"]
    event_name = await asyncio.to_thread(load_event_name_sync, event_id)
    if result.get("cleared"):
        log.info(
            f"[{event_name}] R{round_num} cleared {match_id} by {actor_label(interaction)} (team board)"
        )
    else:
        log.info(format_match_result_log(
            event_label=event_name, round_num=round_num, actor=actor_label(interaction),
            match_id=match_id, winner=winner_name, score=score, surface="team board",
        ))

    data = await asyncio.to_thread(load_team_board_data, event_id)
    newly_reported = not result.get("cleared") and (
        not result.get("was_reported") or result.get("winner_changed")
    )
    if newly_reported:
        match_state = _board_match(data, match_id)
        if match_state is not None and match_was_played(match_state):
            try:
                await board_message.channel.send(
                    format_round_announcement(round_num, match_state, board_message.jump_url),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                log.warning(f"[TEAM] result_announce_failed event={event_id}", exc_info=True)

    finished = [
        name for name in (result["a_name"], result["b_name"]) if _player_has_no_pending(data, name)
    ]
    if finished:
        asyncio.create_task(send_final_submit_deck_dms(interaction.client, event_id, finished))
        asyncio.create_task(deck_recovery_scan(interaction.client, event_id, finished))

    if await _maybe_finalize(event_id, data):
        data = await asyncio.to_thread(load_team_board_data, event_id)
    else:
        manager = ACTIVE_POD_MANAGERS.get(event_id)
        if manager is not None:
            from bot.services.pod_team_showcase import maybe_post_team_trophy_hype

            asyncio.create_task(maybe_post_team_trophy_hype(manager))
    await refresh_board_messages(event_id, data, board_message)


def _player_has_no_pending(data: TeamBoardData, name: str) -> bool:
    for _, matches in data.rounds:
        for m in matches:
            if not m["winner_name"] and name in (m["a_name"], m["b_name"]):
                return False
    return True


async def refresh_board_messages(
    event_id: str, data: TeamBoardData, clicked_message: discord.Message,
) -> None:
    """Re-render every rounds page; the summary embed is posted once and left alone. Pages come from
    the manager's tracked refs, or are rediscovered from the thread after a restart; the clicked
    page is always covered."""
    views = build_team_board_views(data)
    pages = await _resolve_board_messages(event_id, clicked_message, len(views))
    for view in views:
        target = _message_for_view(view, pages)
        if target is None:
            log.warning(f"[TEAM] board_page_missing event={event_id}")
            continue
        try:
            await target.edit(view=view)
        except discord.HTTPException:
            log.warning(f"[TEAM] board_edit_failed event={event_id} message={target.id}", exc_info=True)


def _message_for_view(view: TeamBoardView, messages: list[discord.Message]) -> discord.Message | None:
    for message in messages:
        if view.report_custom_ids & message_report_ids(message):
            return message
    return None


def message_report_ids(message: discord.Message) -> set[str]:
    """Report-button custom_ids in a message's component tree, walking containers, sections, and
    section accessories."""
    found: set[str] = set()

    def walk(components) -> None:
        for component in components:
            custom_id = getattr(component, "custom_id", None)
            if custom_id and custom_id.startswith(f"{REPORT_BUTTON_PREFIX}:"):
                found.add(custom_id)
            walk(getattr(component, "children", None) or [])
            accessory = getattr(component, "accessory", None)
            if accessory is not None:
                walk([accessory])

    walk(message.components)
    return found


BOARD_HISTORY_SCAN_LIMIT = 200


async def _resolve_board_messages(
    event_id: str, clicked_message: discord.Message, expected_pages: int,
) -> list[discord.Message]:
    manager = ACTIVE_POD_MANAGERS.get(event_id)
    if manager is not None and len(manager.team_board_messages) >= expected_pages:
        return list(manager.team_board_messages)
    pages = await _find_board_messages(clicked_message, expected_pages)
    if manager is not None and len(pages) >= expected_pages:
        manager.team_board_messages = list(pages)
    return pages


async def _find_board_messages(
    clicked_message: discord.Message, expected_pages: int,
) -> list[discord.Message]:
    """Rediscover the rounds pages after a restart: the pinned first page, then a bounded history
    scan for the rest. Rounds pages are the only messages carrying report-button custom_ids, so the
    filter can't catch other bot messages."""
    pages: dict[int, discord.Message] = {clicked_message.id: clicked_message}
    try:
        for message in await clicked_message.channel.pins():
            if message_report_ids(message):
                pages[message.id] = message
    except (discord.HTTPException, AttributeError):
        log.warning("could not fetch pins to rediscover the team board", exc_info=True)
    if len(pages) < expected_pages:
        try:
            async for message in clicked_message.channel.history(limit=BOARD_HISTORY_SCAN_LIMIT):
                if message_report_ids(message):
                    pages[message.id] = message
                if len(pages) >= expected_pages:
                    break
        except (discord.HTTPException, AttributeError):
            log.warning("could not scan history to rediscover the team board", exc_info=True)
    return sorted(pages.values(), key=lambda m: m.id)


def _board_match(data: TeamBoardData, match_id: str) -> dict | None:
    for _, matches in data.rounds:
        for m in matches:
            if m["match_id"] == match_id:
                return m
    return None


async def _maybe_finalize(event_id: str, data: TeamBoardData) -> bool:
    if data.pending > 0 or data.finalized:
        return False
    manager = ACTIVE_POD_MANAGERS.get(event_id)
    if manager is None:
        log.warning(f"[TEAM] finalize.no_manager event={event_id}")
        return False
    from bot.services import pod_team_flow

    async with manager._advance_lock:
        await pod_team_flow.finalize_team_tournament(manager)
    return True
