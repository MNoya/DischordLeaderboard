"""/pod-backfill — reconstruct a pod-draft event from its Discord thread.

Pipeline: scrape the thread → infer structure (seats, records, decks, matches via 17lands
mirror-join) → gaps-first confirmation wizard → idempotent writes in one transaction →
post-process (DraftLog ingest, MagicProTools, replay backfill, optional announcement).
See spec/pod-backfill-handoff.md.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from bot.commands import descriptions as desc
from bot.commands.messages import MSG_ADMIN_ONLY
from bot.database import SessionLocal
from bot.discord_helpers import first_image_url
from bot.models import Player, PodDraftEvent, PodDraftMatch, PodDraftParticipant
from bot.services.pod_backfill import COLORS_RE, apply_seat, normalize_colors, strip_cdn_dims
from bot.services.pod_drafts import (
    FinalStanding,
    ParsedSeshEvent,
    finalize_champion,
    load_event_id_by_name_sync,
    load_event_id_by_thread_sync,
    normalize_player_name,
    player_for_name,
    record_event,
    record_match,
    search_event_names_sync,
    upsert_participant,
)
from bot.services.pod_log_ingest import ingest_draft_log_sync, log_user_names, submit_log_to_mpt
from bot.services.pod_replays import persist_replays_sync
from bot.services.pod_thread_backfill import (
    PLACEHOLDER_SCORE,
    DeckPost,
    MatchDraft,
    ScrapedMessage,
    compute_placements,
    extract_deck_posts,
    extract_draft_log_attachment,
    fill_reported_ats,
    games_from_17lands,
    infer_matches,
    merge_matches,
)
from bot.services.pod_tournament import TOTAL_ROUNDS, post_championship_for_event
from bot.services.sesh_parser import parse_sesh_embed, unescape_markdown
from bot.services.seventeenlands import SeventeenLandsClient
from bot.sets import ACTIVE_SET_CODE
from bot.tasks.pod_draft_reminder import fetch_sesh_message, fetch_sesh_rsvps


log = logging.getLogger(__name__)

MSG_NOT_POD_THREAD = "Run this inside a pod-draft thread, or pass an `event` to backfill a specific pod."
MSG_SESH_UNREADABLE = (
    "No event is registered for this thread, and it couldn't be reconstructed — "
    "the sesh post is missing or has no readable Time/Attendees embed."
)

SCORE_RE = re.compile(r"^[0-3]-[0-3]$")
ARENA_SUFFIX_RE = re.compile(r"#\d+$")
DELETE_SENTINEL = "-"
VIEW_TIMEOUT_S = 30 * 60
REPLAY_HORIZON = timedelta(days=7)


@dataclass
class SeatDraft:
    name: str
    player_id: str | None = None
    player_display: str | None = None
    discord_id: str | None = None
    token: str | None = None
    record: str | None = None
    colors: str | None = None
    caption: str | None = None
    screenshot_url: str | None = None


@dataclass
class Workspace:
    event_id: str
    event_name: str
    event_time: datetime
    thread_id: str
    pairing_mode: str
    socket_status: str
    already_announced: bool
    seats: list[SeatDraft]
    matches: list[MatchDraft]
    draft_log: dict | None = None
    draft_log_filename: str | None = None
    unassigned_decks: list[DeckPost] = field(default_factory=list)
    raw_games: dict[str, list[dict]] = field(default_factory=dict)
    announce: bool = False
    replays_skipped: bool = False

    def seat_named(self, name: str) -> SeatDraft | None:
        norm = normalize_player_name(name)
        for seat in self.seats:
            if normalize_player_name(seat.name) == norm:
                return seat
        return None

    def resolve_seat_name(self, raw: str) -> str | None:
        """Canonical seat name for an admin-typed name: exact normalized match, then unique prefix."""
        exact = self.seat_named(raw)
        if exact is not None:
            return exact.name
        norm = normalize_player_name(raw)
        if not norm:
            return None
        prefixed = [s for s in self.seats if normalize_player_name(s.name).startswith(norm)]
        if len(prefixed) == 1:
            return prefixed[0].name
        return None


class PodBackfill(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="pod-backfill", description=desc.POD_BACKFILL)
    @app_commands.describe(event="Pod-draft event to backfill; defaults to the current thread")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_backfill(self, interaction: discord.Interaction, event: str | None = None) -> None:
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(MSG_ADMIN_ONLY, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        if event:
            event_id = await asyncio.to_thread(load_event_id_by_name_sync, event)
            if event_id is None:
                await interaction.followup.send(f"No pod-draft event named `{event}`.", ephemeral=True)
                return
        else:
            thread_id = str(interaction.channel_id) if interaction.channel_id else None
            if thread_id is None:
                await interaction.followup.send(MSG_NOT_POD_THREAD, ephemeral=True)
                return
            event_id = await asyncio.to_thread(load_event_id_by_thread_sync, thread_id)
            if event_id is None:
                event_id = await reconstruct_event_from_thread(self.bot, thread_id)
                if event_id is None:
                    await interaction.followup.send(MSG_SESH_UNREADABLE, ephemeral=True)
                    return
                log.info(f"pod-backfill: reconstructed pre-bot event {event_id} from thread {thread_id}")

        log.info(f"pod-backfill: {interaction.user} started for event_id={event_id}")
        try:
            ws = await assemble_workspace(self.bot, event_id)
        except Exception:
            log.warning(f"pod-backfill: assembly failed for event_id={event_id}", exc_info=True)
            await interaction.followup.send("Couldn't assemble the event from its thread — check the logs.",
                                            ephemeral=True)
            return

        view = BackfillView(self.bot, ws, invoker_id=interaction.user.id)
        message = await interaction.followup.send(embed=build_workspace_embed(ws), view=view, wait=True)
        view.message = message

    @pod_backfill.autocomplete("event")
    async def _pod_backfill_event_autocomplete(
        self, interaction: discord.Interaction, current: str,
    ) -> list[app_commands.Choice[str]]:
        names = await asyncio.to_thread(search_event_names_sync, current)
        return [app_commands.Choice(name=n, value=n) for n in names]


async def reconstruct_event_from_thread(bot: commands.Bot, thread_id: str) -> str | None:
    """Register a pod event for a thread that predates the bot. Sesh spawns the thread from its RSVP
    message, so the thread id doubles as the sesh message id — fetch it, parse the embed, and record
    the event with its original date, attendees and set code."""
    message = await fetch_sesh_message(bot, thread_id)
    if message is None:
        return None
    fields = None
    for embed in message.embeds:
        fields = parse_sesh_embed(embed)
        if fields is not None:
            break
    if fields is None:
        return None
    parsed = ParsedSeshEvent(
        event_date=fields.event_date,
        event_time=fields.event_time,
        set_code=fields.set_code or ACTIVE_SET_CODE,
        event_number=fields.event_number,
        name=fields.name,
        attendees=fields.attendees,
        sesh_message_id=thread_id,
        discord_thread_id=thread_id,
    )
    return await asyncio.to_thread(_record_event_sync, parsed)


def _record_event_sync(parsed: ParsedSeshEvent) -> str:
    with SessionLocal() as session:
        event = record_event(session, parsed)
        session.commit()
        return event.id


async def assemble_workspace(bot: commands.Bot, event_id: str) -> Workspace:
    info = await asyncio.to_thread(_load_event_info_sync, event_id)
    thread = bot.get_channel(int(info["thread_id"])) or await bot.fetch_channel(int(info["thread_id"]))
    scraped, txt_attachments = await _scrape_thread(thread)
    deck_posts = extract_deck_posts(scraped)

    draft_log = None
    draft_log_filename = None
    log_attachment = extract_draft_log_attachment(scraped)
    if log_attachment is not None:
        draft_log_filename, url = log_attachment
        attachment = txt_attachments.get(url)
        if attachment is not None:
            try:
                draft_log = json.loads(await attachment.read())
            except (discord.HTTPException, ValueError):
                log.warning(f"pod-backfill: could not read DraftLog {draft_log_filename!r}", exc_info=True)
                draft_log_filename = None

    rsvps = await fetch_sesh_rsvps(bot, info["sesh_message_id"]) if info["sesh_message_id"] else None
    yes_names = rsvps[0] if rsvps else []
    roster = log_user_names(draft_log) if draft_log else None

    ws = await asyncio.to_thread(_assemble_sync, info, deck_posts, roster, yes_names)
    ws.draft_log = draft_log
    ws.draft_log_filename = draft_log_filename

    ws.replays_skipped = datetime.now(timezone.utc) - ws.event_time > REPLAY_HORIZON
    client = SeventeenLandsClient()
    games_by_seat = {}
    for seat in ws.seats:
        if ws.replays_skipped or not seat.token:
            continue
        raw = await asyncio.to_thread(client.fetch_user_games, seat.token)
        ws.raw_games[seat.name] = raw
        games_by_seat[seat.name] = games_from_17lands(raw, ws.event_time)

    inferred = infer_matches(games_by_seat)
    ws.matches = merge_matches(ws.matches, inferred)
    if not ws.replays_skipped:
        ws.matches = fill_reported_ats(ws.matches, ws.event_time)
    return ws


def _load_event_info_sync(event_id: str) -> dict:
    with SessionLocal() as session:
        event = session.get(PodDraftEvent, event_id)
        if event is None:
            raise ValueError(f"pod_draft_event {event_id} not found")
        return {
            "event_id": event.id,
            "name": event.name,
            "event_time": event.event_time,
            "thread_id": event.discord_thread_id,
            "sesh_message_id": event.sesh_message_id,
            "pairing_mode": event.pairing_mode,
            "socket_status": event.socket_status,
            "championship_posted_at": event.championship_posted_at,
        }


async def _scrape_thread(thread) -> tuple[list[ScrapedMessage], dict[str, discord.Attachment]]:
    scraped: list[ScrapedMessage] = []
    txt_attachments: dict[str, discord.Attachment] = {}
    async for message in thread.history(limit=None, oldest_first=True):
        txts = []
        for attachment in message.attachments:
            if attachment.filename.lower().endswith(".txt"):
                txts.append((attachment.filename, attachment.url))
                txt_attachments[attachment.url] = attachment
        scraped.append(ScrapedMessage(
            author_id=str(message.author.id),
            author_display=message.author.display_name,
            author_is_bot=message.author.bot,
            content=message.content or "",
            image_url=first_image_url(message),
            txt_attachments=tuple(txts),
            created_at=message.created_at,
        ))
    return scraped, txt_attachments


def _assemble_sync(
    info: dict,
    deck_posts: dict[str, DeckPost],
    roster: list[str] | None,
    yes_names: list[str],
) -> Workspace:
    with SessionLocal() as session:
        participants = session.execute(
            select(PodDraftParticipant).where(PodDraftParticipant.event_id == info["event_id"])
        ).scalars().all()

        ws = Workspace(
            event_id=info["event_id"],
            event_name=info["name"],
            event_time=info["event_time"],
            thread_id=info["thread_id"],
            pairing_mode=info["pairing_mode"],
            socket_status=info["socket_status"],
            already_announced=info["championship_posted_at"] is not None,
            seats=[],
            matches=[],
        )

        for name in roster or []:
            ws.seats.append(SeatDraft(name=name))

        for p in participants:
            seat = ws.seat_named(p.draftmancer_name or p.display_name) or ws.seat_named(p.display_name)
            if seat is None:
                if roster is not None and p.placement is None and p.record is None:
                    continue
                seat = SeatDraft(name=unescape_markdown(p.draftmancer_name or p.display_name))
                ws.seats.append(seat)
            seat.player_id = p.player_id
            seat.record = p.record
            seat.colors = p.deck_colors
            seat.caption = p.deck_screenshot_caption
            seat.screenshot_url = p.deck_screenshot_url

        if not ws.seats:
            for name in yes_names:
                ws.seats.append(SeatDraft(name=name))

        for seat in ws.seats:
            player = session.get(Player, seat.player_id) if seat.player_id else None
            if player is None:
                player = player_for_name(session, seat.name)
            if player is not None:
                seat.player_id = player.id
                seat.player_display = player.display_name
                seat.discord_id = player.discord_id
                seat.token = player.seventeenlands_token

        seats_by_discord = {s.discord_id: s for s in ws.seats if s.discord_id}
        for post in deck_posts.values():
            seat = seats_by_discord.get(post.author_id) or ws.seat_named(post.author_display)
            if seat is None:
                player = session.execute(
                    select(Player).where(Player.discord_id == post.author_id)
                ).scalar_one_or_none()
                if player is not None and roster is None:
                    seat = SeatDraft(
                        name=player.display_name, player_id=player.id, player_display=player.display_name,
                        discord_id=player.discord_id, token=player.seventeenlands_token,
                    )
                    ws.seats.append(seat)
            if seat is None:
                ws.unassigned_decks.append(post)
                continue
            seat.screenshot_url = strip_cdn_dims(post.image_url)
            seat.caption = post.caption
            if post.record:
                seat.record = post.record
            if post.colors and not seat.colors:
                seat.colors = post.colors

        db_matches = session.execute(
            select(PodDraftMatch).where(PodDraftMatch.event_id == info["event_id"])
        ).scalars().all()
        ws.matches = [
            MatchDraft(
                round=m.round, player_a=m.player_a_name, player_b=m.player_b_name,
                winner=m.winner_name, score=m.score, reported_at=m.reported_at, source="db",
            )
            for m in db_matches
        ]
        return ws


def build_workspace_embed(ws: Workspace) -> discord.Embed:
    if ws.replays_skipped:
        seventeenlands_status = "skipped (event past the replay horizon)"
    else:
        seventeenlands_status = f"{len(ws.raw_games)}/{len(ws.seats)} seats"
    header = [
        f"**{ws.event_time:%Y-%m-%d}** · {ws.pairing_mode} · status `{ws.socket_status}`",
        f"DraftLog: {f'✅ `{ws.draft_log_filename}`' if ws.draft_log else '—'}"
        f" · 17lands: {seventeenlands_status}",
        f"Announce: {'📣 post championship on confirm' if ws.announce else '🤫 quiet (no announcement)'}",
    ]
    if ws.already_announced:
        header.append("Championship was already announced for this event.")
    embed = discord.Embed(
        title=f"Pod Backfill — {ws.event_name}",
        description="\n".join(header),
        color=discord.Color.gold(),
    )

    seat_lines = []
    for s in ws.seats:
        link = "🪪" if s.player_id else "❔"
        shot = "📷" if s.screenshot_url else "·"
        seat_lines.append(f"{link} `{short_name(s.name)}`  {s.record or '?-?'}  {s.colors or '—'}  {shot}")
    embed.add_field(name=f"Players ({len(ws.seats)})", value="\n".join(seat_lines) or "—", inline=False)

    for round_num in range(1, TOTAL_ROUNDS + 1):
        lines = []
        for m in [m for m in ws.matches if m.round == round_num]:
            if m.winner:
                outcome = f"{m.score or PLACEHOLDER_SCORE + '?'} → **{short_name(m.winner)}**"
            else:
                outcome = "❓ winner unknown"
            lines.append(f"`{short_name(m.player_a)}` vs `{short_name(m.player_b)}` — {outcome} ({m.source})")
        embed.add_field(name=f"Round {round_num}", value="\n".join(lines) or "❓ no matches", inline=False)

    standings = compute_placements([s.name for s in ws.seats], ws.matches, seat_records(ws))
    if standings:
        placement_lines = [
            f"{st.rank}. `{short_name(st.player_name)}` ({st.wins}-{st.losses})" for st in standings
        ]
        embed.add_field(name="Computed placements", value="\n".join(placement_lines), inline=False)

    gaps = compute_gaps(ws)
    embed.add_field(
        name=f"Gaps ({len(gaps)})",
        value="\n".join(f"⚠️ {g}" for g in gaps[:15]) + ("\n…" if len(gaps) > 15 else "") if gaps else "✅ none",
        inline=False,
    )
    return embed


def compute_gaps(ws: Workspace) -> list[str]:
    gaps: list[str] = []
    if len(ws.seats) % 2:
        gaps.append(f"odd player count ({len(ws.seats)})")
    expected = len(ws.seats) // 2

    for s in ws.seats:
        missing = [label for label, value in (
            ("record", s.record), ("colors", s.colors), ("screenshot", s.screenshot_url),
        ) if not value]
        if missing:
            gaps.append(f"`{s.name}` missing {', '.join(missing)}")
        if s.player_id is None:
            gaps.append(f"`{s.name}` not linked to a player")

    for round_num in range(1, TOTAL_ROUNDS + 1):
        in_round = [m for m in ws.matches if m.round == round_num]
        if len(in_round) < expected:
            gaps.append(f"round {round_num}: {len(in_round)}/{expected} matches known")
        for m in in_round:
            if not m.winner:
                gaps.append(f"R{round_num} `{m.player_a}` vs `{m.player_b}`: winner unknown")
            elif not m.score:
                gaps.append(f"R{round_num} `{m.player_a}` vs `{m.player_b}`: score unknown "
                            f"(will write {PLACEHOLDER_SCORE})")

    caption_records = {normalize_player_name(s.name): s.record for s in ws.seats if s.record}
    for st in compute_placements([s.name for s in ws.seats], ws.matches, seat_records(ws)):
        caption_record = caption_records.get(normalize_player_name(st.player_name))
        computed = f"{st.wins}-{st.losses}"
        if caption_record and caption_record != computed and (st.wins or st.losses):
            gaps.append(f"`{st.player_name}` caption record {caption_record} ≠ computed {computed}")

    for post in ws.unassigned_decks:
        gaps.append(f"deck post by `{post.author_display}` not matched to a player")
    return gaps


def seat_records(ws: Workspace) -> dict[str, str | None]:
    return {s.name: s.record for s in ws.seats}


def short_name(name: str) -> str:
    """Drop the trailing #NNNN arena suffix for display; canonical seat names keep it."""
    return ARENA_SUFFIX_RE.sub("", name)


def blocking_gaps(ws: Workspace) -> list[str]:
    blockers = [f"R{m.round} `{m.player_a}` vs `{m.player_b}`: winner unknown"
                for m in ws.matches if not m.winner]
    if not ws.matches and not any(s.record for s in ws.seats):
        blockers.append("no matches and no player records — nothing to score")
    return blockers


class BackfillView(discord.ui.View):
    def __init__(self, bot: commands.Bot, ws: Workspace, *, invoker_id: int) -> None:
        super().__init__(timeout=VIEW_TIMEOUT_S)
        self.bot = bot
        self.ws = ws
        self.invoker_id = invoker_id
        self.message: discord.Message | None = None
        self._build_items()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.invoker_id

    def _build_items(self) -> None:
        self.clear_items()

        seat_select = discord.ui.Select(
            placeholder="Edit a player…",
            options=[
                discord.SelectOption(
                    label=short_name(s.name)[:100], value=s.name[:100],
                    description=f"{s.record or '?-?'} {s.colors or ''}".strip()[:100] or None,
                )
                for s in self.ws.seats[:25]
            ] or [discord.SelectOption(label="(no players)", value="none")],
            row=0,
        )
        seat_select.callback = self._on_seat_select
        self.add_item(seat_select)

        match_options = [discord.SelectOption(label="➕ Add match", value="add")]
        for i, m in enumerate(self.ws.matches[:24]):
            outcome = f"{m.score or '?'} → {short_name(m.winner)}" if m.winner else "winner unknown"
            match_options.append(discord.SelectOption(
                label=f"R{m.round}: {short_name(m.player_a)} vs {short_name(m.player_b)}"[:100],
                value=str(i),
                description=outcome[:100],
            ))
        match_select = discord.ui.Select(placeholder="Edit a match…", options=match_options, row=1)
        match_select.callback = self._on_match_select
        self.add_item(match_select)

        announce = discord.ui.Button(
            label="Announce: on 📣" if self.ws.announce else "Announce: off 🤫",
            style=discord.ButtonStyle.secondary, row=2,
        )
        announce.callback = self._on_announce_toggle
        self.add_item(announce)

        confirm = discord.ui.Button(label="Confirm & write", style=discord.ButtonStyle.success, row=2)
        confirm.callback = self._on_confirm
        self.add_item(confirm)

        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, row=2)
        cancel.callback = self._on_cancel
        self.add_item(cancel)

    async def refresh(self, interaction: discord.Interaction) -> None:
        self._build_items()
        embed = build_workspace_embed(self.ws)
        if interaction.response.is_done():
            if self.message is not None:
                await self.message.edit(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def _on_seat_select(self, interaction: discord.Interaction) -> None:
        seat = self.ws.seat_named(interaction.data["values"][0])
        if seat is None:
            await interaction.response.defer()
            return
        await interaction.response.send_modal(SeatModal(self, seat))

    async def _on_match_select(self, interaction: discord.Interaction) -> None:
        value = interaction.data["values"][0]
        match = None if value == "add" else self.ws.matches[int(value)]
        await interaction.response.send_modal(MatchModal(self, match))

    async def _on_announce_toggle(self, interaction: discord.Interaction) -> None:
        self.ws.announce = not self.ws.announce
        await self.refresh(interaction)

    async def _on_cancel(self, interaction: discord.Interaction) -> None:
        self.stop()
        await interaction.response.edit_message(content="Backfill cancelled — nothing written.",
                                                embed=None, view=None)

    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        blockers = blocking_gaps(self.ws)
        if blockers:
            lines = "\n".join(f"⚠️ {b}" for b in blockers[:10])
            await interaction.response.send_message(
                f"Can't write yet — fill these first:\n{lines}", ephemeral=True,
            )
            return

        self.stop()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        summary = await run_backfill(self.bot, self.ws)
        log.info(f"pod-backfill: {interaction.user} wrote event_id={self.ws.event_id}")
        await interaction.followup.send(embed=summary, ephemeral=True)


class SeatModal(discord.ui.Modal):
    def __init__(self, view: BackfillView, seat: SeatDraft) -> None:
        super().__init__(title=f"Player — {seat.name}"[:45])
        self.view = view
        self.seat = seat
        self.record_input = discord.ui.TextInput(
            label=f"Record (W-L, or `{DELETE_SENTINEL}` to remove the player)",
            required=False, default=seat.record or "", max_length=5,
        )
        self.colors_input = discord.ui.TextInput(
            label="Colors (WUBRG order, lowercase = splash)", required=False,
            default=seat.colors or "", max_length=5,
        )
        self.screenshot_input = discord.ui.TextInput(
            label="Screenshot URL", required=False, default=seat.screenshot_url or "",
            style=discord.TextStyle.long, max_length=1024,
        )
        self.caption_input = discord.ui.TextInput(
            label="Caption", required=False, default=seat.caption or "",
            style=discord.TextStyle.long, max_length=512,
        )
        for item in (self.record_input, self.colors_input, self.screenshot_input, self.caption_input):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if self.record_input.value.strip() == DELETE_SENTINEL:
            self.view.ws.seats = [s for s in self.view.ws.seats if s is not self.seat]
            await self.view.refresh(interaction)
            return

        errors = []
        record = self.record_input.value.strip()
        if record and not SCORE_RE.match(record):
            errors.append(f"invalid record `{record}` (expected `W-L`)")
        colors = self.colors_input.value.strip()
        if colors and not COLORS_RE.match(colors):
            errors.append(f"invalid colors `{colors}` (expected 1-5 of W/U/B/R/G)")
        if errors:
            await interaction.response.send_message("\n".join(f"⚠️ {e}" for e in errors), ephemeral=True)
            return

        self.seat.record = record or None
        self.seat.colors = normalize_colors(colors) if colors else None
        screenshot = self.screenshot_input.value.strip()
        self.seat.screenshot_url = strip_cdn_dims(screenshot) if screenshot else None
        self.seat.caption = self.caption_input.value.strip() or None
        await self.view.refresh(interaction)


class MatchModal(discord.ui.Modal):
    def __init__(self, view: BackfillView, match: MatchDraft | None) -> None:
        super().__init__(title="Edit match" if match else "Add match")
        self.view = view
        self.match = match
        prior = match or MatchDraft(round=0, player_a="", player_b="", winner=None, score=None,
                                    reported_at=None, source="manual")
        self.round_input = discord.ui.TextInput(
            label=f"Round (1-{TOTAL_ROUNDS})", default=str(prior.round) if match else "", max_length=1,
        )
        self.player_a_input = discord.ui.TextInput(
            label="Player A", default=prior.player_a, max_length=100,
        )
        self.player_b_input = discord.ui.TextInput(
            label="Player B", default=prior.player_b, max_length=100,
        )
        self.winner_input = discord.ui.TextInput(
            label=f"Winner (name, or `{DELETE_SENTINEL}` to delete)",
            default=prior.winner or "", required=False, max_length=100,
        )
        self.score_input = discord.ui.TextInput(
            label=f"Score (blank = {PLACEHOLDER_SCORE})",
            default=prior.score or "", required=False, max_length=5,
        )
        for item in (self.round_input, self.player_a_input, self.player_b_input,
                     self.winner_input, self.score_input):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        ws = self.view.ws
        if self.winner_input.value.strip() == DELETE_SENTINEL and self.match is not None:
            ws.matches = [m for m in ws.matches if m is not self.match]
            await self.view.refresh(interaction)
            return

        errors = []
        round_raw = self.round_input.value.strip()
        round_num = int(round_raw) if round_raw.isdigit() else 0
        if not 1 <= round_num <= TOTAL_ROUNDS:
            errors.append(f"round must be 1-{TOTAL_ROUNDS}")
        player_a = ws.resolve_seat_name(self.player_a_input.value.strip())
        player_b = ws.resolve_seat_name(self.player_b_input.value.strip())
        if player_a is None:
            errors.append(f"`{self.player_a_input.value.strip()}` doesn't match a player")
        if player_b is None:
            errors.append(f"`{self.player_b_input.value.strip()}` doesn't match a player")
        winner = None
        winner_raw = self.winner_input.value.strip()
        if winner_raw:
            winner = ws.resolve_seat_name(winner_raw)
            if winner not in (player_a, player_b):
                errors.append(f"winner `{winner_raw}` must be one of the two players")
        score = self.score_input.value.strip() or None
        if score and not SCORE_RE.match(score):
            errors.append(f"invalid score `{score}` (expected `N-N`)")
        if errors:
            await interaction.response.send_message("\n".join(f"⚠️ {e}" for e in errors), ephemeral=True)
            return

        edited = MatchDraft(
            round=round_num, player_a=player_a, player_b=player_b,
            winner=winner, score=score, reported_at=None, source="manual",
        )
        if self.match is not None:
            ws.matches = [edited if m is self.match else m for m in ws.matches]
        else:
            ws.matches = [*ws.matches, edited]
        if not ws.replays_skipped:
            ws.matches = fill_reported_ats(ws.matches, ws.event_time)
        await self.view.refresh(interaction)


async def run_backfill(bot: commands.Bot, ws: Workspace) -> discord.Embed:
    lines = await asyncio.to_thread(_apply_workspace_sync, ws)

    if ws.draft_log is not None:
        ingest = await asyncio.to_thread(ingest_draft_log_sync, ws.event_id, ws.draft_log)
        if ingest is None or not ingest.applied:
            unmatched = ", ".join(ingest.unmatched) if ingest else "event missing"
            lines.append(f"⚠️ DraftLog ingest skipped — unmatched: {unmatched}")
        else:
            lines.append(f"DraftLog ingested: {ingest.seats} seats, {ingest.renamed} renamed, "
                         f"{ingest.stored_bytes:,} bytes")
            mpt = await submit_log_to_mpt(ws.event_id, ws.draft_log)
            if mpt is not None:
                lines.append(f"MagicProTools: {mpt.submitted} submitted, {mpt.failed} failed")

    if ws.replays_skipped:
        lines.append("Replays: skipped — event is past the 17lands history horizon")
    else:
        replay_rows = 0
        for seat in ws.seats:
            raw = ws.raw_games.get(seat.name)
            if seat.player_id and raw:
                replay_rows += await asyncio.to_thread(
                    persist_replays_sync, ws.event_id, seat.player_id, seat.name, raw,
                )
        lines.append(f"Replays: {replay_rows} rows touched")

    if ws.announce:
        announced = await post_championship_for_event(bot, ws.event_id, ws.thread_id)
        lines.append("Championship announcement posted." if announced
                     else "⚠️ Championship announcement did not post — check the logs.")

    embed = discord.Embed(
        title=f"Backfill complete — {ws.event_name}",
        description="\n".join(lines),
        color=discord.Color.green(),
    )
    return embed


def _apply_workspace_sync(ws: Workspace) -> list[str]:
    matches = [m if m.score else replace(m, score=PLACEHOLDER_SCORE) for m in ws.matches]
    lines: list[str] = []
    with SessionLocal() as session:
        taken_player_ids = {
            pid for pid in session.execute(
                select(PodDraftParticipant.player_id).where(
                    PodDraftParticipant.event_id == ws.event_id,
                    PodDraftParticipant.player_id.isnot(None),
                )
            ).scalars()
        }
        for seat in ws.seats:
            participant = upsert_participant(
                session, ws.event_id, display_name=seat.name, draftmancer_name=seat.name,
            )
            participant.display_name = seat.name
            if seat.player_id and participant.player_id is None and seat.player_id not in taken_player_ids:
                participant.player_id = seat.player_id
                taken_player_ids.add(seat.player_id)
        session.flush()

        for m in matches:
            row = record_match(session, ws.event_id, m.round, m.player_a, m.player_b, m.winner, m.score)
            if m.reported_at is not None:
                row.reported_at = m.reported_at

        standings = compute_placements([s.name for s in ws.seats], matches, seat_records(ws))
        final = [
            FinalStanding(
                draftmancer_name=st.player_name,
                placement=st.rank,
                record=f"{st.wins}-{st.losses}",
                eliminated_round=None if st.rank == 1 else TOTAL_ROUNDS,
            )
            for st in standings
        ]
        event = finalize_champion(session, ws.event_id, final)
        event.current_round = TOTAL_ROUNDS
        if not ws.announce and event.championship_posted_at is None:
            event.championship_posted_at = datetime.now(timezone.utc)

        seat_errors = []
        for seat in ws.seats:
            result = apply_seat(
                session, ws.event_id, seat.name,
                colors=seat.colors, caption=seat.caption, screenshot=seat.screenshot_url,
            )
            if not result.matched:
                seat_errors.append(result.error)
        session.commit()

    champion = standings[0].player_name if standings else None
    lines.append(f"Wrote {len(ws.seats)} players, {len(matches)} matches. Champion: **{champion}**")
    for error in seat_errors:
        lines.append(f"⚠️ {error}")
    return lines


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PodBackfill(bot))
