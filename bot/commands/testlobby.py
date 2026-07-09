"""Owner-only `!test` — sandbox for previewing the pod-draft lobby embed and live tournament path.

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

from sqlalchemy import any_, delete, select, update

from bot.config import settings
from bot.database import SessionLocal
from bot.models import MagicSet, Player, PodDraftEvent, PodDraftParticipant
from bot.services.lobby_embed import (
    LobbyReadyButtonView,
    build_drafting_view,
    register_force_start_preview,
    register_settings_preview,
    render as render_lobby_embed,
    render_ready_check_progress,
)
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_deck_color import SubmitDeckView
from bot.services.pod_draft_manager import PodDraftManager, start_manager
from bot.services.pod_drafts import seed_event_participants
from bot.sets import active_set_code
from bot.services.pod_format import format_display
from bot.services.pod_pairing_select import DEFAULT_PAIRING_MODE, pairing_label
from bot.services.pod_seating_select import seating_mode_label
from bot.services.player_stats import rank_players_for_set
from bot.commands.pod_draft import build_seeding_image_message_from_names, post_manual_seating_table, post_table
from bot.commands.pod_split import build_split_view
from bot.commands.test_group import register_test_fallback
from bot.services.pod_format_select import FormatSelectView
from bot.services.pod_settings_view import PodSettingsView
from bot.services.pod_drafts import normalize_player_name
from bot.services.pod_swiss import Standing
from bot.services.pod_tournament import (
    REVIEW_EMOJI,
    ParticipantDeckData,
    actor_label,
    build_draft_review_message,
    build_trophy_hype_view,
    mark_trophy_match,
    pod_voice_channel_url,
    render_draft_review_embed,
    round_embed,
    start_tournament,
)
from bot.slug import disambiguate_slug, slugify


log = logging.getLogger(__name__)

# In testlobby the invoker plays this seat in the fake roster.
_INVOKER_SEAT = "Noya"

# Module-level scratch store for the SubmitDeck POC; cleared on bot restart.
_TEST_DECK_COLORS: dict[int, str] = {}

# Fictional 8-player roster for the live-seeded tournament path (`podbracket` / `podswiss` / `round1`).
_LIVE_TEST_ROSTER = ["Ava", "Bram", "Cara", "Dex", "Eli", "Fern", "Gus", "Hana"]
_LIVE_TEST_STATUS = "test"

# Arena handles for the fictional roster so the live round embeds exercise the real Round 1 arena
# rendering. Bram's handle diverges from the Discord name (shows the 'arena (discord)' form); the rest
# match (collapse to the handle alone).
_LIVE_TEST_ARENA = {
    "Bram": "driftwood#49190",
    "Cara": "Cara#10003",
    "Dex": "Dex#10004",
    "Eli": "Eli#10005",
    "Fern": "Fern#10006",
    "Gus": "Gus#10007",
    "Hana": "Hana#10008",
}


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
            leaderboard_opt_in=False,
        )
        session.add(player)
        session.flush()
    return player.id


def _ensure_fictional_player_sync(session, display_name: str, arena_name: str) -> str:
    """Find-or-create a discord-less Player carrying `arena_name` for a fictional live-test roster
    member, so the round embeds resolve a linked Arena handle. Keyed on the arena alias so repeated
    `!test` runs reuse the same row instead of piling up duplicates."""
    normalized = normalize_player_name(arena_name)
    existing = session.execute(
        select(Player).where(normalized == any_(Player.arena_aliases))
    ).scalar_one_or_none()
    if existing is not None:
        return existing.id
    taken = set(session.execute(select(Player.slug)).scalars().all())
    player = Player(
        slug=disambiguate_slug(slugify(display_name), taken),
        discord_id=f"testlobby-{normalized}",
        discord_username=display_name,
        display_name=display_name,
        arena_name=arena_name,
        arena_aliases=[normalized],
        active=True,
        leaderboard_opt_in=False,
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
            set_code=active_set_code(),
            name="Testlobby Live Pod",
            draftmancer_session=session_id,
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
            for name in roster:
                arena = _LIVE_TEST_ARENA.get(name)
                if arena is None:
                    continue
                player_id = _ensure_fictional_player_sync(session, name, arena)
                session.execute(
                    update(PodDraftParticipant)
                    .where(
                        PodDraftParticipant.event_id == event_id,
                        PodDraftParticipant.draftmancer_name == name,
                    )
                    .values(player_id=player_id)
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


# Fictional pre-claims so a single real click by the invoker crosses the split threshold and
# materializes the overflow table. Negative ids mark fixtures so the ping block renders them as
# plain names rather than trying to mention a real user.
_SPLIT_PRESEED = [(-1, "Ava"), (-2, "Bram"), (-3, "Cara"), (-4, "Dex"), (-5, "Eli")]


def _split_test_base_name() -> str:
    return f"{active_set_code()} Split Test"


def _seed_split_source_sync(channel_id: int) -> str:
    """Seed a stand-in 'Table 1' source pod so `!test split` has a real event to clone. Returns its id."""
    now = datetime.now(timezone.utc)
    event_id = str(uuid4())
    with SessionLocal() as session:
        session.add(PodDraftEvent(
            id=event_id,
            event_date=now.date(),
            event_time=now,
            set_code=active_set_code(),
            name=_split_test_base_name(),
            draftmancer_session=f"TESTSPLIT-{channel_id}",
            discord_thread_id=str(channel_id),
            sesh_message_id=None,
            socket_status=_LIVE_TEST_STATUS,
            pairing_mode=DEFAULT_PAIRING_MODE,
        ))
        session.commit()
    return event_id


def _purge_split_family_sync(base_name: str) -> list[tuple[str, str]]:
    """Delete the source pod and every table split off it. Returns (event_id, thread_id) so the caller
    can evict managers and remove the created threads."""
    with SessionLocal() as session:
        rows = session.execute(
            select(PodDraftEvent.id, PodDraftEvent.discord_thread_id)
            .where(PodDraftEvent.name.ilike(f"{base_name}%"))
        ).all()
        ids = [row[0] for row in rows]
        if ids:
            session.execute(delete(PodDraftEvent).where(PodDraftEvent.id.in_(ids)))
            session.commit()
    return [(row[0], row[1]) for row in rows]


def _purge_live_test_pods_sync(channel_id: int) -> list[str]:
    """Delete prior live-test events for this channel (cascades to participants + matches). Returns
    the purged event ids so the caller can evict their managers."""
    with SessionLocal() as session:
        ids = session.execute(
            select(PodDraftEvent.id).where(
                PodDraftEvent.discord_thread_id == str(channel_id),
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
        bot, event_id, session_id, channel_id, active_set_code(), len(roster),
        event_name="Testlobby Live Pod",
        draftmancer_url=f"{settings.draftmancer_web_url}/?session={session_id}",
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


async def _evict_test_managers_for_channel(channel_id: int) -> None:
    """Drop any lingering manager for this channel so a fresh `!test` preview isn't intercepted by a
    prior podX run's manager — otherwise its current_round>0 trips the pairing-lock guard on the
    preview's Settings panel."""
    stale = [m for m in ACTIVE_POD_MANAGERS.values() if m.thread_id == channel_id]
    for mgr in stale:
        for task in (mgr.grace_task, mgr.championship_task):
            if task is not None and not task.done():
                task.cancel()
        await mgr.disconnect_safely()


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
    await _delete_last_test_messages(ctx.channel)


def _top_ranked_names_sync(n: int) -> list[str]:
    with SessionLocal() as session:
        set_id = session.execute(
            select(MagicSet.id).where(MagicSet.code == active_set_code())
        ).scalar_one_or_none()
        if not set_id:
            return []
        return [r.display_name for r in rank_players_for_set(session, set_id)[:n]]


_SEEDING_FILLERS = ["Marina", "Quill", "Ridley", "Sable", "Tovo", "Umbra"]


async def _post_test_seeding(ctx, count: int = 8) -> None:
    """Render the /pod-seeding embed (seat-column table + the round-table PNG) for `count` players from
    the local leaderboard, padding with fictional fillers when the DB has fewer. Bypasses the sesh fetch;
    local DB only."""
    ranked = await asyncio.to_thread(_top_ranked_names_sync, count)
    if not ranked:
        await ctx.send("No ranked players in the local DB — run seed_local_players + refresh_stats first.")
        return
    yes = ranked[:count]
    yes += [f for f in _SEEDING_FILLERS if f not in yes][: max(0, count - len(yes))]
    file, embed = await asyncio.to_thread(build_seeding_image_message_from_names, yes)
    await post_table(ctx.bot, ctx.channel, file, embed)


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
    lobby + ready-check flow runs. Local DB only."""
    if await _refuse_if_prod(ctx):
        return
    await _purge_and_reset_test(ctx)
    channel_id = ctx.channel.id
    event_id, session_id = await asyncio.to_thread(
        _seed_live_test_event_sync, channel_id, DEFAULT_PAIRING_MODE,
    )
    url = f"{settings.draftmancer_web_url}/?session={session_id}"
    log.info(f"[testlobby] live lobby connecting event={event_id} session={session_id}")
    manager = await start_manager(
        ctx.bot, event_id, session_id, channel_id, active_set_code(), len(_LIVE_TEST_ROSTER),
        event_name="Testlobby Live Pod", draftmancer_url=url,
    )
    if manager is None:
        await ctx.send("⚠️ Could not connect to Draftmancer — see logs.")
        return
    await ctx.send(f"🧪 Connected to Draftmancer `{session_id}`.")


async def _start_test_split(ctx) -> None:
    """Drive the real `/pod-split` flow: seed a source pod, then post the prod claim card preseeded to
    one below threshold so the invoker's single click materializes the overflow table (real thread +
    Draftmancer lobby + tournament manager). Local DB only."""
    if await _refuse_if_prod(ctx):
        return
    purged = await asyncio.to_thread(_purge_split_family_sync, _split_test_base_name())
    for old_id, old_thread in purged:
        mgr = ACTIVE_POD_MANAGERS.get(old_id)
        if mgr is not None:
            for task in (mgr.grace_task, mgr.championship_task):
                if task is not None and not task.done():
                    task.cancel()
            await mgr.disconnect_safely()
        if old_thread and old_thread != str(ctx.channel.id):
            thread = ctx.bot.get_channel(int(old_thread))
            if thread is not None:
                try:
                    await thread.delete()
                except discord.HTTPException:
                    pass
    source_id = await asyncio.to_thread(_seed_split_source_sync, ctx.channel.id)
    preseed = _SPLIT_PRESEED[: max(0, settings.pod_split_open_threshold - 1)]
    log.info(f"[testlobby] split preview seeded source={source_id} preseed={len(preseed)}")
    lobby_channel = ctx.channel.parent if isinstance(ctx.channel, discord.Thread) else ctx.channel
    view = await build_split_view(ctx.bot, source_id, lobby_channel=lobby_channel, preseeded_claims=preseed)
    if view is None:
        await ctx.send("could not seed the split source event")
        return
    view.claim_message = await ctx.send(embed=view.render_embed(), view=view)


async def _test_submit_deck_color(interaction: discord.Interaction, color: str) -> None:
    _TEST_DECK_COLORS[interaction.user.id] = color
    log.info(f"testlobby deck color saved: user={interaction.user.id} color={color}")


async def _test_lookup_deck_state(interaction: discord.Interaction) -> str | None:
    return _TEST_DECK_COLORS.get(interaction.user.id)


def _submit_deck_view() -> SubmitDeckView:
    """Build a SubmitDeckView (button form) for the testlobby channel preview."""
    return SubmitDeckView(_test_submit_deck_color, _test_lookup_deck_state)


def _review_preview_roster() -> list[dict]:
    """Fixture roster for the `!test review` preview — fictional seats with varied colors, records, slugs."""
    colors = ["WU", "BRg", "UG", "R", "WUBRG", "BR", "WGu", "UB"]
    records = ["3-0", "2-1", "2-1", "2-1", "1-2", "1-2", "1-2", "0-3"]
    return [
        {
            "seat_index": i, "name": name, "colors": colors[i % len(colors)],
            "result": records[i % len(records)], "slug": slugify(name),
        }
        for i, name in enumerate(_LIVE_TEST_ROSTER)
    ]


_TEST_DECK_SCREENSHOT_URL = "https://placehold.co/1280x720/2b2d31/ffffff/png?text=Deck+Screenshot"


def _trophy_hype_preview() -> discord.ui.LayoutView:
    """The #trophy-hype champion card rendered from fixture data via the prod builder."""
    champion = Standing(
        rank=1, player_id="Ava", player_name="Ava", wins=3, losses=0,
        omw_pct=0.0, gw_pct=0.0, ogw_pct=0.0,
    )
    key = normalize_player_name(champion.player_name)
    return build_trophy_hype_view(
        [champion],
        event_name="SOS Pod Draft #6 - Jun 3",
        displays={key: {"display_name": "Ava"}},
        player_colors={key: "URg"},
        deck_data={key: ParticipantDeckData(
            colors="URg",
            screenshot_url=_TEST_DECK_SCREENSHOT_URL,
            screenshot_caption="Izzet spells with a green splash for the bombs",
        )},
        guild_id=1,
        thread_id=1,
    )


def _round1_preview_states(seated: bool) -> list[dict]:
    """In-memory Round-1 match states for the no-DB `round1` snapshot, fed through the prod `round_embed`
    builder so the rendering stays in sync — only the match data is fixtured. Arena handles come from
    `_LIVE_TEST_ARENA` (Bram diverges → 'arena (discord)'; the rest collapse to the handle). Seated
    cross-pairs 1v5/2v6/...; `seated=False` previews the random header. Use `podswiss` to drive rounds."""
    roster = _LIVE_TEST_ROSTER
    states: list[dict] = []
    for offset in range(4):
        a, b = roster[offset], roster[offset + 4]
        a_arena = _LIVE_TEST_ARENA.get(a) or f"{a}#10001"
        b_arena = _LIVE_TEST_ARENA.get(b) or f"{b}#10005"
        states.append({
            "a_name": a, "a_display": a, "a_arena": a_arena,
            "a_record": "0-0", "a_seat": offset + 1 if seated else None,
            "b_name": b, "b_display": b, "b_arena": b_arena,
            "b_record": "0-0", "b_seat": offset + 5 if seated else None,
            "winner_name": None, "score": None,
        })
    return states


# Fixture records for the no-DB `round2` / `round3` snapshots: round 2 splits into Winners (1-0) and
# Losers (0-1); round 3 into Trophy (2-0), 1-1, and Last Chance (0-2).
_LATER_ROUND_PREVIEW = {
    2: [("Ava", "Bram", "1-0", "1-0"), ("Cara", "Dex", "1-0", "1-0"),
        ("Eli", "Fern", "0-1", "0-1"), ("Gus", "Hana", "0-1", "0-1")],
    3: [("Ava", "Bram", "2-0", "2-0"), ("Cara", "Dex", "1-1", "1-1"),
        ("Eli", "Fern", "1-1", "1-1"), ("Gus", "Hana", "0-2", "0-2")],
}


def _later_round_preview_states(round_num: int) -> list[dict]:
    """In-memory match states for the no-DB `round2` / `round3` snapshots, fed through the prod
    `round_embed` builder so the grouped rendering (Winners/Losers, Trophy/1-1/Last Chance) and arena
    handles stay in sync. Only the match data is fixtured."""
    states: list[dict] = []
    for a, b, a_record, b_record in _LATER_ROUND_PREVIEW[round_num]:
        states.append({
            "match_id": f"{a}-{b}", "a_name": a, "b_name": b,
            "a_display": a, "b_display": b,
            "a_arena": _LIVE_TEST_ARENA.get(a) or f"{a}#10001",
            "b_arena": _LIVE_TEST_ARENA.get(b) or f"{b}#10005",
            "a_record": a_record, "b_record": b_record,
            "winner_name": None, "score": None,
        })
    mark_trophy_match(states, round_num)
    return states


_THREAD_NAME = "SOS Pod Draft #3 - May 15"
_DRAFTMANCER_URL = f"{settings.draftmancer_web_url}/?session=LLUT-SOS-May-15-D"
_RSVPS_YES = [
    "Noya", "Bacchus", "NiamhIsTired", "maimslap", "Waveofshadow", "Elfandor",
    "fullerene60", "whalematron", "springbok7", "jonnietang",
]
_RSVPS_MAYBE = ["Aristeo", "DongSlinger420", "Oophies"]
_SPECTATORS = ["Tassagk", "Vesperin"]
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
    "drafting", "complete", "submit", "podbracket", "podswiss", "podrandom", "podlobby", "format",
    "seeding", "trophyhype", "round1", "round2", "round3", "voicelink", "review", "split",
)

_LIVE_POD_MODES = {"podbracket": "bracket", "podswiss": "swiss", "podrandom": "random"}

_LAST_MESSAGE: dict[int, discord.Message] = {}
_LAST_PROGRESS_MESSAGES: dict[int, list[discord.Message]] = {}


async def _delete_last_test_messages(channel) -> None:
    """Clear the previous testlobby preview before a fresh run by deleting only the tracked last
    message(s) for this channel — never sweep the channel history, which would also take out unrelated
    bot messages."""
    last = _LAST_MESSAGE.pop(channel.id, None)
    progress = _LAST_PROGRESS_MESSAGES.pop(channel.id, None) or []
    for msg in [last, *progress]:
        if msg is None:
            continue
        try:
            await msg.delete()
        except discord.HTTPException:
            pass


_PROGRESS_STATES = ("ready", "notready", "cancelled", "superseded", "drafting", "complete")

def _preview_settings_labels() -> dict:
    return dict(
        format_label=format_display(active_set_code()),
        pairing_label=pairing_label(DEFAULT_PAIRING_MODE),
        seating_label=seating_mode_label("random"),
    )


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
        spectators=_SPECTATORS,
        **_preview_settings_labels(),
    )
    spectate_url = f"{_DRAFTMANCER_URL}&spectate=preview"
    if state == "drafting":
        view: discord.ui.View | None = build_drafting_view(spectate_url)
    elif state == "complete":
        view = None
    else:
        view = LobbyReadyButtonView(
            draftmancer_url=_DRAFTMANCER_URL,
            ready_disabled=(render_state == "ready"),
            show_force_start=(render_state == "unlinked"),
            spectate_url=spectate_url,
        )
    return embed, view


def _build_ready_progress(state: str) -> list[tuple[discord.Embed, discord.ui.View | None]]:
    """Preview the ready-check progress card(s) for the states where one is posted in prod. Returns a
    list: `superseded` mirrors a real retry — the collapsed old receipt plus the fresh active check
    below it — every other state is a single card. Buttons live only on an active check."""
    if state not in _PROGRESS_STATES:
        return []
    in_session = list(_LINKED_EIGHT)
    active_view = LobbyReadyButtonView(
        draftmancer_url=_DRAFTMANCER_URL, ready_disabled=True, show_force_start=True,
    )
    if state == "ready":
        embed = render_ready_check_progress(
            _THREAD_NAME, in_session, state="ready",
            draftmancer_url=_DRAFTMANCER_URL, ready_arena_names={arena for arena, _ in _LINKED_EIGHT[:3]},
            initiated_by=_LINKED_EIGHT[0][1], **_preview_settings_labels(),
        )
        return [(embed, active_view)]
    if state in ("notready", "cancelled"):
        decliner = None if state == "cancelled" else _LINKED_EIGHT[3][0]
        cancel_reason = "Player list changed" if state == "cancelled" else None
        embed = render_ready_check_progress(
            _THREAD_NAME, in_session, state="notready", draftmancer_url=_DRAFTMANCER_URL,
            decliner_name=decliner, cancel_reason=cancel_reason, ready_count=3, total_count=8,
            **_preview_settings_labels(),
        )
        return [(embed, None)]
    if state == "superseded":
        collapsed = render_ready_check_progress(
            _THREAD_NAME, in_session, state="notready", draftmancer_url=_DRAFTMANCER_URL,
            decliner_name=_LINKED_EIGHT[3][0], superseded=True, ready_count=3, total_count=8,
            **_preview_settings_labels(),
        )
        active = render_ready_check_progress(
            _THREAD_NAME, in_session, state="ready",
            draftmancer_url=_DRAFTMANCER_URL, ready_arena_names=set(),
            initiated_by=_LINKED_EIGHT[0][1], **_preview_settings_labels(),
        )
        return [(collapsed, None), (active, active_view)]
    embed = render_ready_check_progress(
        _THREAD_NAME, in_session, state=state, draftmancer_url=_DRAFTMANCER_URL,
        **_preview_settings_labels(),
    )
    return [(embed, None)]


async def _settings_preview_noop(interaction: discord.Interaction, value: str) -> str | None:
    return None


async def _settings_preview_seating_noop(
    interaction: discord.Interaction, ordered_user_names: list[str],
) -> str | None:
    return None


async def _settings_preview_seat_order() -> list[tuple[str, str]]:
    return [(arena, display or arena) for arena, display in _LINKED_EIGHT]


async def _settings_preview_on_seated(interaction: discord.Interaction, labels: list[str]) -> None:
    await post_manual_seating_table(interaction.client, interaction.channel, labels, actor_label(interaction))


async def _settings_preview_link_targets() -> list[str]:
    return ["Stranger#12345"]


async def _settings_preview_on_link(
    interaction: discord.Interaction, arena_name: str, member: discord.abc.User,
) -> str | None:
    return None


def _settings_preview_view() -> PodSettingsView:
    """No-op Settings panel so `!test` can preview the format + pairing + seats dropdowns plus the Link
    Players flow with no pod. Defaults to Seats: Random (like a fresh pod); pick Manual in the dropdown
    to reveal the Seat Order button."""
    return PodSettingsView(
        on_format=_settings_preview_noop, on_pairing=_settings_preview_noop,
        current_code=None, current_mode=DEFAULT_PAIRING_MODE,
        on_seating_mode=_settings_preview_noop, current_seating="random",
        on_seating=_settings_preview_seating_noop, seat_order_provider=_settings_preview_seat_order,
        on_seated=_settings_preview_on_seated,
        link_targets_provider=_settings_preview_link_targets, on_link=_settings_preview_on_link,
    )


async def setup(bot: commands.Bot) -> None:
    """Wire the lobby states as the `!test` fallback and register the settings preview."""
    register_settings_preview(_settings_preview_view)
    register_force_start_preview(lambda: (5, 8, ["Bram", "Cara", "Dex"]))

    async def test_lobby(ctx: commands.Context, state: str = "", extra: str = "") -> None:
        """Owner-only. Render the pod-draft lobby embed in this channel.

        `state` ∈ empty | partial | linked | unlinked | ready | notready | cancelled | superseded |
        drafting | complete | submit | podbracket | podswiss | podrandom | podlobby | format |
        seeding | trophyhype | round1 | round2 | round3 | voicelink.
        `ready` shows the active ready-check card; clicking its Force Start button previews the ephemeral
        confirm dialog (no live pod needed). `round1`/`round2`/`round3` are no-DB snapshots of each round
        embed (`round1 random` for the random-pairing header).
        No arg → posts the beginning lobby state. Every invocation posts fresh messages.
        `podbracket` / `podswiss` / `podrandom` seed a real 8-player pod (seat 1 = you) and hand off to
        the prod tournament code, so the round embeds + result dropdowns drive the real round-to-round
        flow (these write to the local DB). `round1` (`round1 random` for random pairing) is a no-DB
        snapshot of the Round 1 embed only — to drive rounds, use `podswiss`. `podlobby` connects to a
        live Draftmancer session for ready-check testing. `seeding [count]` posts the /pod-seeding embed
        (table + round-table PNG) for `count` players (default 8; ranked padded with fillers), no sesh."""
        if state and state not in _VALID_STATES:
            await ctx.send(f"unknown state `{state}`; pick one of: {', '.join(_VALID_STATES)}")
            return

        if state in _LIVE_POD_MODES:
            await _start_live_test_pod(ctx, _LIVE_POD_MODES[state])
            return

        if state == "podlobby":
            await _start_live_test_lobby(ctx)
            return

        if state == "split":
            await _start_test_split(ctx)
            return

        if state == "seeding":
            await _post_test_seeding(ctx, int(extra) if extra.isdigit() else 8)
            return

        if state == "submit":
            await ctx.send(view=_submit_deck_view())
            return

        if state == "trophyhype":
            await ctx.send(view=_trophy_hype_preview())
            return

        if state == "round1":
            await ctx.send(embed=round_embed(1, _round1_preview_states(seated=extra != "random")))
            return

        if state in ("round2", "round3"):
            round_num = int(state[-1])
            await ctx.send(embed=round_embed(round_num, _later_round_preview_states(round_num)))
            return

        if state == "voicelink":
            channel = discord.utils.get(
                ctx.guild.voice_channels, name=settings.pod_draft_voice_channel_name,
            ) if ctx.guild else None
            if channel is None:
                await ctx.send(f"(no '{settings.pod_draft_voice_channel_name}' voice channel in this server)")
                return
            await ctx.send(channel.jump_url)
            return

        if state == "review":
            voice_url = pod_voice_channel_url(ctx.guild)
            embed = render_draft_review_embed(_review_preview_roster(), event_name="Pod Draft Preview")
            msg = await ctx.send(
                content=build_draft_review_message(voice_url),
                embed=embed, allowed_mentions=discord.AllowedMentions.none(),
            )
            try:
                await msg.add_reaction(REVIEW_EMOJI)
            except discord.HTTPException:
                pass
            return

        if state == "format":
            async def _test_apply(inter: discord.Interaction, code: str) -> str | None:
                embed = render_lobby_embed(
                    _THREAD_NAME, _RSVPS_YES, _RSVPS_MAYBE, list(_LINKED_EIGHT),
                    state="linked", draftmancer_url=_DRAFTMANCER_URL,
                    format_label=format_display(code), pairing_label=pairing_label(DEFAULT_PAIRING_MODE),
                    seating_label=seating_mode_label("random"),
                )
                await inter.channel.send(embed=embed)
                return None
            await ctx.send(view=FormatSelectView(_test_apply))
            return

        if state == "":
            state = "empty"

        await _evict_test_managers_for_channel(ctx.channel.id)
        embed, view = _build(state)
        _LAST_MESSAGE[ctx.channel.id] = await ctx.send(embed=embed, view=view)
        posted = [await ctx.send(embed=e, view=v) for e, v in _build_ready_progress(state)]
        _LAST_PROGRESS_MESSAGES[ctx.channel.id] = posted

    register_test_fallback(test_lobby)
