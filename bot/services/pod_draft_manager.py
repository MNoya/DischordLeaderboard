"""Draftmancer socket.io session lifecycle for a single pod-draft event.

One PodDraftManager per active event, kept in the module-level ACTIVE_POD_MANAGERS registry so the
ready check and bracket flows can look up the right session by event_id. Connects with
exponential backoff + jitter, joins the session, applies the agreed settings, and listens for
sessionUsers updates so later commands can act on who is in the lobby
"""
from __future__ import annotations

import asyncio
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
from bot.models import Player, PodDraftEvent
from bot.services.lobby_embed import LobbyReadyButtonView, render as render_lobby_embed
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_drafts import classify_lobby_names
from bot.services.pod_tournament import start_tournament
from bot.slug import disambiguate_slug, slugify


log = logging.getLogger(__name__)


_BACKOFF_BASE_S = 1.0
_BACKOFF_MAX_S = 30.0
_BACKOFF_MAX_RETRIES = 8
_BOT_USER_NAME = "DisChordBot"
_READY_TIMEOUT_S = 90
_START_DRAFT_DELAY_S = 1
_ARENA_SUFFIX_RE = re.compile(r"#\d+$")


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
        self.current_round = 0
        self.finalized = False
        self.tournament_roster: list[str] = []  # draftmancer userNames, set on endDraft
        self.tournament_players: list = []       # pod_swiss.Player list, set by pod_tournament.start_tournament
        self.sio = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)
        self.sio.on("connect", self._on_connect)
        self.sio.on("disconnect", self._on_disconnect)
        self.sio.on("sessionUsers", self._on_session_users)
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
                    log.error("draftmancer connect gave up after %d attempts for %s: %s",
                              attempt, self.session_id, e)
                    return False
                wait = min(delay + random.uniform(0, delay * 0.25), _BACKOFF_MAX_S)
                log.warning("draftmancer connect attempt %d failed: %s; retrying in %.1fs",
                            attempt, e, wait)
                await asyncio.sleep(wait)
                delay = min(delay * 2, _BACKOFF_MAX_S)
        return False

    async def disconnect_safely(self) -> None:
        self._closed = True
        try:
            if self.sio.connected:
                await self.sio.disconnect()
        except Exception:
            log.warning("clean disconnect failed for %s", self.session_id, exc_info=True)
        ACTIVE_POD_MANAGERS.pop(self.event_id, None)

    async def _on_connect(self) -> None:
        log.info("draftmancer ws connected for %s", self.session_id)
        await self._mark_socket_status("connected")

    async def _on_disconnect(self) -> None:
        log.warning("draftmancer ws disconnected for %s (closed=%s)", self.session_id, self._closed)
        # Reconnect-on-disconnect disabled during debugging so Draftmancer kicks don't loop;
        # disconnect_safely() is the explicit teardown path
        self._closed = True
        ACTIVE_POD_MANAGERS.pop(self.event_id, None)

    async def _on_session_users(self, users) -> None:
        self.session_users = list(users) if isinstance(users, list) else []
        names = [u.get("userName") for u in self.session_users]
        log.info("draftmancer sessionUsers for %s: %s", self.session_id, names)
        # Any session change clears the notready banner; lobby reverts to its normal state
        self.last_decliner_name = None
        self.last_cancel_reason = None
        if self.bot_user_id is None:
            for u in self.session_users:
                if u.get("userName") == _BOT_USER_NAME:
                    self.bot_user_id = u.get("userID")
                    log.info("found bot userID=%s for %s", self.bot_user_id, self.session_id)
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

    async def _claim_ownership_and_apply_settings(self) -> None:
        if self.bot_user_id is None or self.owner_claimed:
            return
        self.owner_claimed = True
        try:
            await self.sio.emit("setSessionOwner", self.bot_user_id)
            await asyncio.sleep(0.3)
            await self._emit_session_settings()
            log.info("session ownership + settings applied for %s", self.session_id)
        except Exception:
            log.exception("ownership/settings flow failed for %s", self.session_id)

    async def _emit_session_settings(self) -> None:
        await self.sio.emit("setRestriction", [self.set_code.lower()])
        await self.sio.emit("setOwnerIsPlayer", False)
        await self.sio.emit("setMaxPlayers", settings.pod_draft_max_players)
        await self.sio.emit("setPickTimer", settings.pod_draft_pick_timer)
        await self.sio.emit("setBots", settings.pod_draft_bots)
        await self.sio.emit("setColorBalance", False)
        await self.sio.emit("setPersonalLogs", True)
        await self.sio.emit("setDraftLogRecipients", "delayed")
        log.info("draftmancer settings emitted for %s (set=%s bots=%d)",
                 self.session_id, self.set_code, settings.pod_draft_bots)

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
            log.exception("readyCheck emit failed for %s", self.session_id)
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

    async def _refresh_lobby_status(self, classified: list[tuple[str, str | None]]) -> None:
        thread = await self._fetch_thread()
        if thread is None:
            return
        state = self._compute_state(classified)
        ready_now = len(self.ready_users) if state == "ready" else None
        embed = render_lobby_embed(
            title=self.event_name,
            rsvps_yes=self.rsvps_yes,
            rsvps_maybe=self.rsvps_maybe,
            in_session=classified,
            state=state,
            draftmancer_url=self.draftmancer_url,
            ready_count=ready_now,
            decliner_name=self.last_decliner_name,
            cancel_reason=self.last_cancel_reason,
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
                log.warning("could not post lobby status for %s", self.session_id, exc_info=True)
        else:
            try:
                await self.lobby_status_message.edit(embed=embed, view=view)
            except Exception:
                log.warning("could not edit lobby status for %s", self.session_id, exc_info=True)

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
        log.info("endDraft received for %s", self.session_id)
        self.drafting = False
        self.draft_complete = True
        await self._mark_socket_status("draft_done")
        await self.refresh_lobby_now()
        # Snapshot roster and hand off to the Python-Swiss bracket flow
        if settings.pod_draft_test_roster.strip():
            self.tournament_roster = [n.strip() for n in settings.pod_draft_test_roster.split(",") if n.strip()]
            log.info("using POD_DRAFT_TEST_ROSTER for %s: %s", self.session_id, self.tournament_roster)
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
        log.info("draftLog stored for %s (%d total)", self.session_id, len(self.draft_logs))

    async def _fetch_thread(self):
        try:
            return await self.bot.fetch_channel(self.thread_id)
        except Exception:
            log.warning("could not fetch thread %s", self.thread_id, exc_info=True)
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
        await asyncio.sleep(_START_DRAFT_DELAY_S)
        await self._start_draft()

    async def _start_draft(self) -> None:
        result = await self._emit_with_ack("startDraft")
        log.info("startDraft ack for %s: %r", self.session_id, result)
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
        await self.refresh_lobby_now()

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
            log.warning("%s ack timeout for %s", event, self.session_id)
            return None
        except Exception:
            log.exception("%s emit failed for %s", event, self.session_id)
            return None

    async def share_draft_log(self) -> bool:
        """Owner-only emit that flips the session's delayed/personal logs to fully public."""
        if not self.sio.connected:
            log.warning("share_draft_log skipped for %s — socket not connected", self.session_id)
            return False
        if not self.draft_logs:
            log.warning("share_draft_log skipped for %s — no draftLog payload stored", self.session_id)
            return False
        payload = next(iter(self.draft_logs.values()))
        try:
            await self.sio.emit("shareDraftLog", payload)
            log.info("shared draftLog for %s", self.session_id)
            return True
        except Exception:
            log.exception("shareDraftLog emit failed for %s", self.session_id)
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
        try:
            await self.sio.emit("setOwnerIsPlayer", True)
            await asyncio.sleep(1.0)
            await self.sio.emit("setSessionOwner", target_user_id)
            await asyncio.sleep(1.0)
            log.info("takeover transferred ownership of %s to %s", self.session_id, target_user_id)
        except Exception:
            log.exception("takeover transfer failed for %s", self.session_id)
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
        log.info("manager already active for event %s", event_id)
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
    Existing rows are left untouched (we never overwrite a manually-set arena_name)."""
    if not pairs:
        return
    with SessionLocal() as session:
        taken_slugs = set(session.execute(select(Player.slug)).scalars().all())
        for arena_name, member in pairs:
            discord_id = str(member.id)
            existing = session.execute(
                select(Player).where(Player.discord_id == discord_id)
            ).scalar_one_or_none()
            if existing is not None:
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
                active=True,
            ))
            log.info("auto-created Player row for guild member %s (arena=%s)", member.display_name, arena_name)
        session.commit()
