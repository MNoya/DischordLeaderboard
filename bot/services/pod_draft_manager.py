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

import discord
import socketio
from discord.ext import commands

from sqlalchemy import select

from bot.config import settings
from bot.database import SessionLocal
from bot.discord_helpers import extract_avatar_hash
from bot.models import Player, PodDraftEvent, PodDraftParticipant
from bot.scripts.draftmancer_log import build_compact
from bot.services.lobby_embed import LobbyReadyButtonView, render as render_lobby_embed
from bot.services.magicprotools import submit_to_api as submit_to_magicprotools
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_drafts import _normalize_player_name, classify_lobby_names, seed_event_participants
from bot.services.pod_tournament import start_tournament
from bot.slug import disambiguate_slug, slugify


log = logging.getLogger(__name__)


_BACKOFF_BASE_S = 1.0
_BACKOFF_MAX_S = 30.0
_BACKOFF_MAX_RETRIES = 8
_BOT_USER_NAME = "DisChordBot"
_READY_TIMEOUT_S = 90
_ARENA_SUFFIX_RE = re.compile(r"#\d+$")
_AI_BOT_NAME_RE = re.compile(r"^Bot #\d+$")


class PodDraftManager:
    def __init__(self, bot: commands.Bot, event_id: str, session_id: str, thread_id: int,
                 set_code: str, expected_attendee_count: int, *,
                 event_name: str = "Pod Draft",
                 draftmancer_url: str = "",
                 rsvps_yes: list[str] | None = None,
                 rsvps_maybe: list[str] | None = None) -> None:
        self.bot = bot
        self.event_id = event_id
        self.session_id = session_id
        self.thread_id = thread_id
        self.set_code = set_code
        self.expected_attendee_count = expected_attendee_count
        self.event_name = event_name
        self.draftmancer_url = draftmancer_url
        self.rsvps_yes: list[str] = list(rsvps_yes or [])
        self.rsvps_maybe: list[str] = list(rsvps_maybe or [])
        self.session_users: list[dict] = []
        self.bot_user_id: str | None = None
        self.owner_claimed = False
        self._closed = False
        self.ready_check_active = False
        self.ready_users: set[str] = set()
        self.expected_user_ids: set[str] = set()
        self.lobby_status_message: object | None = None
        self._ready_timeout_task: asyncio.Task | None = None
        self.drafting = False
        self.draft_complete = False
        self.last_decliner_name: str | None = None
        self.last_cancel_reason: str | None = None
        self.draft_logs: dict[str, dict] = {}
        self.mpt_task: asyncio.Task | None = None
        self.current_round = 0
        self.finalized = False
        self.tournament_roster: list[str] = []  # draftmancer userNames, set on endDraft
        self.tournament_players: list = []       # pod_swiss.Player list, set by pod_tournament.start_tournament
        self.standings_message = None
        self.round_messages: dict[int, "discord.Message"] = {}
        self.grace_task = None
        self.grace_round: int | None = None
        self.champion_announced = False
        self.champion_announcement_message = None
        self.champion_discord_ids: set[str] = set()
        self.sio = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)
        self.sio.on("connect", self._on_connect)
        self.sio.on("disconnect", self._on_disconnect)
        self.sio.on("sessionUsers", self._on_session_users)
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
                    log.error(f"draftmancer connect gave up after {attempt} attempts for {self.session_id}: {e}")
                    return False
                wait = min(delay + random.uniform(0, delay * 0.25), _BACKOFF_MAX_S)
                log.warning(f"draftmancer connect attempt {attempt} failed: {e}; retrying in {wait:.1f}s")
                await asyncio.sleep(wait)
                delay = min(delay * 2, _BACKOFF_MAX_S)
        return False

    async def disconnect_safely(self) -> None:
        self._closed = True
        try:
            if self.sio.connected:
                await self.sio.disconnect()
        except Exception:
            log.warning(f"clean disconnect failed for {self.session_id}", exc_info=True)
        ACTIVE_POD_MANAGERS.pop(self.event_id, None)

    async def _on_connect(self) -> None:
        log.info(f"draftmancer ws connected for {self.session_id}")
        await self._mark_socket_status("connected")

    async def _on_disconnect(self) -> None:
        log.warning(
            f"draftmancer ws disconnected for {self.session_id} "
            f"(closed={self._closed}, drafting={self.drafting}, draft_complete={self.draft_complete})"
        )
        self._closed = True
        if self.drafting or self.draft_complete:
            log.info(f"keeping manager {self.event_id} in ACTIVE_POD_MANAGERS — tournament in flight")
            return
        ACTIVE_POD_MANAGERS.pop(self.event_id, None)

    async def _on_session_users(self, users) -> None:
        self.session_users = list(users) if isinstance(users, list) else []
        names = [u.get("userName") for u in self.session_users]
        log.info(f"draftmancer sessionUsers for {self.session_id}: {names}")
        # Any session change clears the notready banner; lobby reverts to its normal state
        self.last_decliner_name = None
        self.last_cancel_reason = None
        if self.bot_user_id is None:
            for u in self.session_users:
                if u.get("userName") == _BOT_USER_NAME:
                    self.bot_user_id = u.get("userID")
                    log.info(f"found bot userID={self.bot_user_id} for {self.session_id}")
                    if not self.owner_claimed:
                        asyncio.create_task(self._claim_ownership_and_apply_settings())
                    break

        non_bot_names = [u.get("userName") for u in self.session_users
                         if u.get("userName") and u.get("userName") != _BOT_USER_NAME]
        classified = await self._classify_users(non_bot_names) if non_bot_names else []
        await self._refresh_lobby_status(classified)

        if self.ready_check_active:
            current = {u.get("userID") for u in self.session_users if u.get("userName") != _BOT_USER_NAME}
            if current != self.expected_user_ids:
                asyncio.create_task(self._invalidate_ready_check("Player list changed"))

    async def _on_update_user(self, payload) -> None:
        if not isinstance(payload, dict):
            return
        user_id = payload.get("userID")
        updates = payload.get("updatedProperties") or {}
        if not user_id or not updates:
            return
        for u in self.session_users:
            if u.get("userID") == user_id:
                u.update(updates)
                break
        if "userName" in updates:
            log.info(f"draftmancer updateUser rename for {self.session_id}: {user_id} → {updates['userName']}")
            await self.refresh_lobby_now()

    async def _claim_ownership_and_apply_settings(self) -> None:
        if self.bot_user_id is None or self.owner_claimed:
            return
        self.owner_claimed = True
        try:
            await self.sio.emit("setSessionOwner", self.bot_user_id)
            await asyncio.sleep(0.3)
            await self._emit_session_settings()
            log.info(f"session ownership + settings applied for {self.session_id}")
        except Exception:
            log.exception(f"ownership/settings flow failed for {self.session_id}")

    async def _emit_session_settings(self) -> None:
        await self.sio.emit("setRestriction", [self.set_code.lower()])
        await self.sio.emit("setOwnerIsPlayer", False)
        await self.sio.emit("setMaxPlayers", settings.pod_draft_max_players)
        await self.sio.emit("setPickTimer", settings.pod_draft_pick_timer)
        await self.sio.emit("setBots", settings.pod_draft_bots)
        await self.sio.emit("setColorBalance", False)
        await self.sio.emit("setPersonalLogs", True)
        await self.sio.emit("setDraftLogRecipients", "delayed")
        log.info(f"draftmancer settings emitted for {self.session_id} (set={self.set_code} bots={settings.pod_draft_bots})")

    async def _mark_socket_status(self, status: str) -> None:
        with SessionLocal() as session:
            event = session.get(PodDraftEvent, self.event_id)
            if event is not None:
                event.socket_status = status
                session.commit()

    async def initiate_ready_check(self, thread) -> str | None:
        """Start a Draftmancer ready check; returns an error string on failure, None on success."""
        if not self.sio.connected:
            return "Draftmancer session is not connected."
        if self.ready_check_active:
            return "Ready check already in progress."
        non_bot = [u for u in self.session_users if u.get("userName") != _BOT_USER_NAME]
        if not non_bot:
            return "Nobody in the Draftmancer lobby yet."
        self.expected_user_ids = {u.get("userID") for u in non_bot}
        self.ready_users = set()
        self.ready_check_active = True
        self.last_decliner_name = None
        self.last_cancel_reason = None
        try:
            await self.sio.emit("readyCheck")
        except Exception:
            self.ready_check_active = False
            log.exception(f"readyCheck emit failed for {self.session_id}")
            return "Could not start ready check — see logs."
        self._ready_timeout_task = asyncio.create_task(self._ready_timeout())
        await self.refresh_lobby_now()
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

    async def refresh_lobby_now(self) -> None:
        """Re-run classification with current sessionUsers and edit the lobby card.
        External hook for /pod-link-arena so the lobby reflects the new link immediately."""
        non_bot_names = [u.get("userName") for u in self.session_users
                         if u.get("userName") and u.get("userName") != _BOT_USER_NAME]
        classified = await self._classify_users(non_bot_names) if non_bot_names else []
        await self._refresh_lobby_status(classified)

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

    async def _refresh_lobby_status(self, classified: list[tuple[str, str | None]]) -> None:
        thread = await self._fetch_thread()
        if thread is None:
            return
        state = self._compute_state(classified)
        ready_now = len(self.ready_users) if state == "ready" else None
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
            ready_count=ready_now,
            ready_arena_names=ready_arena_names,
            decliner_name=self.last_decliner_name,
            cancel_reason=self.last_cancel_reason,
            display_name_by_mention_id=await self._resolve_rsvp_mentions(thread.guild),
        )
        has_unrecognized = any(dn is None for _, dn in classified)
        view = (
            None if state in ("drafting", "complete")
            else LobbyReadyButtonView(
                draftmancer_url=self.draftmancer_url,
                ready_disabled=(state == "ready" or has_unrecognized),
            )
        )
        if self.lobby_status_message is None:
            try:
                self.lobby_status_message = await thread.send(embed=embed, view=view)
            except Exception:
                log.warning(f"could not post lobby status for {self.session_id}", exc_info=True)
        else:
            try:
                await self.lobby_status_message.edit(embed=embed, view=view)
            except Exception:
                log.warning(f"could not edit lobby status for {self.session_id}", exc_info=True)

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
        log.info(f"endDraft received for {self.session_id}")
        self.drafting = False
        self.draft_complete = True
        await self._mark_socket_status("draft_done")
        await self.refresh_lobby_now()
        payload = next(iter(self.draft_logs.values()), None)
        if payload is not None:
            self.mpt_task = asyncio.create_task(self._submit_logs_to_magicprotools(payload))
        else:
            log.warning(f"endDraft for {self.session_id} but no draftLog payload cached; skipping MPT submit")
        # Snapshot roster and hand off to the Python-Swiss bracket flow
        if settings.pod_draft_test_roster.strip():
            self.tournament_roster = [n.strip() for n in settings.pod_draft_test_roster.split(",") if n.strip()]
            log.info(f"using POD_DRAFT_TEST_ROSTER for {self.session_id}: {self.tournament_roster}")
        else:
            self.tournament_roster = [
                u.get("userName") for u in self.session_users
                if u.get("userName") and u.get("userName") != _BOT_USER_NAME
            ]
        asyncio.create_task(start_tournament(self))

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
        log.info(f"draftLog stored for {self.session_id} ({len(self.draft_logs)} total)")
        await asyncio.to_thread(self._persist_draft_log_gz, log_payload)

    async def _submit_logs_to_magicprotools(self, log_payload: dict) -> None:
        """For each Draftmancer seat in the log, submit to MagicProTools and stash the URL on the
        matching pod_draft_participants row. Fire-and-forget; per-seat failures are silent."""
        if settings.mpt_api_key is None:
            log.warning(f"MPT_API_KEY not configured; no draft logs uploaded for {self.session_id}")
            return
        users = log_payload.get("users") or {}
        if not isinstance(users, dict):
            return
        for user_id, user_data in users.items():
            if not isinstance(user_data, dict):
                continue
            user_name = user_data.get("userName")
            if not user_name or user_name == _BOT_USER_NAME:
                continue
            # Skip Draftmancer AI bots — they have no participant row, the URL would be discarded
            # downstream, and we'd waste an MPT API call per bot seat.
            if user_data.get("isBot"):
                continue
            url = await submit_to_magicprotools(user_id, log_payload)
            if not url:
                continue
            await asyncio.to_thread(self._store_draft_log_url, user_name, url)

    def _store_draft_log_url(self, draftmancer_name: str, url: str) -> None:
        try:
            with SessionLocal() as session:
                rows = session.execute(
                    select(PodDraftParticipant)
                    .where(
                        PodDraftParticipant.event_id == self.event_id,
                        PodDraftParticipant.draftmancer_name == draftmancer_name,
                    )
                ).scalars().all()
                if not rows:
                    log.info(f"magicprotools: no participant row matching {draftmancer_name} in {self.event_id}")
                    return
                for row in rows:
                    row.draft_log_url = url
                session.commit()
        except Exception:
            log.warning(f"magicprotools: store url failed for {draftmancer_name}", exc_info=True)

    def _persist_draft_log_gz(self, log_payload: dict) -> None:
        try:
            compact = build_compact(log_payload)
            blob = gzip.compress(json.dumps(compact, separators=(",", ":")).encode("utf-8"))
        except Exception:
            log.warning(f"draft_log_gz compact/gzip failed for {self.session_id}", exc_info=True)
            return
        try:
            with SessionLocal() as session:
                event = session.execute(
                    select(PodDraftEvent).where(PodDraftEvent.id == self.event_id)
                ).scalar_one_or_none()
                if event is None:
                    log.warning(f"draft_log_gz: event {self.event_id} not found, skipping persist")
                    return
                event.draft_log_gz = blob
                _apply_seat_indexes(session, self.event_id, compact.get("seats") or [])
                session.commit()
                log.info(f"draft_log_gz persisted for {self.event_id} ({len(blob)} bytes)")
        except Exception:
            log.warning(f"draft_log_gz persist failed for {self.event_id}", exc_info=True)

    async def _fetch_thread(self):
        try:
            return await self.bot.fetch_channel(self.thread_id)
        except Exception:
            log.warning(f"could not fetch thread {self.thread_id}", exc_info=True)
            return None

    async def _on_set_ready(self, user_id, ready_state) -> None:
        if not self.ready_check_active:
            return
        ready = _is_ready_state(ready_state)
        if ready:
            self.ready_users.add(user_id)
        else:
            self.ready_users.discard(user_id)
            # Explicit Not Ready: cancel the check immediately
            decliner_name = next(
                (u.get("userName") for u in self.session_users if u.get("userID") == user_id),
                None,
            )
            await self._invalidate_ready_check("declined", decliner_name=decliner_name)
            return
        await self.refresh_lobby_now()
        if self.ready_users >= self.expected_user_ids:
            await self._complete_ready_check()

    async def _complete_ready_check(self) -> None:
        if not self.ready_check_active:
            return
        self.ready_check_active = False
        if self._ready_timeout_task is not None:
            self._ready_timeout_task.cancel()
        await self._start_draft()

    async def _start_draft(self) -> None:
        result = await self._emit_with_ack("startDraft")
        log.info(f"startDraft ack for {self.session_id}: {result!r}")
        error_text = _ack_error_text(result)
        if error_text is not None:
            thread = await self._fetch_thread()
            if thread is not None:
                try:
                    await thread.send(
                        f"⚠️ Could not start the draft: {error_text}\n"
                        f"Use `/pod-takeover` to take control of the Draftmancer session manually."
                    )
                except Exception:
                    log.warning("could not post startDraft error", exc_info=True)
            return
        self.drafting = True
        await asyncio.to_thread(self._seed_participants_at_draft_start)
        await self.refresh_lobby_now()

    def _seed_participants_at_draft_start(self) -> None:
        """Insert pod_draft_participants for every non-bot Draftmancer userName now that the draft
        has begun (lobby locked). Idempotent — start_tournament will re-call with the same roster
        as a safety net after endDraft."""
        roster = [
            u.get("userName") for u in self.session_users
            if u.get("userName") and u.get("userName") != _BOT_USER_NAME
        ]
        if not roster:
            return
        try:
            with SessionLocal() as session:
                seed_event_participants(session, self.event_id, roster)
                session.commit()
            log.info(f"seeded {len(roster)} participants at draft start for {self.event_id}")
        except Exception:
            log.warning(f"could not seed participants at draft start for {self.event_id}", exc_info=True)

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
        """Owner-only emit that flips the session's delayed/personal logs to fully public."""
        if not self.sio.connected:
            log.warning(f"share_draft_log skipped for {self.session_id} — socket not connected")
            return False
        if not self.draft_logs:
            log.warning(f"share_draft_log skipped for {self.session_id} — no draftLog payload stored")
            return False
        payload = next(iter(self.draft_logs.values()))
        try:
            await self.sio.emit("shareDraftLog", payload)
            log.info(f"shared draftLog for {self.session_id}")
            return True
        except Exception:
            log.exception(f"shareDraftLog emit failed for {self.session_id}")
            return False

    async def takeover(self, target_user_id: str) -> tuple[bool, str]:
        """Hand session ownership to target_user_id and disconnect the bot.

        Sequence (ported from Amelas/DraftBot's /mutiny): setOwnerIsPlayer(True) → setSessionOwner(target).
        Draftmancer's protocol forbids both emits while a draft is in progress for an owner-spectator
        bot, so we refuse mid-draft rather than silently no-op.
        """
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
            log.info(f"takeover transferred ownership of {self.session_id} to {target_user_id}")
        except Exception:
            log.exception(f"takeover transfer failed for {self.session_id}")
            return False, "Ownership transfer failed; check logs."
        await self.disconnect_safely()
        return True, ""

    async def _ready_timeout(self) -> None:
        try:
            await asyncio.sleep(_READY_TIMEOUT_S)
        except asyncio.CancelledError:
            return
        await self._invalidate_ready_check("timed out")

    async def _invalidate_ready_check(self, reason: str, *, decliner_name: str | None = None) -> None:
        if not self.ready_check_active:
            return
        self.ready_check_active = False
        self.ready_users = set()
        if self._ready_timeout_task is not None:
            self._ready_timeout_task.cancel()
        self.last_decliner_name = decliner_name
        self.last_cancel_reason = None if decliner_name is not None else reason
        await self.refresh_lobby_now()

def _apply_seat_indexes(session, event_id: str, seats: list[str]) -> None:
    if not seats:
        return
    rows = session.execute(
        select(PodDraftParticipant).where(PodDraftParticipant.event_id == event_id)
    ).scalars().all()
    by_dm: dict[str, PodDraftParticipant] = {}
    by_display: dict[str, PodDraftParticipant] = {}
    for row in rows:
        if row.draftmancer_name:
            by_dm[_normalize_player_name(row.draftmancer_name)] = row
        if row.display_name:
            by_display[_normalize_player_name(row.display_name)] = row
    matched = 0
    for i, name in enumerate(seats):
        if not name or name == _BOT_USER_NAME or _AI_BOT_NAME_RE.match(name):
            continue
        key = _normalize_player_name(name)
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
    rsvps_yes: list[str] | None = None,
    rsvps_maybe: list[str] | None = None,
) -> PodDraftManager | None:
    existing = ACTIVE_POD_MANAGERS.get(event_id)
    if existing is not None:
        log.info(f"manager already active for event {event_id}")
        return existing
    manager = PodDraftManager(
        bot, event_id, session_id, thread_id, set_code, expected_attendee_count,
        event_name=event_name, draftmancer_url=draftmancer_url,
        rsvps_yes=rsvps_yes, rsvps_maybe=rsvps_maybe,
    )
    ACTIVE_POD_MANAGERS[event_id] = manager
    ok = await manager.connect()
    if not ok:
        ACTIVE_POD_MANAGERS.pop(event_id, None)
        await manager._mark_socket_status("error")
        return None
    return manager




def _classify_names_sync(names: list[str]) -> list[tuple[str, bool]]:
    with SessionLocal() as session:
        return classify_lobby_names(session, names)


def _find_guild_member_for_arena(guild: discord.Guild, arena_name: str) -> discord.Member | None:
    """Match a Draftmancer username to a guild member by display_name or username.
    Strips the trailing `#NNNN` Arena suffix so `MNG#61656` matches a member whose display name is `MNG`."""
    norm = _ARENA_SUFFIX_RE.sub("", arena_name).lower()
    for member in guild.members:
        if member.display_name.lower() == norm or member.name.lower() == norm:
            return member
    return None


def _ensure_players_for_members_sync(pairs: list[tuple[str, discord.Member]]) -> None:
    """For each (arena_name, member) pair, find or lazily create a Player row keyed by discord_id.
    Backfills `arena_name` on existing rows when null, never overwrites a value set by /pod-link-arena."""
    if not pairs:
        return
    with SessionLocal() as session:
        taken_slugs = set(session.execute(select(Player.slug)).scalars().all())
        for arena_name, member in pairs:
            discord_id = str(member.id)
            normalized = _normalize_player_name(arena_name)
            existing = session.execute(
                select(Player).where(Player.discord_id == discord_id)
            ).scalar_one_or_none()
            if existing is not None:
                if existing.arena_name is None:
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
                arena_name=arena_name,
                arena_aliases=[normalized] if normalized else [],
                active=True,
            ))
            log.info(f"auto-created Player row for guild member {member.display_name} (arena={arena_name})")
        session.commit()
