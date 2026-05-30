"""Owner-only `!testlobby` — sandbox for previewing the pod-draft lobby embed and live tournament path.

This entire module is throwaway scaffolding for design iteration. To remove it:
  1. Delete this file.
  2. Drop the `setup` call from bot/main.py setup_hook.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

import discord
from discord.ext import commands

from sqlalchemy import delete, select, update

from bot.config import settings
from bot.database import SessionLocal
from bot.models import Player, PodDraftEvent, PodDraftParticipant
from bot.services.lobby_embed import (
    LobbyReadyButtonView,
    register_settings_preview,
    render as render_lobby_embed,
    render_ready_check_progress,
)
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_deck_color import SubmitDeckView
from bot.services.pod_draft_manager import PodDraftManager, start_manager
from bot.services.pod_drafts import seed_event_participants
from bot.sets import ACTIVE_SET_CODE
from bot.services.pod_format import label_for
from bot.services.pod_format_select import FormatSelectView
from bot.services.pod_settings_view import PodSettingsView
from bot.services.pod_tournament import start_tournament
from bot.slug import disambiguate_slug, slugify


log = logging.getLogger(__name__)

# In testlobby the invoker plays this seat in the fake roster.
_INVOKER_SEAT = "Noya"

# Module-level scratch store for the SubmitDeck POC; cleared on bot restart.
_TEST_DECK_COLORS: dict[int, str] = {}
_TEST_REVIEW_CHOICES: dict[int, bool] = {}

# Fictional 8-player roster for the live-seeded tournament path (`podbracket` / `podswiss`).
_LIVE_TEST_ROSTER = ["Ava", "Bram", "Cara", "Dex", "Eli", "Fern", "Gus", "Hana"]
_LIVE_TEST_STATUS = "test"


def _looks_like_prod_db() -> bool:
    url = settings.database_url or ""
    return "supabase" in url or "pooler" in url


def _ensure_invoker_player_sync(session, discord_id: int, display_name: str) -> str:
    """Find-or-create a local Player for the testlobby invoker so seat 1 receives the real pairing /
    deck DMs and can report its own matches."""
    player = session.execute(
        select(Player).where(Player.discord_id == str(discord_id))
    ).scalar_one_or_none()
    if player is None:
        taken = set(session.execute(select(Player.slug)).scalars().all())
        player = Player(
            slug=disambiguate_slug(slugify(display_name), taken),
            discord_id=str(discord_id),
            discord_username=display_name,
            display_name=display_name,
            active=True,
        )
        session.add(player)
        session.flush()
    return player.id


def _seed_live_test_event_sync(
    channel_id: int, mode: str, roster: list[str] | None = None,
    invoker_id: int | None = None,
) -> tuple[str, str]:
    """Create a throwaway PodDraftEvent in the local DB. With `roster`, also seed seated participants
    (seat 0 linked to the invoker so they get the real DMs). With no roster, the event is lobby-only —
    participants arrive from the live Draftmancer session. Returns (event_id, session_id)."""
    now = datetime.now(timezone.utc)
    event_id = str(uuid4())
    session_id = f"TESTLOBBY-{channel_id}"
    with SessionLocal() as session:
        session.add(PodDraftEvent(
            id=event_id,
            event_date=now.date(),
            event_time=now,
            set_code=ACTIVE_SET_CODE,
            name="Testlobby Live Pod",
            draftmancer_session=session_id,
            draftmancer_url=f"https://draftmancer.com/?session={session_id}",
            discord_thread_id=str(channel_id),
            sesh_message_id=f"testlobby-{channel_id}",
            socket_status=_LIVE_TEST_STATUS,
            pairing_mode=mode,
        ))
        session.flush()
        if roster:
            seed_event_participants(session, event_id, roster)
            for seat, name in enumerate(roster):
                session.execute(
                    update(PodDraftParticipant)
                    .where(
                        PodDraftParticipant.event_id == event_id,
                        PodDraftParticipant.draftmancer_name == name,
                    )
                    .values(seat_index=seat)
                )
            if invoker_id is not None:
                player_id = _ensure_invoker_player_sync(session, invoker_id, roster[0])
                session.execute(
                    update(PodDraftParticipant)
                    .where(
                        PodDraftParticipant.event_id == event_id,
                        PodDraftParticipant.draftmancer_name == roster[0],
                    )
                    .values(player_id=player_id)
                )
        session.commit()
    return event_id, session_id


def _purge_live_test_pods_sync(channel_id: int) -> list[str]:
    """Delete prior live-test events for this channel (cascades to participants + matches). Returns
    the purged event ids so the caller can evict their managers."""
    with SessionLocal() as session:
        ids = session.execute(
            select(PodDraftEvent.id).where(
                PodDraftEvent.discord_thread_id == str(channel_id),
                PodDraftEvent.socket_status == _LIVE_TEST_STATUS,
            )
        ).scalars().all()
        if ids:
            session.execute(delete(PodDraftEvent).where(PodDraftEvent.id.in_(ids)))
            session.commit()
    return list(ids)


def _build_live_test_manager(
    bot, event_id: str, session_id: str, channel_id: int, mode: str, roster: list[str],
) -> PodDraftManager:
    """A socket-less manager wired to drive the real tournament code. Never calls connect()."""
    manager = PodDraftManager(
        bot, event_id, session_id, channel_id, ACTIVE_SET_CODE, len(roster),
        event_name="Testlobby Live Pod",
        draftmancer_url=f"https://draftmancer.com/?session={session_id}",
    )
    manager.tournament_roster = list(roster)
    manager.pairing_mode = mode
    return manager


async def _refuse_if_prod(ctx) -> bool:
    if _looks_like_prod_db():
        await ctx.send(
            "⚠️ Refusing — `DATABASE_URL` looks like prod. The live testlobby pod only runs against "
            "the local dev DB."
        )
        return True
    return False


async def _purge_and_reset_test(ctx) -> None:
    """Delete prior test events for this channel, disconnect/evict their managers, and clear the thread."""
    purged = await asyncio.to_thread(_purge_live_test_pods_sync, ctx.channel.id)
    for old_id in purged:
        old = ACTIVE_POD_MANAGERS.get(old_id)
        if old is not None:
            for task in (old.grace_task, old.championship_task):
                if task is not None and not task.done():
                    task.cancel()
            await old.disconnect_safely()
    await _reset_podbracket(ctx.channel, ctx.bot.user)


async def _start_live_test_pod(ctx, mode: str) -> None:
    """Seed a real event + socket-less manager and hand off to the prod start_tournament, so the
    posted result dropdowns drive the real _handle_result_submission. Seat 1 is the invoker so they
    receive the real pairing / deck DMs. Local DB only."""
    if await _refuse_if_prod(ctx):
        return
    await _purge_and_reset_test(ctx)
    channel_id = ctx.channel.id
    roster = [ctx.author.display_name] + _LIVE_TEST_ROSTER[1:]
    event_id, session_id = await asyncio.to_thread(
        _seed_live_test_event_sync, channel_id, mode, roster, ctx.author.id,
    )
    manager = _build_live_test_manager(ctx.bot, event_id, session_id, channel_id, mode, roster)
    ACTIVE_POD_MANAGERS[event_id] = manager
    log.info(f"[testlobby] live {mode} pod seeded event={event_id} channel={channel_id}")
    await start_tournament(manager)


async def _start_live_test_lobby(ctx) -> None:
    """Seed a lobby-only event and connect a real manager to a live Draftmancer session, so the real
    lobby + ready-check flow runs. Open the session link in 6+ tabs to drive it. Local DB only."""
    if await _refuse_if_prod(ctx):
        return
    await _purge_and_reset_test(ctx)
    channel_id = ctx.channel.id
    event_id, session_id = await asyncio.to_thread(_seed_live_test_event_sync, channel_id, "swiss")
    url = f"https://draftmancer.com/?session={session_id}"
    log.info(f"[testlobby] live lobby connecting event={event_id} session={session_id}")
    manager = await start_manager(
        ctx.bot, event_id, session_id, channel_id, ACTIVE_SET_CODE, len(_LIVE_TEST_ROSTER),
        event_name="Testlobby Live Pod", draftmancer_url=url,
    )
    if manager is None:
        await ctx.send("⚠️ Could not connect to Draftmancer — see logs.")
        return
    await ctx.send(
        f"🧪 Connected to Draftmancer `{session_id}`. Open {url} in 6+ tabs with distinct names, "
        "then use the lobby card's **Ready Check** button. The card appears once players join."
    )


async def _test_submit_deck_color(interaction: discord.Interaction, color: str) -> None:
    _TEST_DECK_COLORS[interaction.user.id] = color
    log.info(f"testlobby deck color saved: user={interaction.user.id} color={color}")


async def _test_lookup_deck_state(interaction: discord.Interaction) -> tuple[str | None, bool | None]:
    return _TEST_DECK_COLORS.get(interaction.user.id), _TEST_REVIEW_CHOICES.get(interaction.user.id)


async def _test_review_toggle(interaction: discord.Interaction, wants_review: bool) -> None:
    _TEST_REVIEW_CHOICES[interaction.user.id] = wants_review
    log.info(f"testlobby review choice saved: user={interaction.user.id} wants={wants_review}")


def _submit_deck_view() -> SubmitDeckView:
    """Build a SubmitDeckView (button form) for the testlobby channel preview."""
    return SubmitDeckView(_test_submit_deck_color, _test_lookup_deck_state, _test_review_toggle)


_THREAD_NAME = "SOS Pod Draft #3 - May 15"
_DRAFTMANCER_URL = "https://draftmancer.com/?session=LLUT-SOS-May-15-D"
_RSVPS_YES = [
    "Noya", "Bacchus", "NiamhIsTired", "maimslap", "Waveofshadow", "Elfandor",
    "fullerene60", "whalematron", "springbok7", "jonnietang",
]
_RSVPS_MAYBE = ["Aristeo", "DongSlinger420", "Oophies"]
# Seats match the real Pod Draft #3 Draftmancer log (DraftLog_LLUSOS31). Arena tag = log userName;
# discord display name (second element) is what we show in the announcement.
_LINKED_EIGHT: list[tuple[str, str]] = [
    ("Noya#08011", "Noya"),
    ("Bacchus#23673", "Bacchus"),
    ("NiamhIsTired#12791", "NiamhIsTired"),
    ("maimslap#64991", "maimslap"),
    ("Waveofshadow#17843", "Waveofshadow"),
    ("Elfandor#43425", "Elfandor"),
    ("fullerene60#49190", "flutterdev"),
    ("whalematron#89523", "whalematron"),
]
_VALID_STATES = (
    "empty", "partial", "linked", "unlinked", "ready", "notready", "cancelled", "superseded",
    "drafting", "complete", "submit", "podbracket", "podswiss", "podlobby", "format",
)

_LAST_MESSAGE: dict[int, discord.Message] = {}
_LAST_PROGRESS_MESSAGE: dict[int, discord.Message] = {}


async def _reset_podbracket(channel, bot_user) -> None:
    """Wipe a prior testlobby run from this thread before starting fresh: drop the tracked preview
    messages and delete the bot's own messages so the new bracket isn't buried under stale rounds."""
    _LAST_MESSAGE.pop(channel.id, None)
    _LAST_PROGRESS_MESSAGE.pop(channel.id, None)
    try:
        async for msg in channel.history(limit=200):
            if msg.author.id == bot_user.id:
                try:
                    await msg.delete()
                except discord.HTTPException:
                    pass
    except discord.HTTPException:
        log.warning("could not sweep testlobby thread history", exc_info=True)


_PROGRESS_STATES = ("ready", "notready", "cancelled", "superseded", "drafting", "complete")


def _build(state: str) -> tuple[discord.Embed, discord.ui.View | None]:
    """Returns (embed, view) for a lobby-state preview."""
    if state == "empty":
        in_session: list[tuple[str, str | None]] = []
    elif state == "partial":
        in_session = list(_LINKED_EIGHT[:2])
    elif state == "unlinked":
        in_session = list(_LINKED_EIGHT[:7]) + [("Stranger#12345", None)]
    else:
        in_session = list(_LINKED_EIGHT)

    if state == "cancelled":
        render_state = "notready"
    elif state == "superseded":
        render_state = "ready"
    else:
        render_state = state
    decliner_name = _LINKED_EIGHT[3][0] if state == "notready" else None
    cancel_reason = "Player list changed" if state == "cancelled" else None
    initiated_by = _LINKED_EIGHT[0][1] if render_state == "ready" else None
    embed = render_lobby_embed(
        _THREAD_NAME, _RSVPS_YES, _RSVPS_MAYBE, in_session,
        state=render_state, draftmancer_url=_DRAFTMANCER_URL,
        decliner_name=decliner_name, cancel_reason=cancel_reason, initiated_by=initiated_by,
    )
    has_unrecognized = any(dn is None for _, dn in in_session)
    view: discord.ui.View | None = (
        None if state in ("drafting", "complete")
        else LobbyReadyButtonView(
            draftmancer_url=_DRAFTMANCER_URL,
            ready_disabled=(render_state == "ready" or has_unrecognized),
        )
    )
    return embed, view


def _build_ready_progress(state: str) -> tuple[discord.Embed, discord.ui.View | None] | None:
    """Preview the ready-check progress card (embed + view) for the states where one is posted in
    prod. View mirrors the manager: buttons disabled during `ready`, gone once the draft starts."""
    if state not in _PROGRESS_STATES:
        return None
    in_session = list(_LINKED_EIGHT)
    if state == "ready":
        ready_arena_names = {arena for arena, _ in _LINKED_EIGHT[:3]}
        embed = render_ready_check_progress(
            _THREAD_NAME, in_session, state="ready",
            draftmancer_url=_DRAFTMANCER_URL, ready_arena_names=ready_arena_names,
            initiated_by=_LINKED_EIGHT[0][1],
        )
    elif state in ("notready", "cancelled"):
        decliner = None if state == "cancelled" else _LINKED_EIGHT[3][0]
        cancel_reason = "Player list changed" if state == "cancelled" else None
        embed = render_ready_check_progress(
            _THREAD_NAME, in_session, state="notready", draftmancer_url=_DRAFTMANCER_URL,
            decliner_name=decliner, cancel_reason=cancel_reason,
        )
    elif state == "superseded":
        embed = render_ready_check_progress(
            _THREAD_NAME, in_session, state="notready", draftmancer_url=_DRAFTMANCER_URL,
            decliner_name=_LINKED_EIGHT[3][0], superseded=True,
        )
    else:
        embed = render_ready_check_progress(
            _THREAD_NAME, in_session, state=state, draftmancer_url=_DRAFTMANCER_URL,
        )
    view = (
        None if state in ("drafting", "complete")
        else LobbyReadyButtonView(
            draftmancer_url=_DRAFTMANCER_URL, ready_disabled=(state in ("ready", "superseded")),
        )
    )
    return embed, view


async def _sync_progress_card(
    channel: discord.abc.Messageable, progress: tuple[discord.Embed, discord.ui.View | None] | None,
) -> None:
    """Edit the lingering progress card in place, post a fresh one, or clear it — mirroring how the
    live manager keeps a single progress card updated across a ready check's lifecycle."""
    existing = _LAST_PROGRESS_MESSAGE.get(channel.id)
    if progress is None:
        if existing is not None:
            try:
                await existing.delete()
            except discord.HTTPException:
                pass
            _LAST_PROGRESS_MESSAGE.pop(channel.id, None)
        return
    embed, view = progress
    if existing is not None:
        try:
            await existing.edit(embed=embed, view=view)
            return
        except discord.HTTPException:
            _LAST_PROGRESS_MESSAGE.pop(channel.id, None)
    _LAST_PROGRESS_MESSAGE[channel.id] = await channel.send(embed=embed, view=view)


async def _settings_preview_noop(interaction: discord.Interaction, value: str) -> str | None:
    return None


def _settings_preview_view() -> PodSettingsView:
    """No-op Settings panel so `!testlobby` can preview the format + pairing dropdowns with no pod."""
    return PodSettingsView(
        on_format=_settings_preview_noop, on_pairing=_settings_preview_noop,
        current_code=None, current_mode="swiss",
    )


async def setup(bot: commands.Bot) -> None:
    """Wire the `!testlobby` command and register the settings preview."""
    register_settings_preview(_settings_preview_view)

    @bot.command(name="testlobby")
    @commands.is_owner()
    async def test_lobby(ctx: commands.Context, state: str = "") -> None:
        """Owner-only. Render the pod-draft lobby embed in this channel.

        `state` ∈ empty | partial | linked | unlinked | ready | notready | cancelled | superseded |
        drafting | complete | submit | podbracket | podswiss | podlobby | format.
        No arg → posts the beginning lobby state. A specific state → edits the last in place.
        `podbracket` / `podswiss` seed a real 8-player pod (seat 1 = you) and hand off to the prod
        tournament code. `podlobby` connects to a live Draftmancer session for ready-check testing."""
        if state and state not in _VALID_STATES:
            await ctx.send(f"unknown state `{state}`; pick one of: {', '.join(_VALID_STATES)}")
            return

        if state in ("podbracket", "podswiss"):
            await _start_live_test_pod(ctx, "bracket" if state == "podbracket" else "swiss")
            return

        if state == "podlobby":
            await _start_live_test_lobby(ctx)
            return

        if state == "submit":
            await ctx.send(view=_submit_deck_view())
            return

        if state == "format":
            async def _test_apply(inter: discord.Interaction, code: str) -> str | None:
                embed = render_lobby_embed(
                    _THREAD_NAME, _RSVPS_YES, _RSVPS_MAYBE, list(_LINKED_EIGHT),
                    state="linked", draftmancer_url=_DRAFTMANCER_URL,
                    format_label=label_for(code),
                )
                await inter.channel.send(embed=embed)
                return None
            await ctx.send(view=FormatSelectView(_test_apply))
            return

        if state == "":
            state = "empty"

        embed, view = _build(state)
        progress = _build_ready_progress(state)
        last = _LAST_MESSAGE.get(ctx.channel.id)
        if last is not None:
            try:
                await last.edit(embed=embed, view=view, attachments=[])
                await _sync_progress_card(ctx.channel, progress)
                return
            except discord.HTTPException:
                _LAST_MESSAGE.pop(ctx.channel.id, None)
        msg = await ctx.send(embed=embed, view=view)
        _LAST_MESSAGE[ctx.channel.id] = msg
        await _sync_progress_card(ctx.channel, progress)
