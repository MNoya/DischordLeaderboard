"""Draftmancer socket.io session lifecycle for a single pod-draft event.

One PodDraftManager per active event, kept in the module-level ACTIVE_POD_MANAGERS registry so the
ready check and bracket flows can look up the right session by event_id. Connects with
exponential backoff + jitter, joins the session, applies the agreed settings, and listens for
sessionUsers updates so later commands can act on who is in the lobby
"""
from __future__ import annotations

import asyncio
import gzip
import json
import logging
import random
import re
from datetime import datetime, timedelta, timezone

import discord
import socketio
from discord.ext import commands

from sqlalchemy import func, select

from bot import emojis
from bot.commands.messages import (
    MSG_BOT_RECONNECTED,
    MSG_LOBBY_FULL_PROMPT,
    MSG_MOCK_COMPLETE,
    MSG_MOCK_LOBBY_COUNTER,
    MSG_MOCK_LOBBY_OPEN,
)
from bot.config import settings
from bot.database import SessionLocal
from bot.discord_helpers import extract_avatar_hash
from bot.models import Player, PodDraftEvent, PodDraftParticipant
from bot.scripts.draftmancer_log import build_compact
from bot.services import bot_log as bot_log_mod
from bot.services.lobby_embed import (
    LobbyReadyButtonView,
    render as render_lobby_embed,
    render_ready_check_progress,
)
from bot.services.magicprotools import submit_to_api as submit_to_magicprotools
from bot.services import pod_format
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_pairing_select import pairing_label
from bot.services.pod_seating_select import seating_mode_label
from bot.services.pod_drafts import (
    attach_arena_alias,
    full_arena_handle,
    normalize_player_name,
    classify_lobby_names,
    delete_event_sync,
    draftmancer_url_for,
    finalize_mock_event,
    load_event_pairing_mode_sync,
    load_event_seating_mode_sync,
    name_token_match,
    player_for_name,
    seed_event_participants,
    update_event_format,
)
from bot.services.pod_tournament import (
    persist_pairing_mode,
    persist_seating_mode,
    refresh_round_pairing_messages,
    start_tournament,
)
from bot.services.player_stats import leaderboard_seat_order
from bot.slug import disambiguate_slug, slugify


log = logging.getLogger(__name__)


_BACKOFF_BASE_S = 1.0
_BACKOFF_MAX_S = 30.0
_BACKOFF_MAX_RETRIES = 8
_BOT_USER_NAME = "DisChordBot"
LOBBY_REHYDRATE_WINDOW = timedelta(hours=12)
_READY_TIMEOUT_S = 90
_READY_DEBOUNCE_S = 2.0
_LOBBY_FULL_THRESHOLD = 8
_LOBBY_HALF_THRESHOLD = _LOBBY_FULL_THRESHOLD // 2
_LOBBY_FULL_PROMPT_DELAY_S = 10
_AI_BOT_NAME_RE = re.compile(r"^Bot #\d+$")

_SEEDING_REFRESH_HOOK = None
_SEEDING_REPOST_HOOK = None


def set_seeding_refresh_hook(callback) -> None:
    """The command layer registers its seeding-table refresher here so the manager and the sesh listener
    can update the posted table without importing the command module (which imports the manager)."""
    global _SEEDING_REFRESH_HOOK
    _SEEDING_REFRESH_HOOK = callback


def set_seeding_repost_hook(callback) -> None:
    """Companion to set_seeding_refresh_hook: re-posts a fresh seeding table at the bottom of the thread
    (the in-place refresh only edits the existing ones)."""
    global _SEEDING_REPOST_HOOK
    _SEEDING_REPOST_HOOK = callback


def notify_seeding_change(bot, event_id: str) -> None:
    """Fire the registered seeding-table refresh (no-op if unset). Called on Draftmancer join/leave and
    on sesh RSVP edits; the refresher itself decides whether a table exists and the pod is leaderboard-seated."""
    if _SEEDING_REFRESH_HOOK is not None:
        asyncio.create_task(_SEEDING_REFRESH_HOOK(bot, event_id))


def notify_seeding_repost(bot, event_id: str) -> None:
    """Re-post a fresh seeding table at the bottom of the thread (no-op if unset). Fired when the spectate
    link goes up so the live table sits by the action instead of only at the scrolled-up pinned anchor."""
    if _SEEDING_REPOST_HOOK is not None:
        asyncio.create_task(_SEEDING_REPOST_HOOK(bot, event_id))


async def cancel_pod_event(event_id: str, *, actor: str) -> str | None:
    """Tear down a pod draft entirely: cancel pending tournament tasks, disconnect the manager, and
    delete the event row — the cascade drops participants, matches, replays, and DM trackers, which
    also removes the leaderboard pod page."""
    log.warning(f"pod-cancel: {actor} deleting event {event_id}")
    manager = ACTIVE_POD_MANAGERS.get(event_id)
    if manager is not None:
        for task in (manager.grace_task, manager.championship_task):
            if task is not None and not task.done():
                task.cancel()
        await manager.disconnect_safely()
    await asyncio.to_thread(delete_event_sync, event_id)
    return None


class PodDraftManager:
    def __init__(self, bot: commands.Bot, event_id: str, session_id: str, thread_id: int,
                 set_code: str, expected_attendee_count: int, *,
                 event_name: str = "Pod Draft",
                 draftmancer_url: str = "",
                 kind: str = "tournament",
                 mock_lobby_message: "discord.Message | None" = None,
                 rsvps_yes: list[str] | None = None,
                 rsvps_maybe: list[str] | None = None,
                 reconnect: bool = False) -> None:
        self.bot = bot
        self.event_id = event_id
        self.session_id = session_id
        self.thread_id = thread_id
        self.set_code = set_code
        self.expected_attendee_count = expected_attendee_count
        self.event_name = event_name
        self.draftmancer_url = draftmancer_url
        self.spectate_url: str | None = None
        self.kind = kind
        self.reconnect = reconnect
        self._lobby_card_adopt_attempted = False
        self.mock_lobby_message = mock_lobby_message
        self._thread_added_ids: set[str] = set()
        self.rsvps_yes: list[str] = list(rsvps_yes or [])
        self.rsvps_maybe: list[str] = list(rsvps_maybe or [])
        self.session_users: list[dict] = []
        self.session_spectators: list[dict] = []
        self.spectator_user_ids: set[str] = set()
        self.spectator_names: list[str] = []
        self.spectator_targets: list[tuple[str, str]] = []
        self.desired_seating: list[str] | None = None
        self.bot_user_id: str | None = None
        self.owner_claimed = False
        self._closed = False
        self.ready_check_active = False
        self.ready_users: set[str] = set()
        self.expected_user_ids: set[str] = set()
        self._lobby_full_prompt_task: asyncio.Task | None = None
        self._lobby_full_prompt_message: "discord.Message | None" = None
        self._lobby_full_prompted = False
        self._voice_link_posted = False
        self._ready_check_started_at = 0.0
        self.lobby_status_message: object | None = None
        self.ready_check_progress_message: object | None = None
        self._lobby_post_lock = asyncio.Lock()
        self._ready_timeout_task: asyncio.Task | None = None
        self.drafting = False
        self.draft_complete = False
        self.last_decliner_name: str | None = None
        self.last_cancel_reason: str | None = None
        self.last_ready_summary: tuple[int, int] | None = None
        self.initiated_by: str | None = None
        self.draft_logs: dict[str, dict] = {}
        self.mpt_task: asyncio.Task | None = None
        self.current_round = 0
        self.finalized = False
        self.tournament_roster: list[str] = []  # draftmancer userNames, set on endDraft
        self.tournament_players: list = []       # pod_swiss.Player list, set by pod_tournament.start_tournament
        self.pairing_mode = "swiss"              # 'swiss', 'bracket', or 'random'; resolved in start_tournament
        self.seating_mode = "random"             # 'random', 'manual', or 'leaderboard'; hydrated on connect
        self._last_seating_signature: tuple[str, ...] | None = None
        self.standings_message = None
        self._standings_post_lock = asyncio.Lock()
        self.round_messages: dict[int, "discord.Message"] = {}
        self.grace_task = None
        self.grace_round: int | None = None
        self.champion_announced = False
        self.champion_announcement_message = None
        self.champion_discord_ids: set[str] = set()
        self.championship_task: asyncio.Task | None = None
        self._end_watchdog_task: asyncio.Task | None = None
        self.sio = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)
        self.sio.on("connect", self._on_connect)
        self.sio.on("disconnect", self._on_disconnect)
        self.sio.on("sessionUsers", self._on_session_users)
        self.sio.on("sessionSpectators", self._on_session_spectators)
        self.sio.on("updateUser", self._on_update_user)
        self.sio.on("setReady", self._on_set_ready)
        self.sio.on("endDraft", self._on_end_draft)
        self.sio.on("draftLog", self._on_draft_log)

    @property
    def _connect_user_id(self) -> str:
        return f"{_BOT_USER_NAME}-{self.session_id}"

    @property
    def _connect_url(self) -> str:
        return (
            f"{settings.draftmancer_ws_url}/?"
            f"userID={self._connect_user_id}&sessionID={self.session_id}&userName={_BOT_USER_NAME}"
        )

    async def connect(self) -> bool:
        delay = _BACKOFF_BASE_S
        for attempt in range(1, _BACKOFF_MAX_RETRIES + 1):
            try:
                await self.sio.connect(self._connect_url, transports=["websocket"], wait_timeout=10)
                return True
            except (socketio.exceptions.ConnectionError, OSError) as e:
                if attempt >= _BACKOFF_MAX_RETRIES:
                    log.error(
                        f"[LIFECYCLE] connect.gave_up event={self.event_id} attempts={attempt} err={e!s}"
                    )
                    await bot_log_mod.get(self.bot).post(
                        f"Draftmancer connect gave up for event `{self.event_id}` after {attempt} attempts.",
                        fingerprint=f"connect_gave_up:{self.event_id}",
                        tag="LIFECYCLE",
                    )
                    return False
                wait = min(delay + random.uniform(0, delay * 0.25), _BACKOFF_MAX_S)
                log.warning(
                    f"[LIFECYCLE] connect.retry event={self.event_id} attempt={attempt} "
                    f"wait_s={wait:.1f} err={e!s}"
                )
                await asyncio.sleep(wait)
                delay = min(delay * 2, _BACKOFF_MAX_S)
        return False

    async def disconnect_safely(self) -> None:
        log.info(
            f"[LIFECYCLE] disconnect_safely event={self.event_id} "
            f"sio_connected={self.sio.connected} drafting={self.drafting} "
            f"complete={self.draft_complete} finalized={self.finalized}"
        )
        self._closed = True
        self._cancel_end_watchdog()
        try:
            if self.sio.connected:
                await self.sio.disconnect()
        except Exception:
            log.warning(f"[LIFECYCLE] disconnect_safely.error event={self.event_id}", exc_info=True)
        removed = ACTIVE_POD_MANAGERS.pop(self.event_id, None) is not None
        log.info(
            f"[LIFECYCLE] disconnect_safely.done event={self.event_id} "
            f"removed_from_registry={removed} registry_size={len(ACTIVE_POD_MANAGERS)}"
        )

    async def _on_connect(self) -> None:
        log.info(f"[LIFECYCLE] socket_connect event={self.event_id} sid={self.session_id}")
        await self._mark_socket_status("connected")

    async def _on_disconnect(self) -> None:
        in_flight = self.drafting or (self.draft_complete and not self.finalized)
        was_closed_intentionally = self._closed
        self._closed = True
        decision = "keep" if in_flight else "drop"
        log.warning(
            f"[LIFECYCLE] socket_disconnect event={self.event_id} sid={self.session_id} "
            f"closed_intentionally={was_closed_intentionally} drafting={self.drafting} "
            f"complete={self.draft_complete} finalized={self.finalized} "
            f"decision={decision} registry_size={len(ACTIVE_POD_MANAGERS)}"
        )
        if in_flight:
            if not was_closed_intentionally:
                await bot_log_mod.get(self.bot).post(
                    f"Socket dropped mid-flight for event `{self.event_id}` "
                    f"(drafting={self.drafting}, complete={self.draft_complete}).",
                    fingerprint=f"socket_drop_in_flight:{self.event_id}",
                    tag="LIFECYCLE",
                )
            return
        removed = ACTIVE_POD_MANAGERS.pop(self.event_id, None) is not None
        log.info(
            f"[LIFECYCLE] socket_disconnect.evict event={self.event_id} "
            f"removed={removed} registry_size={len(ACTIVE_POD_MANAGERS)}"
        )

    async def _on_session_users(self, users) -> None:
        self.session_users = list(users) if isinstance(users, list) else []
        slim = [{k: v for k, v in u.items() if k != "collection"} for u in self.session_users]
        log.info(f"draftmancer sessionUsers for {self.session_id}: {slim}")
        if self.draft_complete:
            return
        # Any session change clears the notready banner; lobby reverts to its normal state
        self.last_decliner_name = None
        self.last_cancel_reason = None
        self.last_ready_summary = None
        if self.bot_user_id is None:
            for u in self.session_users:
                if u.get("userName") == _BOT_USER_NAME:
                    self.bot_user_id = u.get("userID")
                    log.info(f"found bot userID={self.bot_user_id} for {self.session_id}")
                    if not self.owner_claimed:
                        asyncio.create_task(self._claim_ownership_and_apply_settings())
                    break

        await self._refresh_lobby_status()

        self._refresh_mock_lobby()

        self._sync_leaderboard_seeding()

        if self.ready_check_active:
            present = {u.get("userID") for u in self.player_session_users()}
            if not present <= self.expected_user_ids:
                await self._invalidate_ready_check("Player list changed")
            else:
                await self._maybe_complete_ready_check()

    async def _on_session_spectators(self, spectators) -> None:
        self.session_spectators = list(spectators) if isinstance(spectators, list) else []
        self._recompute_spectator_state()
        log.info(f"draftmancer sessionSpectators for {self.session_id}: {self.spectator_names}")
        if self.draft_complete:
            return
        await self._refresh_lobby_status()

    def _recompute_spectator_state(self) -> None:
        rows = self.session_spectators
        self.spectator_user_ids = {s.get("userID") for s in rows if s.get("userID")}
        self.spectator_names = [s.get("userName") for s in rows if s.get("userName")]
        self.spectator_targets = [
            (s.get("userID"), s.get("userName")) for s in rows
            if s.get("userID") and s.get("userName") != _BOT_USER_NAME
        ]

    async def _on_update_user(self, payload) -> None:
        if not isinstance(payload, dict):
            return
        user_id = payload.get("userID")
        updates = payload.get("updatedProperties") or {}
        if not user_id or not updates:
            return
        renamed_roster = self._apply_user_update(self.session_users, user_id, updates)
        renamed_spectator = self._apply_user_update(self.session_spectators, user_id, updates)
        if renamed_spectator:
            self._recompute_spectator_state()
        if "userName" in updates and (renamed_roster or renamed_spectator):
            log.info(f"draftmancer updateUser rename for {self.session_id}: {user_id} → {updates['userName']}")
            if not self.draft_complete:
                await self.refresh_lobby_now()
                self._refresh_mock_lobby()
                if renamed_roster:
                    self._sync_leaderboard_seeding()

    @staticmethod
    def _apply_user_update(rows: list[dict], user_id: str, updates: dict) -> bool:
        for u in rows:
            if u.get("userID") == user_id:
                u.update(updates)
                return True
        return False

    async def _claim_ownership_and_apply_settings(self) -> None:
        if self.bot_user_id is None or self.owner_claimed:
            return
        self.owner_claimed = True
        try:
            await self.sio.emit("setSessionOwner", self.bot_user_id)
            await asyncio.sleep(0.3)
            await self._emit_session_settings()
            await self.apply_seating_mode()
            await self._enable_spectators_and_share_link()
            log.info(f"[LIFECYCLE] ownership_applied event={self.event_id} bot_user={self.bot_user_id}")
        except Exception:
            log.exception(f"[LIFECYCLE] ownership_failed event={self.event_id}")
            await bot_log_mod.get(self.bot).post(
                f"Ownership/settings flow failed for event `{self.event_id}` — draft cannot be started.",
                fingerprint=f"ownership_failed:{self.event_id}",
                tag="LIFECYCLE",
            )

    async def _emit_session_settings(self) -> None:
        await self._emit_format()
        await self.sio.emit("setOwnerIsPlayer", False)
        await self.sio.emit("setMaxPlayers", settings.pod_draft_max_players)
        await self.sio.emit("setPickTimer", settings.pod_draft_pick_timer)
        await self.sio.emit("setBots", settings.pod_draft_bots)
        await self.sio.emit("setColorBalance", False)
        await self.sio.emit("setPersonalLogs", True)
        await self.sio.emit("setDraftLogRecipients", self._draft_log_recipients)
        log.info(
            f"[LIFECYCLE] session_settings_applied event={self.event_id} set={self.set_code} "
            f"max_players={settings.pod_draft_max_players} pick_timer={settings.pod_draft_pick_timer} "
            f"bots={settings.pod_draft_bots} log_recipients={self._draft_log_recipients}"
        )

    @property
    def _draft_log_recipients(self) -> str:
        """Mock drafts play no rounds, so picks never need hiding — open every player's draft log the
        moment the draft ends. Tournament pods stay 'delayed' so the table can't be scouted mid-event."""
        return "everyone" if self.kind == "mock" else "delayed"

    async def _enable_spectators_and_share_link(self) -> None:
        result = await self._emit_with_ack("setAllowSpectators", True)
        spectate_key = result.get("spectateKey") if isinstance(result, dict) else None
        if not spectate_key:
            error_text = _ack_error_text(result)
            log.warning(f"[LIFECYCLE] spectators.enable_failed event={self.event_id} error={error_text!r}")
            return
        self.spectate_url = f"{self.draftmancer_url}&spectate={spectate_key}"
        if self.reconnect:
            return
        await self._refresh_lobby_status()
        log.info(f"[LIFECYCLE] spectators.enabled event={self.event_id}")
        notify_seeding_repost(self.bot, self.event_id)

    async def _emit_format(self) -> str | None:
        """
        Point the session at the current `set_code`: a registered cube → importCube, else a  plain set → setRestriction.
        Returns an error string on cube-import failure, else None.
        """
        cube_id = pod_format.cube_id_for(self.set_code)
        if cube_id is None:
            await self.sio.emit("setRestriction", [self.set_code.lower()])
            return None
        err = await self._import_cube(cube_id)
        if err is not None:
            thread = await self._fetch_thread()
            if thread is not None:
                try:
                    await thread.send(f"⚠️ {err}")
                except Exception:
                    log.warning(f"[LIFECYCLE] import_cube.thread_post_error event={self.event_id}", exc_info=True)
        return err

    async def _import_cube(self, cube_id: str) -> str | None:
        """Load a CubeCobra cube into the session (owner-only). Ported from Amelas/DraftBot."""
        payload = {"service": "Cube Cobra", "cubeID": cube_id, "matchVersions": True}
        result = await self._emit_with_ack("importCube", payload, timeout_s=30.0)
        error_text = _ack_error_text(result)
        if error_text is not None:
            log.warning(
                f"[LIFECYCLE] import_cube.failed event={self.event_id} cube={cube_id} error={error_text!r}"
            )
            await bot_log_mod.get(self.bot).post(
                f"importCube failed for event `{self.event_id}` (cube `{cube_id}`): {error_text}",
                fingerprint=f"import_cube_failed:{self.event_id}",
                tag="LIFECYCLE",
            )
            return f"Couldn't load cube `{cube_id}` in Draftmancer: {error_text}"
        log.info(f"[LIFECYCLE] import_cube.ok event={self.event_id} cube={cube_id}")
        return None

    async def apply_format(self, code: str) -> str | None:
        """Switch this pod's format to `code` (a set code or a registered cube code). Pre-draft only.
        Persists set_code, re-emits to a live session, and refreshes the lobby card."""
        if self.drafting or self.draft_complete:
            return pod_format.FORMAT_LOCKED_MSG
        if not await asyncio.to_thread(_persist_format, self.event_id, code):
            return pod_format.FORMAT_LOCKED_MSG
        self.set_code = code
        if self.sio.connected and self.owner_claimed:
            err = await self._emit_format()
            if err is not None:
                return err
        await self.refresh_lobby_now()
        return None

    async def _mark_socket_status(self, status: str) -> None:
        with SessionLocal() as session:
            event = session.get(PodDraftEvent, self.event_id)
            if event is not None:
                event.socket_status = status
                session.commit()

    async def initiate_ready_check(
        self, thread, initiated_by: str | None = None, *, min_players: int | None = None,
    ) -> str | None:
        """Start a Draftmancer ready check; returns an error string on failure, None on success.
        `min_players` overrides the floor — the lobby button uses the default, the manual /pod-ready
        command passes a lower one so a small pod can be readied."""
        if not self.sio.connected:
            return "Draftmancer session is not connected."
        if self.drafting or self.draft_complete:
            return "The draft has already started."
        if self.ready_check_active:
            return "Ready check already in progress."
        non_bot = self.player_session_users()
        if not non_bot:
            return "Nobody in the Draftmancer lobby yet."
        min_players = min_players if min_players is not None else settings.pod_draft_min_ready_players
        if len(non_bot) < min_players:
            return (
                f"Ready check is only available with {min_players} or more players. "
                f"Currently {len(non_bot)} in the Draftmancer lobby.\n"
                "Wait for more players to join, or run `/pod-start` to start the draft now, "
                "skipping the ready check."
            )
        self.expected_user_ids = {u.get("userID") for u in non_bot}
        self.ready_users = set()
        self.ready_check_active = True
        self._suppress_lobby_full_prompt()
        self._ready_check_started_at = asyncio.get_running_loop().time()
        self.initiated_by = initiated_by
        prior_decliner = self.last_decliner_name
        prior_cancel = self.last_cancel_reason
        prior_summary = self.last_ready_summary
        self.last_decliner_name = None
        self.last_cancel_reason = None
        self.last_ready_summary = None
        log.info(
            f"[READY] start event={self.event_id} expected={len(self.expected_user_ids)} "
            f"timeout_s={_READY_TIMEOUT_S}"
        )
        try:
            await self.sio.emit("readyCheck")
        except Exception:
            self.ready_check_active = False
            log.exception(f"[READY] emit_failed event={self.event_id}")
            return "Could not start ready check — see logs."
        self._ready_timeout_task = asyncio.create_task(self._ready_timeout())

        non_bot_names = [u.get("userName") for u in non_bot if u.get("userName")]
        classified = await self._classify_users(non_bot_names) if non_bot_names else []

        prior_progress = self.ready_check_progress_message
        self.ready_check_progress_message = None
        if prior_progress is not None:
            superseded_embed = render_ready_check_progress(
                title=self.event_name,
                in_session=classified,
                state="notready",
                draftmancer_url=self.draftmancer_url,
                decliner_name=prior_decliner,
                cancel_reason=prior_cancel,
                superseded=True,
                ready_count=prior_summary[0] if prior_summary else None,
                total_count=prior_summary[1] if prior_summary else None,
                **self._settings_labels(),
            )
            try:
                await prior_progress.edit(embed=superseded_embed, view=None)
            except Exception:
                log.warning("could not lock prior ready-check progress card", exc_info=True)

        progress_embed = render_ready_check_progress(
            title=self.event_name,
            in_session=classified,
            state="ready",
            draftmancer_url=self.draftmancer_url,
            ready_arena_names=set(),
            initiated_by=self.initiated_by,
            **self._settings_labels(),
        )
        try:
            self.ready_check_progress_message = await thread.send(
                embed=progress_embed,
                view=LobbyReadyButtonView(
                    draftmancer_url=self.draftmancer_url, ready_disabled=True, show_force_start=True,
                    spectate_url=self.spectate_url,
                ),
            )
        except Exception:
            log.warning("could not post ready-check progress card", exc_info=True)

        await self._refresh_lobby_status()
        return None

    async def _classify_users(self, names: list[str]) -> list[tuple[str, str | None]]:
        """Classify Draftmancer usernames against linked players, falling back to guild members
        whose Discord display_name (or username) matches the Draftmancer name's prefix.
        For guild-member matches without a Player row, lazily create one so the participant is
        recorded toward the pod leaderboard at draft completion."""
        classified = await asyncio.to_thread(_classify_names_sync, names)
        if not any(dn is None for _, dn in classified):
            return classified
        thread = await self._fetch_thread()
        guild = thread.guild if thread is not None else None
        if guild is None:
            return classified
        unresolved: list[tuple[str, discord.Member]] = []
        out: list[tuple[str, str | None]] = []
        for arena, dn in classified:
            if dn is not None:
                out.append((arena, dn))
                continue
            member = _find_guild_member_for_arena(guild, arena)
            if member is None:
                out.append((arena, None))
                continue
            unresolved.append((arena, member))
            out.append((arena, member.display_name))
        if unresolved:
            await asyncio.to_thread(_ensure_players_for_members_sync, unresolved)
        return out

    def player_session_users(self) -> list[dict]:
        """Session users that count as players: excludes the bot and anyone spectating."""
        return [
            u for u in self.session_users
            if u.get("userName") and u.get("userName") != _BOT_USER_NAME
            and u.get("userID") not in self.spectator_user_ids
        ]

    def non_bot_session_names(self) -> list[str]:
        return [u.get("userName") for u in self.player_session_users()]

    async def classified_session_users(self) -> list[tuple[str, str | None]]:
        """Current non-bot session users as (arena_name, linked_display_name_or_None)."""
        names = self.non_bot_session_names()
        return await self._classify_users(names) if names else []

    async def refresh_lobby_now(self) -> None:
        """Re-run classification and edit the lobby card. External hook for /pod-link-arena so the
        lobby reflects the new link immediately. Once the draft completes the roster is frozen:
        _refresh_lobby_status renders the endDraft snapshot, not whoever is in the session now."""
        await self._refresh_lobby_status()

    async def _resolve_rsvp_mentions(self, guild: discord.Guild | None) -> dict[int, str]:
        """Resolve `<@id>` mentions in rsvps_yes/rsvps_maybe to guild member display names.
        Used by render_lobby_embed for dedup against in-session display names. Plain-text
        rsvps (when sesh's `Display Usernames as Plain Text` is on) don't need resolution."""
        if guild is None:
            return {}
        ids: set[int] = set()
        for rsvp in (*self.rsvps_yes, *self.rsvps_maybe):
            m = re.match(r"^<@!?(\d+)>$", rsvp.strip())
            if m:
                ids.add(int(m.group(1)))
        out: dict[int, str] = {}
        for mid in ids:
            member = guild.get_member(mid)
            if member is None:
                try:
                    member = await guild.fetch_member(mid)
                except discord.HTTPException:
                    continue
            out[mid] = member.display_name
        return out

    def _settings_labels(self) -> dict[str, str]:
        """Format / Pairings / Seats labels for the sticky lobby + progress-card footer."""
        return {
            "format_label": pod_format.format_display(self.set_code),
            "pairing_label": pairing_label(self.pairing_mode),
            "seating_label": seating_mode_label(self.seating_mode),
        }

    async def _refresh_lobby_status(self) -> None:
        """Re-render the lobby card from the live session. Roster classification and the card edit run
        together under _lobby_post_lock so concurrent sessionUsers / sessionSpectators broadcasts can't
        clobber each other — without it, a handler that captured a pre-kick roster before its await
        would edit last and resurrect the removed player."""
        thread = await self._fetch_thread()
        if thread is None:
            return
        async with self._lobby_post_lock:
            if self.draft_complete and self.tournament_roster:
                names = list(self.tournament_roster)
            else:
                names = self.non_bot_session_names()
            classified = await self._classify_users(names) if names else []
            state = self._compute_state(classified)
            ready_arena_names: set[str] | None = None
            if state == "ready":
                ready_arena_names = {
                    u.get("userName") for u in self.session_users
                    if u.get("userID") in self.ready_users and u.get("userName")
                }
            embed = render_lobby_embed(
                title=self.event_name,
                rsvps_yes=self.rsvps_yes,
                rsvps_maybe=self.rsvps_maybe,
                in_session=classified,
                state=state,
                draftmancer_url=self.draftmancer_url,
                decliner_name=self.last_decliner_name,
                cancel_reason=self.last_cancel_reason,
                initiated_by=self.initiated_by,
                display_name_by_mention_id=await self._resolve_rsvp_mentions(thread.guild),
                spectators=self.spectator_names,
                **self._settings_labels(),
            )
            self._maybe_schedule_lobby_full_prompt(classified)
            view = (
                None if state in ("drafting", "complete")
                else LobbyReadyButtonView(
                    draftmancer_url=self.draftmancer_url,
                    ready_disabled=(state == "ready"),
                    show_force_start=(state == "unlinked"),
                    spectate_url=self.spectate_url,
                )
            )
            suppress_empty_reconnect = self.reconnect and not classified
            if (
                self.lobby_status_message is None and self.reconnect and classified
                and not self._lobby_card_adopt_attempted
            ):
                self._lobby_card_adopt_attempted = True
                try:
                    await thread.send(MSG_BOT_RECONNECTED)
                except Exception:
                    log.warning(f"could not post reconnect notice for {self.session_id}", exc_info=True)
                adopted = await _find_pinned_lobby_card(thread, self.bot.user, self.event_name)
                if adopted is not None:
                    self.lobby_status_message = adopted
                    log.info(f"[LIFECYCLE] rehydrate_lobby.adopted_card event={self.event_id} msg={adopted.id}")
            if self.lobby_status_message is None:
                if not suppress_empty_reconnect:
                    try:
                        self.lobby_status_message = await thread.send(embed=embed, view=view)
                        try:
                            await self.lobby_status_message.pin()
                        except Exception:
                            log.warning(f"could not pin lobby status for {self.session_id}", exc_info=True)
                    except Exception:
                        log.warning(f"could not post lobby status for {self.session_id}", exc_info=True)
            else:
                try:
                    await self.lobby_status_message.edit(embed=embed, view=view)
                except Exception:
                    log.warning(f"could not edit lobby status for {self.session_id}", exc_info=True)

        if self.ready_check_progress_message is not None:
            progress_embed = render_ready_check_progress(
                title=self.event_name,
                in_session=classified,
                state=state,
                draftmancer_url=self.draftmancer_url,
                ready_arena_names=ready_arena_names,
                decliner_name=self.last_decliner_name,
                cancel_reason=self.last_cancel_reason,
                initiated_by=self.initiated_by,
                ready_count=self.last_ready_summary[0] if self.last_ready_summary else None,
                total_count=self.last_ready_summary[1] if self.last_ready_summary else None,
                **self._settings_labels(),
            )
            if state in ("drafting", "complete", "notready"):
                progress_view = None
            else:
                progress_view = LobbyReadyButtonView(
                    draftmancer_url=self.draftmancer_url,
                    ready_disabled=(state == "ready"),
                    show_force_start=(state == "ready"),
                    spectate_url=self.spectate_url,
                )
            try:
                await self.ready_check_progress_message.edit(embed=progress_embed, view=progress_view)
            except Exception:
                log.warning("could not edit ready-check progress card", exc_info=True)

        await self._maybe_post_voice_link(classified, thread)

    async def _maybe_post_voice_link(self, classified: list[tuple[str, str | None]], thread) -> None:
        """Once half the table has gathered in the Draftmancer lobby, drop a one-time link to the pod
        voice channel so players hop in to chat while the rest fill in. Resolved by name from the guild's
        cached channels, so it costs no extra Discord request."""
        if self._voice_link_posted or self.kind == "mock" or self.drafting or self.draft_complete:
            return
        if len(classified) < _LOBBY_HALF_THRESHOLD:
            return
        channel = discord.utils.get(thread.guild.voice_channels, name=settings.pod_draft_voice_channel_name)
        self._voice_link_posted = True
        if channel is None:
            log.info(
                f"[LOBBY] voice_link_skip — no '{settings.pod_draft_voice_channel_name}' voice channel "
                f"event={self.event_id}"
            )
            return
        try:
            await thread.send(channel.jump_url)
        except discord.HTTPException:
            self._voice_link_posted = False
            log.warning(f"[LOBBY] voice_link_send_failed event={self.event_id}", exc_info=True)

    def _compute_state(self, classified: list[tuple[str, str | None]]) -> str:
        if self.draft_complete:
            return "complete"
        if self.drafting:
            return "drafting"
        if self.last_decliner_name or self.last_cancel_reason:
            return "notready"
        if self.ready_check_active:
            return "ready"
        if not classified:
            return "empty"
        if any(dn is None for _, dn in classified):
            return "unlinked"
        return "linked"

    async def _on_end_draft(self, *_) -> None:
        log.info(f"[DRAFT] end_received event={self.event_id} session_users={len(self.session_users)}")
        self.drafting = False
        self.draft_complete = True
        self._cancel_end_watchdog()
        await self._mark_socket_status("draft_done")
        self.tournament_roster = self._snapshot_tournament_roster()
        log.info(
            f"[DRAFT] roster_snapshot event={self.event_id} roster_size={len(self.tournament_roster)}"
        )
        await self.refresh_lobby_now()
        payload = next(iter(self.draft_logs.values()), None)
        if payload is not None:
            self.mpt_task = asyncio.create_task(self._submit_logs_to_magicprotools(payload))
        else:
            log.warning(f"[DRAFT] end_no_payload event={self.event_id}")
        if self.kind == "mock":
            asyncio.create_task(self._finalize_mock())
        else:
            asyncio.create_task(start_tournament(self))

    async def _finalize_mock(self) -> None:
        """A mock draft ends at the draft itself — no rounds, no champion. Stamp the event finished so
        the site renders the table + logs, post the breakdown link, then drop the bot from the
        Draftmancer session so it's freed for deckbuilding. Logs are already open to everyone."""
        self.finalized = True
        await asyncio.to_thread(self._mark_mock_finalized)
        log.info(f"[DRAFT] mock_finalized event={self.event_id}")
        thread = await self._fetch_thread()
        if thread is not None:
            event_url = f"{settings.public_site_url.rstrip('/')}/pods/{slugify(self.event_name)}"
            try:
                await thread.send(MSG_MOCK_COMPLETE.format(
                    event_name=self.event_name, url=event_url, manat=emojis.get("manat"),
                ))
            except Exception:
                log.warning(f"[DRAFT] mock_finalize.thread_post_error event={self.event_id}", exc_info=True)
        if self.mpt_task is not None:
            try:
                await self.mpt_task
            except Exception:
                log.warning(f"[DRAFT] mock_finalize.mpt_await_error event={self.event_id}", exc_info=True)
        await self.disconnect_safely()

    def _mark_mock_finalized(self) -> None:
        with SessionLocal() as session:
            finalize_mock_event(session, self.event_id)
            session.commit()

    def _refresh_mock_lobby(self) -> None:
        """Mock-only reaction to a lobby change (join, leave, or rename): add recognized members to the
        thread and update the live player count on the anchor message. No-op for tournament pods."""
        if self.kind != "mock" or self.draft_complete:
            return
        asyncio.create_task(self._sync_thread_membership())
        asyncio.create_task(self._update_mock_lobby_counter())

    async def _update_mock_lobby_counter(self) -> None:
        if self.mock_lobby_message is None:
            return
        count = len(self.player_session_users())
        counter = MSG_MOCK_LOBBY_COUNTER.format(count=count) if count >= 1 else ""
        content = MSG_MOCK_LOBBY_OPEN.format(
            draftmancer_emoji=emojis.get("draftmancer"),
            event_name=self.event_name,
            url=self.draftmancer_url,
            counter=counter,
        )
        try:
            await self.mock_lobby_message.edit(content=content)
        except discord.HTTPException:
            log.info(f"[MOCK] counter_edit_failed event={self.event_id}", exc_info=True)

    async def _sync_thread_membership(self) -> None:
        """Add Draftmancer joiners we recognize as guild members to the mock-draft thread, so the
        people drafting see the thread without being manually invited. Idempotent per discord id."""
        thread = await self._fetch_thread()
        guild = thread.guild if thread is not None else None
        if guild is None:
            return
        names = self.non_bot_session_names()
        if not names:
            return
        discord_id_by_name = await asyncio.to_thread(_discord_ids_for_names_sync, names)
        for name in names:
            discord_id = discord_id_by_name.get(name)
            member = guild.get_member(int(discord_id)) if discord_id else _find_guild_member_for_arena(guild, name)
            if member is None or str(member.id) in self._thread_added_ids:
                continue
            self._thread_added_ids.add(str(member.id))
            try:
                await thread.add_user(member)
                log.info(f"[MOCK] thread_add event={self.event_id} member={member.display_name}")
            except discord.HTTPException:
                log.info(f"[MOCK] thread_add_failed event={self.event_id} member={member.display_name}", exc_info=True)

    def _snapshot_tournament_roster(self) -> list[str]:
        """The locked drafter list, frozen at endDraft. Prefers the draft log's seated users — immune
        to players closing their tab at draft end or spectators joining after — and falls back to
        whoever is in the session right now."""
        payload = next(iter(self.draft_logs.values()), None)
        users = payload.get("users") if isinstance(payload, dict) else None
        if isinstance(users, dict):
            seated = [u.get("userName") for u in users.values() if isinstance(u, dict) and u.get("userName")]
            if seated:
                return seated
        return self.non_bot_session_names()

    async def _on_draft_log(self, log_payload) -> None:
        if not isinstance(log_payload, dict):
            return
        users = log_payload.get("users") or {}
        if isinstance(users, dict):
            for user in users.values():
                name = user.get("userName") if isinstance(user, dict) else None
                if name:
                    self.draft_logs[name] = log_payload
                    break
        log.info(f"[DRAFT] log_stored event={self.event_id} total={len(self.draft_logs)}")
        await asyncio.to_thread(self._persist_draft_log_gz, log_payload)

    async def _submit_logs_to_magicprotools(self, log_payload: dict) -> None:
        """For each Draftmancer seat in the log, submit to MagicProTools and stash the URL on the
        matching pod_draft_participants row. Per-seat failures log + continue."""
        if settings.mpt_api_key is None:
            log.warning(f"[DRAFT] mpt_skipped event={self.event_id} reason=api_key_unset")
            return
        users = log_payload.get("users") or {}
        if not isinstance(users, dict):
            return
        seats = [
            (uid, ud) for uid, ud in users.items()
            if isinstance(ud, dict)
            and ud.get("userName") and ud.get("userName") != _BOT_USER_NAME
            and not ud.get("isBot")
        ]
        log.info(f"[DRAFT] mpt_submit.start event={self.event_id} seats={len(seats)}")
        stored = 0
        for user_id, user_data in seats:
            user_name = user_data["userName"]
            try:
                url = await submit_to_magicprotools(user_id, log_payload)
            except Exception:
                log.warning(
                    f"[DRAFT] mpt_submit.seat_error event={self.event_id} seat={user_name!r}",
                    exc_info=True,
                )
                continue
            if not url:
                continue
            try:
                wrote = await asyncio.to_thread(self._store_draft_log_url, user_name, url)
            except Exception:
                log.warning(
                    f"[DRAFT] mpt_submit.store_error event={self.event_id} seat={user_name!r}",
                    exc_info=True,
                )
                continue
            if wrote:
                stored += 1
                log.info(f"[DRAFT] mpt_submit.seat_stored event={self.event_id} seat={user_name!r}")
        log.info(f"[DRAFT] mpt_submit.done event={self.event_id} stored={stored}/{len(seats)}")
        if seats and stored == 0:
            await bot_log_mod.get(self.bot).post(
                f"MPT submit produced 0/{len(seats)} stored URLs for event `{self.event_id}`.",
                fingerprint=f"mpt_zero_stored:{self.event_id}",
                tag="DRAFT",
            )

    def _store_draft_log_url(self, draftmancer_name: str, url: str) -> bool:
        try:
            with SessionLocal() as session:
                rows = session.execute(
                    select(PodDraftParticipant)
                    .where(
                        PodDraftParticipant.event_id == self.event_id,
                        func.lower(PodDraftParticipant.draftmancer_name) == draftmancer_name.lower(),
                    )
                ).scalars().all()
                if not rows:
                    log.warning(f"[DRAFT] mpt_submit.no_row event={self.event_id} seat={draftmancer_name!r}")
                    return False
                for row in rows:
                    row.draft_log_url = url
                session.commit()
                return True
        except Exception:
            log.warning(f"magicprotools: store url failed for {draftmancer_name}", exc_info=True)
            return False

    def _persist_draft_log_gz(self, log_payload: dict) -> None:
        try:
            compact = build_compact(log_payload)
            blob = gzip.compress(json.dumps(compact, separators=(",", ":")).encode("utf-8"))
        except Exception:
            log.warning(f"[DRAFT] persist.compact_error event={self.event_id}", exc_info=True)
            asyncio.run_coroutine_threadsafe(
                bot_log_mod.get(self.bot).post(
                    f"Draft log compact/gzip failed for event `{self.event_id}` — data not persisted.",
                    fingerprint=f"persist_compact_error:{self.event_id}",
                    tag="DRAFT",
                ),
                self.bot.loop,
            )
            return
        try:
            with SessionLocal() as session:
                event = session.execute(
                    select(PodDraftEvent).where(PodDraftEvent.id == self.event_id)
                ).scalar_one_or_none()
                if event is None:
                    log.warning(f"[DRAFT] persist.event_missing event={self.event_id}")
                    return
                event.draft_log_gz = blob
                event.draft_log = compact
                apply_seat_indexes(session, self.event_id, compact.get("seats") or [])
                session.commit()
                log.info(f"[DRAFT] persist.done event={self.event_id} bytes={len(blob)}")
        except Exception:
            log.warning(f"[DRAFT] persist.db_error event={self.event_id}", exc_info=True)
            asyncio.run_coroutine_threadsafe(
                bot_log_mod.get(self.bot).post(
                    f"Draft log DB persist failed for event `{self.event_id}` — data not saved.",
                    fingerprint=f"persist_db_error:{self.event_id}",
                    tag="DRAFT",
                ),
                self.bot.loop,
            )

    async def _fetch_thread(self):
        try:
            return await self.bot.fetch_channel(self.thread_id)
        except Exception:
            log.warning(f"could not fetch thread {self.thread_id}", exc_info=True)
            return None

    def persist_seat_indexes_from_log(self) -> bool:
        """Write seat_index from the in-memory draft log to participants so round-1 pairing and every
        later re-render read the same seating. Idempotent with _persist_draft_log_gz.
        Returns False when no draft log is in memory yet."""
        payload = next(iter(self.draft_logs.values()), None)
        users = payload.get("users") if isinstance(payload, dict) else None
        if not isinstance(users, dict):
            return False
        seats = [u.get("userName") for u in users.values() if isinstance(u, dict)]
        if not any(seats):
            return False
        with SessionLocal() as session:
            apply_seat_indexes(session, self.event_id, seats)
            session.commit()
        return True

    async def _on_set_ready(self, user_id, ready_state) -> None:
        if not self.ready_check_active:
            return
        ready = _is_ready_state(ready_state)
        if ready:
            self.ready_users.add(user_id)
        else:
            self.ready_users.discard(user_id)
            elapsed = asyncio.get_running_loop().time() - self._ready_check_started_at
            if elapsed < _READY_DEBOUNCE_S:
                log.info(
                    f"[READY] residual_notready_ignored event={self.event_id} user={user_id} "
                    f"elapsed_s={elapsed:.2f}"
                )
                return
            decliner_name = next(
                (u.get("userName") for u in self.session_users if u.get("userID") == user_id),
                None,
            )
            await self._invalidate_ready_check("declined", decliner_name=decliner_name)
            return
        await self.refresh_lobby_now()
        await self._maybe_complete_ready_check()

    async def _maybe_complete_ready_check(self) -> None:
        """Complete only when every player present at the check's start is still in the lobby and
        ready. ready_users is pruned to the current lobby first, so a player who readied then left
        can't satisfy the count — the check holds until they return, or the timeout cancels it."""
        if not self.ready_check_active:
            return
        present = {u.get("userID") for u in self.player_session_users()}
        self.ready_users &= present
        if self.expected_user_ids <= present and self.ready_users >= self.expected_user_ids:
            await self._complete_ready_check()

    async def _complete_ready_check(self) -> None:
        if not self.ready_check_active:
            return
        log.info(f"[READY] complete event={self.event_id} ready_count={len(self.ready_users)}")
        self.ready_check_active = False
        if self._ready_timeout_task is not None:
            self._ready_timeout_task.cancel()
        await self._start_draft()

    async def force_start(self) -> str | None:
        """Bypass the ready-check and emit startDraft directly. Returns an error string on failure, None on success."""
        if not self.sio.connected:
            return "Draftmancer session is not connected."
        if self.draft_complete:
            return "Draft is already complete."
        if self.drafting:
            return "Draft is already in progress."
        if self._ready_timeout_task is not None:
            self._ready_timeout_task.cancel()
        self.ready_check_active = False
        self.ready_users = set()
        self.last_decliner_name = None
        self.last_cancel_reason = None
        log.info(f"[READY] force_start event={self.event_id} ready_check_bypassed=True")
        await self._start_draft()
        return None

    async def _start_draft(self) -> None:
        await self._reapply_seating_if_set()
        result = await self._emit_with_ack("startDraft")
        log.info(f"[DRAFT] start_ack event={self.event_id} ack={result!r}")
        error_text = _ack_error_text(result)
        if error_text is not None:
            log.warning(f"[DRAFT] start_failed event={self.event_id} error={error_text!r}")
            await bot_log_mod.get(self.bot).post(
                f"startDraft failed for event `{self.event_id}`: {error_text}",
                fingerprint=f"start_draft_failed:{self.event_id}",
                tag="DRAFT",
            )
            thread = await self._fetch_thread()
            if thread is not None:
                try:
                    await thread.send(
                        f"⚠️ Could not start the draft: {error_text}\n"
                        f"Use `/pod-takeover` to take control of the Draftmancer session manually."
                    )
                except Exception:
                    log.warning("[DRAFT] start_failed.thread_post_error", exc_info=True)
            return
        self.drafting = True
        log.info(f"[DRAFT] started event={self.event_id} session_users={len(self.session_users)}")
        self._schedule_end_watchdog()
        await self._retire_lobby_full_prompt()
        await asyncio.to_thread(self._seed_participants_at_draft_start)
        await self.refresh_lobby_now()
        thread = await self._fetch_thread()
        if thread is not None:
            try:
                await thread.send(content="**🎉 Draft started!**")
            except Exception:
                log.warning("[DRAFT] started.thread_post_error", exc_info=True)

    def _seed_participants_at_draft_start(self) -> None:
        """Insert pod_draft_participants for every non-bot Draftmancer userName now that the draft
        has begun (lobby locked). Idempotent — start_tournament will re-call with the same roster
        as a safety net after endDraft."""
        roster = self.non_bot_session_names()
        if not roster:
            log.warning(f"[DRAFT] seed_participants.empty_roster event={self.event_id}")
            return
        try:
            with SessionLocal() as session:
                seed_event_participants(session, self.event_id, roster)
                session.commit()
            log.info(f"[DRAFT] seeded_participants event={self.event_id} count={len(roster)}")
        except Exception:
            log.warning(f"[DRAFT] seed_participants.error event={self.event_id}", exc_info=True)

    async def seating_lobby_order(self) -> list[tuple[str, str]]:
        """Current non-bot lobby users in Draftmancer order, as (userName, display_label)."""
        names = [u.get("userName") for u in self.player_session_users() if u.get("userID")]
        classified = await asyncio.to_thread(_classify_names_sync, names)
        return [(name, display or name) for name, display in classified]

    async def set_seating_order(self, ordered_user_names: list[str]) -> str | None:
        """Force the Draftmancer table order (owner-only, pre-draft). Returns an error string or None."""
        if not self.sio.connected:
            return "Draftmancer session is not connected."
        if self.drafting or self.draft_complete:
            return "Seating can't be changed once the draft has started."
        name_to_id = {
            u.get("userName"): u.get("userID")
            for u in self.player_session_users()
            if u.get("userID")
        }
        if set(ordered_user_names) != set(name_to_id):
            return "Lobby changed since the panel opened — reopen Settings and set the seating again."
        user_id_order = [name_to_id[name] for name in ordered_user_names]
        try:
            await self.sio.emit("setRandomizeSeatingOrder", False)
            await self.sio.emit("setSeating", user_id_order)
        except Exception:
            log.exception(f"[SEATING] emit_failed event={self.event_id}")
            return "Could not update the seating order."
        self.desired_seating = list(ordered_user_names)
        log.info(f"[SEATING] applied event={self.event_id} order={ordered_user_names}")
        return None

    def kick_targets(self) -> list[tuple[str, str]]:
        """(userID, label) for every removable session user — seated players plus spectators,
        spectators suffixed so the Settings kick select tells them apart."""
        players = [
            (u.get("userID"), u.get("userName")) for u in self.player_session_users()
            if u.get("userID")
        ]
        spectators = [(user_id, f"{name} (spectator)") for user_id, name in self.spectator_targets]
        return players + spectators

    async def kick_player(self, user_id: str) -> str | None:
        """Remove a user from the Draftmancer session (owner-only socket action; Draftmancer parks
        the removed user in a fresh session). Pre-draft only. Returns an error string or None."""
        if not self.sio.connected:
            return "Draftmancer session is not connected."
        if self.drafting or self.draft_complete:
            return "Players can't be removed once the draft has started."
        try:
            await self.sio.emit("removePlayer", user_id)
        except Exception:
            log.exception(f"[KICK] emit_failed event={self.event_id} user_id={user_id}")
            return "Could not remove the player."
        log.info(f"[KICK] removed event={self.event_id} user_id={user_id}")
        return None

    async def unrecognized_lobby_names(self) -> list[str]:
        """Draftmancer seat names in the live lobby with no linked player — the targets the Settings
        'Link Players' action offers an organizer to bind by hand."""
        names = self.non_bot_session_names()
        classified = await self._classify_users(names) if names else []
        return [arena for arena, dn in classified if dn is None]

    async def link_seat(self, member: discord.abc.User, arena_name: str) -> str | None:
        """Bind `member`'s Discord identity to the exact Draftmancer seat `arena_name`, then refresh
        the lobby so the seat resolves. Returns an error string on failure, None on success."""
        def _link() -> tuple[str | None, str | None]:
            with SessionLocal() as session:
                player_id, collision_id = attach_arena_alias(
                    session,
                    discord_id=str(member.id),
                    discord_username=member.name,
                    display_name=member.display_name,
                    avatar_hash=extract_avatar_hash(member),
                    arena_name=arena_name,
                )
                if collision_id is None:
                    session.commit()
                return player_id, collision_id

        _, collision_id = await asyncio.to_thread(_link)
        if collision_id is not None:
            return f"`{arena_name}` is already linked to another player."
        log.info(f"[LINK] seat_linked event={self.event_id} member={member} arena={arena_name!r}")
        await self.refresh_lobby_now()
        await refresh_round_pairing_messages(self)
        return None

    def _sync_leaderboard_seeding(self) -> None:
        """Re-apply leaderboard seating and refresh the posted seeding table after the player pool or a
        name changes. No-op unless the pod is leaderboard-seated. Fires from both the sessionUsers and
        the updateUser-rename paths so a name set after connect can't leave the seating one player behind."""
        if self.seating_mode != "leaderboard":
            return
        if self.owner_claimed:
            asyncio.create_task(self._apply_leaderboard_seating())
        notify_seeding_change(self.bot, self.event_id)

    @staticmethod
    def _lobby_pod_full(classified: list[tuple[str, str | None]]) -> bool:
        """A full, ready-checkable pod: a full pod's worth of players present and every one of them
        linked. Unlinked players can't draft and disable the Ready Check, so they don't count."""
        if any(display is None for _, display in classified):
            return False
        return len(classified) >= _LOBBY_FULL_THRESHOLD

    def _suppress_lobby_full_prompt(self) -> None:
        """Retire the auto-nudge for this lobby once a Ready Check has been initiated, so it can't fire
        later even if that check is declined and the lobby returns to idle, and delete its posted message
        so the stale Ready Check button can't be clicked."""
        self._lobby_full_prompted = True
        if self._lobby_full_prompt_task is not None:
            self._lobby_full_prompt_task.cancel()
            self._lobby_full_prompt_task = None
        if self._lobby_full_prompt_message is not None:
            asyncio.create_task(self._retire_lobby_full_prompt())

    async def _retire_lobby_full_prompt(self) -> None:
        """Delete the posted lobby-full nudge so its buttons can't outlive the lobby. Best-effort."""
        message = self._lobby_full_prompt_message
        self._lobby_full_prompt_message = None
        if message is None:
            return
        try:
            await message.delete()
        except discord.HTTPException:
            log.info(f"[LOBBY] full_prompt_delete_failed event={self.event_id}", exc_info=True)

    def _maybe_schedule_lobby_full_prompt(self, classified: list[tuple[str, str | None]]) -> None:
        """Arm a one-shot nudge to start a Ready Check once the lobby first fills with a full pod of
        linked players. The delayed task re-validates before posting, so a transient dip-and-refill is
        harmless and a sustained drop just lets it lapse. Sent at most once per lobby."""
        if (self.kind == "mock" or self.draft_complete or self.drafting
                or self.ready_check_active or self._lobby_full_prompted):
            return
        if not self._lobby_pod_full(classified):
            return
        if self._lobby_full_prompt_task is not None and not self._lobby_full_prompt_task.done():
            return
        self._lobby_full_prompt_task = asyncio.create_task(self._lobby_full_prompt_after_delay())

    async def _lobby_full_prompt_after_delay(self) -> None:
        try:
            await asyncio.sleep(_LOBBY_FULL_PROMPT_DELAY_S)
        except asyncio.CancelledError:
            return
        if self.draft_complete or self.drafting or self.ready_check_active or self._lobby_full_prompted:
            return
        if not self._lobby_pod_full(await self.classified_session_users()):
            return
        thread = await self._fetch_thread()
        if thread is None:
            return
        self._lobby_full_prompted = True
        try:
            self._lobby_full_prompt_message = await thread.send(MSG_LOBBY_FULL_PROMPT, view=LobbyReadyButtonView())
        except discord.HTTPException:
            self._lobby_full_prompted = False
            log.warning(f"[LOBBY] full_prompt_send_failed event={self.event_id}", exc_info=True)

    async def apply_seating_mode(self) -> None:
        """Push the current seating_mode to the live table. Leaderboard recomputes the seeded order
        from the present lobby; random asserts the shuffle flag; manual is driven by the Seat Order
        button + the pre-startDraft re-assert, so nothing is pushed here. Pre-draft only."""
        if not self.sio.connected or self.drafting or self.draft_complete:
            return
        if self.seating_mode == "leaderboard":
            await self._apply_leaderboard_seating()
        elif self.seating_mode == "random":
            try:
                await self.sio.emit("setRandomizeSeatingOrder", True)
            except Exception:
                log.exception(f"[SEATING] randomize_emit_failed event={self.event_id}")

    async def _apply_leaderboard_seating(self) -> None:
        """Compute the seeded ring from the present lobby and emit setSeating. Idempotent: skips the
        emit when the computed order matches what was last applied, so the sessionUsers broadcast that
        setSeating itself triggers can't drive a re-seat loop."""
        name_to_id = {
            u.get("userName"): u.get("userID")
            for u in self.player_session_users()
            if u.get("userID")
        }
        if len(name_to_id) < 2:
            return
        ordered_names = await asyncio.to_thread(_leaderboard_seat_order_sync, list(name_to_id))
        user_id_order = tuple(name_to_id[name] for name in ordered_names if name in name_to_id)
        if len(user_id_order) != len(name_to_id):
            log.warning(f"[SEATING] leaderboard_order_mismatch event={self.event_id} names={ordered_names}")
            return
        if user_id_order == self._last_seating_signature:
            return
        try:
            await self.sio.emit("setRandomizeSeatingOrder", False)
            await self.sio.emit("setSeating", list(user_id_order))
        except Exception:
            log.exception(f"[SEATING] leaderboard_emit_failed event={self.event_id}")
            return
        self._last_seating_signature = user_id_order
        log.info(f"[SEATING] leaderboard_applied event={self.event_id} order={ordered_names}")

    async def _reapply_seating_if_set(self) -> None:
        """Re-assert seating right before startDraft so late joins/leaves can't leave a stale order in
        place. Leaderboard recomputes from the final roster; random re-asserts the shuffle; manual
        re-emits the organizer's frozen order. Best-effort: skipped (logged) on lobby mismatch."""
        if self.seating_mode in ("leaderboard", "random"):
            await self.apply_seating_mode()
            return
        if not self.desired_seating:
            return
        err = await self.set_seating_order(self.desired_seating)
        if err is not None:
            log.info(f"[SEATING] reapply_skipped event={self.event_id} reason={err!r}")

    async def _emit_with_ack(self, event: str, *args, timeout_s: float = 5.0):
        """Emit a socket.io event and wait for the server's ack callback."""
        future: asyncio.Future = asyncio.Future()

        def _cb(*cb_args):
            if not future.done():
                future.set_result(cb_args[0] if cb_args else None)

        try:
            await self.sio.emit(event, *args, callback=_cb)
            return await asyncio.wait_for(future, timeout=timeout_s)
        except asyncio.TimeoutError:
            log.warning(f"{event} ack timeout for {self.session_id}")
            return None
        except Exception:
            log.exception(f"{event} emit failed for {self.session_id}")
            return None

    async def share_draft_log(self) -> bool:
        """Owner-only emit that flips the session's delayed/personal logs to fully public.

        Reconnects first when the socket dropped mid-event: this emit is the only way to unlock the
        logs, the session is recoverable by sessionID, and ownership persists for the same userID.
        """
        if not self.sio.connected:
            log.info(f"[DRAFT] share_log.reconnecting event={self.event_id}")
            self._closed = False
            try:
                await self.sio.connect(self._connect_url, transports=["websocket"], wait_timeout=10)
            except (socketio.exceptions.ConnectionError, OSError) as e:
                log.warning(f"[DRAFT] share_log.skipped event={self.event_id} reason=reconnect_failed err={e!s}")
                return False
        if not self.draft_logs:
            log.warning(f"[DRAFT] share_log.skipped event={self.event_id} reason=no_payload")
            return False
        payload = next(iter(self.draft_logs.values()))
        try:
            await self.sio.emit("shareDraftLog", payload)
            log.info(f"[DRAFT] share_log.done event={self.event_id}")
            return True
        except Exception:
            log.exception(f"[DRAFT] share_log.error event={self.event_id}")
            return False

    async def takeover(self, target_user_id: str) -> tuple[bool, str]:
        """Hand session ownership to target_user_id and disconnect the bot.

        Sequence (ported from Amelas/DraftBot's /mutiny): setOwnerIsPlayer(True) → setSessionOwner(target).
        Draftmancer's protocol forbids both emits while a draft is in progress for an owner-spectator
        bot, so we refuse mid-draft rather than silently no-op.
        """
        log.info(
            f"[LIFECYCLE] takeover.start event={self.event_id} target={target_user_id} "
            f"sio_connected={self.sio.connected} drafting={self.drafting}"
        )
        if not self.sio.connected:
            return False, "Draftmancer session is not connected."
        if self.drafting:
            return False, (
                "A draft is already in progress — Draftmancer doesn't allow ownership "
                "transfer mid-draft when the bot is owner-spectator. Finish the draft, then retry."
            )
        await self.share_draft_log()
        try:
            await self.sio.emit("setOwnerIsPlayer", True)
            await asyncio.sleep(1.0)
            await self.sio.emit("setSessionOwner", target_user_id)
            await asyncio.sleep(1.0)
            log.info(f"[LIFECYCLE] takeover.done event={self.event_id} target={target_user_id}")
        except Exception:
            log.exception(f"[LIFECYCLE] takeover.error event={self.event_id}")
            await bot_log_mod.get(self.bot).post(
                f"Takeover transfer failed for event `{self.event_id}`.",
                fingerprint=f"takeover_failed:{self.event_id}",
                tag="LIFECYCLE",
            )
            return False, "Ownership transfer failed; check logs."
        await self.disconnect_safely()
        return True, ""

    async def _ready_timeout(self) -> None:
        try:
            await asyncio.sleep(_READY_TIMEOUT_S)
        except asyncio.CancelledError:
            return
        log.warning(f"[READY] timeout event={self.event_id} timeout_s={_READY_TIMEOUT_S}")
        await bot_log_mod.get(self.bot).post(
            f"Ready check timed out for event `{self.event_id}` — draft did not start.",
            fingerprint=f"ready_check_timeout:{self.event_id}",
            tag="READY",
        )
        await self._invalidate_ready_check("timed out")

    async def _invalidate_ready_check(self, reason: str, *, decliner_name: str | None = None) -> None:
        if not self.ready_check_active:
            return
        log.info(
            f"[READY] invalidated event={self.event_id} reason={reason!r} "
            f"decliner={decliner_name!r}"
        )
        self.ready_check_active = False
        self.last_ready_summary = (len(self.ready_users), len(self.expected_user_ids))
        self.ready_users = set()
        if self._ready_timeout_task is not None:
            self._ready_timeout_task.cancel()
        self.last_decliner_name = decliner_name
        self.last_cancel_reason = None if decliner_name is not None else reason
        await self.refresh_lobby_now()

    def _schedule_end_watchdog(self) -> None:
        self._cancel_end_watchdog()
        self._end_watchdog_task = asyncio.create_task(self._end_draft_watchdog())

    def _cancel_end_watchdog(self) -> None:
        if self._end_watchdog_task is not None and not self._end_watchdog_task.done():
            self._end_watchdog_task.cancel()
        self._end_watchdog_task = None

    async def _end_draft_watchdog(self) -> None:
        window_s = max(1, settings.pod_draft_end_watchdog_minutes) * 60
        try:
            await asyncio.sleep(window_s)
        except asyncio.CancelledError:
            return
        if self.draft_complete or self.finalized:
            return
        log.warning(
            f"[DRAFT] end_watchdog_tripped event={self.event_id} window_min={settings.pod_draft_end_watchdog_minutes} "
            f"drafting={self.drafting} complete={self.draft_complete}"
        )
        await bot_log_mod.get(self.bot).post(
            f"endDraft not received for event `{self.event_id}` after "
            f"{settings.pod_draft_end_watchdog_minutes} min — draft may be stuck.",
            fingerprint=f"end_draft_watchdog:{self.event_id}",
            tag="DRAFT",
        )

def apply_seat_indexes(session, event_id: str, seats: list[str]) -> None:
    if not seats:
        return
    rows = session.execute(
        select(PodDraftParticipant).where(PodDraftParticipant.event_id == event_id)
    ).scalars().all()
    by_dm: dict[str, PodDraftParticipant] = {}
    by_display: dict[str, PodDraftParticipant] = {}
    for row in rows:
        if row.draftmancer_name:
            by_dm[normalize_player_name(row.draftmancer_name)] = row
        if row.display_name:
            by_display[normalize_player_name(row.display_name)] = row
    matched = 0
    for i, name in enumerate(seats):
        if not name or name == _BOT_USER_NAME or _AI_BOT_NAME_RE.match(name):
            continue
        key = normalize_player_name(name)
        row = by_dm.get(key) or by_display.get(key)
        if row is None:
            log.info(f"seat_index: no participant matching {name!r} in {event_id}")
            continue
        row.seat_index = i
        matched += 1
    log.info(f"seat_index: applied to {matched}/{len(seats)} seats for {event_id}")


def _is_ready_state(state) -> bool:
    """Draftmancer sends setReady(userID, state) where state can be 0/1 or 'Ready'/'NotReady'."""
    if isinstance(state, bool):
        return state
    if isinstance(state, int):
        return state == 1
    if isinstance(state, str):
        return state.lower() == "ready"
    return bool(state)


def _ack_error_text(ack) -> str | None:
    """Pull a human error string out of Draftmancer's SocketAck/SocketError shape, or None on success."""
    if ack is None:
        return None
    if isinstance(ack, dict):
        if ack.get("code") and ack.get("code") != 0:
            title = ack.get("title") or "Error"
            text = ack.get("text") or ack.get("error") or ""
            return f"{title}: {text}".strip(": ")
        if ack.get("error"):
            return str(ack["error"])
    return None


async def start_manager(
    bot: commands.Bot, event_id: str, session_id: str, thread_id: int,
    set_code: str, expected_attendee_count: int, *,
    event_name: str = "Pod Draft",
    draftmancer_url: str = "",
    kind: str = "tournament",
    mock_lobby_message: "discord.Message | None" = None,
    rsvps_yes: list[str] | None = None,
    rsvps_maybe: list[str] | None = None,
    reconnect: bool = False,
) -> PodDraftManager | None:
    existing = ACTIVE_POD_MANAGERS.get(event_id)
    if existing is not None:
        log.info(f"[LIFECYCLE] start_manager.already_active event={event_id}")
        return existing
    manager = PodDraftManager(
        bot, event_id, session_id, thread_id, set_code, expected_attendee_count,
        event_name=event_name, draftmancer_url=draftmancer_url, kind=kind,
        mock_lobby_message=mock_lobby_message,
        rsvps_yes=rsvps_yes, rsvps_maybe=rsvps_maybe, reconnect=reconnect,
    )
    persisted_mode = await asyncio.to_thread(load_event_pairing_mode_sync, event_id)
    if persisted_mode:
        manager.pairing_mode = persisted_mode
    persisted_seating = await asyncio.to_thread(load_event_seating_mode_sync, event_id)
    if persisted_seating:
        manager.seating_mode = persisted_seating
    ACTIVE_POD_MANAGERS[event_id] = manager
    log.info(
        f"[LIFECYCLE] start_manager.registered event={event_id} sid={session_id} "
        f"thread={thread_id} set={set_code} pairing={manager.pairing_mode} "
        f"registry_size={len(ACTIVE_POD_MANAGERS)}"
    )
    ok = await manager.connect()
    if not ok:
        ACTIVE_POD_MANAGERS.pop(event_id, None)
        log.warning(
            f"[LIFECYCLE] start_manager.connect_failed event={event_id} "
            f"registry_size={len(ACTIVE_POD_MANAGERS)}"
        )
        await manager._mark_socket_status("error")
        return None
    return manager


async def set_event_format(event_id: str, code: str) -> str | None:
    """Change a pod's format by event id; routes to the live manager when one exists, else persists directly.
    Returns an error string or None."""
    manager = ACTIVE_POD_MANAGERS.get(event_id)
    if manager is not None:
        return await manager.apply_format(code)
    if not await asyncio.to_thread(_persist_format, event_id, code):
        return pod_format.FORMAT_LOCKED_MSG
    return None


def _persist_format(event_id: str, code: str) -> bool:
    with SessionLocal() as session:
        if update_event_format(session, event_id, code):
            session.commit()
            return True
        return False


async def set_event_pairing_mode(event_id: str, mode: str) -> str | None:
    """Set a pod's pairing mode by event id; updates the live manager when one exists and persists.
    Locked once the tournament has started. Returns an error string or None."""
    if mode not in ("swiss", "bracket", "random"):
        return "Unknown pairing mode."
    manager = ACTIVE_POD_MANAGERS.get(event_id)
    if manager is not None:
        if manager.current_round and manager.current_round > 0:
            return "Pairing mode is locked once the tournament has started."
        manager.pairing_mode = mode
    await asyncio.to_thread(persist_pairing_mode, event_id, mode)
    if manager is not None:
        await manager.refresh_lobby_now()
    return None


async def set_event_seating_mode(event_id: str, mode: str) -> str | None:
    """Set a pod's seating mode by event id; updates the live manager when one exists and persists.
    Locked once the draft is underway. Returns an error string or None."""
    if mode not in ("random", "manual", "leaderboard"):
        return "Unknown seating mode."
    manager = ACTIVE_POD_MANAGERS.get(event_id)
    if manager is not None:
        if manager.drafting or manager.draft_complete:
            return "Seating mode is locked once the draft has started."
        manager.seating_mode = mode
    await asyncio.to_thread(persist_seating_mode, event_id, mode)
    if manager is not None:
        await manager.apply_seating_mode()
        await manager.refresh_lobby_now()
    return None


async def set_event_seating(event_id: str, ordered_user_names: list[str]) -> str | None:
    """Apply a manual Draftmancer seating order by event id. Live-only — needs the socket session.
    Returns an error string or None."""
    manager = ACTIVE_POD_MANAGERS.get(event_id)
    if manager is None:
        return "No active Draftmancer session for this pod."
    return await manager.set_seating_order(ordered_user_names)


async def rehydrate_active_lobbies(bot) -> None:
    """Startup sweep: reconnect a manager to any pod whose Draftmancer socket was live (lobby or
    drafting, tournament not yet started) when the bot last stopped, reclaiming ownership so ready
    checks, kicks, seating, and draft start keep working after a restart. The bot's userID is
    derived from the sessionID, so reconnecting to the same session re-lands as the same user and
    setSessionOwner reclaims the chair without forcing players to rejoin a new session."""
    rows = await asyncio.to_thread(_load_live_lobby_pods_sync)
    restored = 0
    for row in rows:
        event_id = row["id"]
        if event_id in ACTIVE_POD_MANAGERS:
            continue
        session_id = row["draftmancer_session"]
        expected = await asyncio.to_thread(_count_participants_sync, event_id)
        manager = await start_manager(
            bot, event_id, session_id, int(row["discord_thread_id"]), row["set_code"], expected,
            event_name=row["name"], draftmancer_url=draftmancer_url_for(session_id),
            kind=row["kind"], reconnect=True,
        )
        if manager is None:
            log.warning(f"[LIFECYCLE] rehydrate_lobby.connect_failed event={event_id} sid={session_id}")
            continue
        restored += 1
        log.info(f"[LIFECYCLE] rehydrate_lobby.restored event={event_id} sid={session_id}")
    if restored:
        log.info(f"startup sweep reconnected {restored} live lobby/draft session(s)")


def _load_live_lobby_pods_sync() -> list[dict]:
    """Pod events whose Draftmancer socket was live but whose tournament hadn't started when the bot
    last stopped — the rows the restart sweep reconnects a manager for."""
    cutoff = datetime.now(timezone.utc) - LOBBY_REHYDRATE_WINDOW
    with SessionLocal() as session:
        rows = session.execute(
            select(
                PodDraftEvent.id,
                PodDraftEvent.draftmancer_session,
                PodDraftEvent.discord_thread_id,
                PodDraftEvent.set_code,
                PodDraftEvent.name,
                PodDraftEvent.kind,
            ).where(
                PodDraftEvent.socket_status == "connected",
                PodDraftEvent.finalized_at.is_(None),
                PodDraftEvent.current_round.is_(None),
                PodDraftEvent.event_time >= cutoff,
            )
        ).all()
    return [dict(row._mapping) for row in rows]


def _count_participants_sync(event_id: str) -> int:
    with SessionLocal() as session:
        return session.execute(
            select(func.count()).select_from(PodDraftParticipant)
            .where(PodDraftParticipant.event_id == event_id)
        ).scalar_one()


async def _find_pinned_lobby_card(thread, bot_user, event_name: str) -> "discord.Message | None":
    """Rediscover the lobby status card pinned by an earlier manager (pre-restart) so a reconnect
    edits it in place instead of posting and pinning a duplicate. The 🤖 Commands field is unique to
    the lobby card, distinguishing it from a pinned standings or round-pairings embed."""
    try:
        pins = await thread.pins()
    except discord.HTTPException:
        log.warning(f"could not fetch pins to rediscover lobby card for {event_name}", exc_info=True)
        return None
    for msg in pins:
        if bot_user is not None and msg.author.id != bot_user.id:
            continue
        for pinned_embed in msg.embeds:
            if (pinned_embed.title or "") != event_name:
                continue
            if any("Commands" in (field.name or "") for field in pinned_embed.fields):
                return msg
    return None


def _classify_names_sync(names: list[str]) -> list[tuple[str, str | None]]:
    with SessionLocal() as session:
        return classify_lobby_names(session, names)


def _discord_ids_for_names_sync(names: list[str]) -> dict[str, str | None]:
    """Map each Draftmancer userName to its linked player's discord_id (or None when unrecognized)."""
    with SessionLocal() as session:
        result: dict[str, str | None] = {}
        for name in names:
            player = player_for_name(session, name)
            result[name] = player.discord_id if player else None
        return result


def _leaderboard_seat_order_sync(names: list[str]) -> list[str]:
    with SessionLocal() as session:
        return leaderboard_seat_order(session, names)


def _find_guild_member_for_arena(guild: discord.Guild, arena_name: str) -> discord.Member | None:
    """Match a Draftmancer username to a guild member by display_name or username.
    Strips the trailing Arena suffix so `MNG#61656` matches a member whose display name is `MNG`.
    Exact matches win; otherwise falls back to word tokens, so `wonderland#12345` matches
    a member displayed as `Alice (Wonderland)`."""
    norm = normalize_player_name(arena_name)
    if not norm:
        return None
    for member in guild.members:
        if member.display_name.lower() == norm or member.name.lower() == norm:
            return member
    for member in guild.members:
        if name_token_match(norm, member.display_name) or name_token_match(norm, member.name):
            return member
    return None


def _ensure_players_for_members_sync(pairs: list[tuple[str, discord.Member]]) -> None:
    """For each (arena_name, member) pair, find or lazily create a Player row keyed by discord_id.
    Only a full ArenaID#12345 handle is stored as `arena_name` — a bare Draftmancer nickname goes to
    aliases only — and a stored full handle is never overwritten here."""
    if not pairs:
        return
    with SessionLocal() as session:
        taken_slugs = set(session.execute(select(Player.slug)).scalars().all())
        for arena_name, member in pairs:
            discord_id = str(member.id)
            normalized = normalize_player_name(arena_name)
            existing = session.execute(
                select(Player).where(Player.discord_id == discord_id)
            ).scalar_one_or_none()
            if existing is not None:
                if full_arena_handle(arena_name) and not full_arena_handle(existing.arena_name):
                    existing.arena_name = arena_name
                    log.info(f"backfilled arena_name for {member.display_name} → {arena_name}")
                if normalized and normalized not in existing.arena_aliases:
                    existing.arena_aliases = [*existing.arena_aliases, normalized]
                continue
            slug = disambiguate_slug(slugify(member.display_name), taken_slugs)
            taken_slugs.add(slug)
            session.add(Player(
                slug=slug,
                discord_id=discord_id,
                discord_username=member.name,
                display_name=member.display_name,
                avatar_hash=extract_avatar_hash(member),
                arena_name=arena_name if full_arena_handle(arena_name) else None,
                arena_aliases=[normalized] if normalized else [],
                active=True,
                leaderboard_opt_in=False,
            ))
            log.info(f"auto-created Player row for guild member {member.display_name} (arena={arena_name})")
        session.commit()
