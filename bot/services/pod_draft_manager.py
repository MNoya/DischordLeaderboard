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

import socketio
from discord.ext import commands

from bot.config import settings


log = logging.getLogger(__name__)

ACTIVE_POD_MANAGERS: dict[str, "PodDraftManager"] = {}

_BACKOFF_BASE_S = 1.0
_BACKOFF_MAX_S = 30.0
_BACKOFF_MAX_RETRIES = 8
_BOT_USER_NAME = "DisChordBot"
_READY_TIMEOUT_S = 90
_START_DRAFT_DELAY_S = 1


class PodDraftManager:
    def __init__(self, bot: commands.Bot, event_id: str, session_id: str, thread_id: int,
                 set_code: str, expected_attendee_count: int) -> None:
        self.bot = bot
        self.event_id = event_id
        self.session_id = session_id
        self.thread_id = thread_id
        self.set_code = set_code
        self.expected_attendee_count = expected_attendee_count
        self.session_users: list[dict] = []
        self.bot_user_id: str | None = None
        self.owner_claimed = False
        self._closed = False
        self.ready_check_active = False
        self.ready_users: set[str] = set()
        self.expected_user_ids: set[str] = set()
        self.ready_status_message: object | None = None
        self._ready_timeout_task: asyncio.Task | None = None
        self.auto_ready_attempted = False
        self.auto_ready_disabled = False
        self._ready_check_is_auto = False
        self.drafting = False
        self.sio = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)
        self.sio.on("connect", self._on_connect)
        self.sio.on("disconnect", self._on_disconnect)
        self.sio.on("sessionUsers", self._on_session_users)
        self.sio.on("setReady", self._on_set_ready)
        self.sio.on("endDraft", self._on_end_draft)

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
        if self.bot_user_id is None:
            for u in self.session_users:
                if u.get("userName") == _BOT_USER_NAME:
                    self.bot_user_id = u.get("userID")
                    log.info("found bot userID=%s for %s", self.bot_user_id, self.session_id)
                    if not self.owner_claimed:
                        asyncio.create_task(self._claim_ownership_and_apply_settings())
                    break
        if self.ready_check_active:
            current = {u.get("userID") for u in self.session_users if u.get("userName") != _BOT_USER_NAME}
            if current != self.expected_user_ids:
                asyncio.create_task(self._invalidate_ready_check("player list changed"))
        elif not self.auto_ready_attempted and not self.auto_ready_disabled:
            non_bot_count = sum(1 for u in self.session_users if u.get("userName") != _BOT_USER_NAME)
            if non_bot_count >= max(1, self.expected_attendee_count):
                asyncio.create_task(self._auto_initiate_ready_check())

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
        from bot.database import SessionLocal
        from bot.models import PodDraftEvent
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
        try:
            await self.sio.emit("readyCheck")
        except Exception:
            self.ready_check_active = False
            log.exception("readyCheck emit failed for %s", self.session_id)
            return "Could not start ready check — see logs."
        try:
            self.ready_status_message = await thread.send(self._format_ready_status())
        except Exception:
            log.warning("could not post ready status message", exc_info=True)
        self._ready_timeout_task = asyncio.create_task(self._ready_timeout())
        return None

    def _format_ready_status(self) -> str:
        ready = len(self.ready_users)
        total = len(self.expected_user_ids)
        waiting_names = [u.get("userName") for u in self.session_users
                         if u.get("userID") in self.expected_user_ids
                         and u.get("userID") not in self.ready_users]
        if waiting_names:
            return f"🔔 Ready check: **{ready}/{total}** — waiting on: {', '.join(waiting_names)}"
        return f"🔔 Ready check: **{ready}/{total}**"

    async def _on_end_draft(self, *_) -> None:
        log.info("endDraft received for %s", self.session_id)
        self.drafting = False
        await self._mark_socket_status("draft_done")

    async def _on_set_ready(self, user_id, ready_state) -> None:
        if not self.ready_check_active:
            return
        ready = _is_ready_state(ready_state)
        if ready:
            self.ready_users.add(user_id)
        else:
            self.ready_users.discard(user_id)
            if self._ready_check_is_auto:
                # Auto-mode treats an explicit Not Ready as a decline — fall back to manual /ready
                await self._invalidate_ready_check("someone clicked Not Ready")
                return
        if self.ready_status_message is not None:
            try:
                await self.ready_status_message.edit(content=self._format_ready_status())
            except Exception:
                log.warning("ready status edit failed", exc_info=True)
        if self.ready_users >= self.expected_user_ids:
            await self._complete_ready_check()

    async def _complete_ready_check(self) -> None:
        if not self.ready_check_active:
            return
        self.ready_check_active = False
        self._ready_check_is_auto = False
        if self._ready_timeout_task is not None:
            self._ready_timeout_task.cancel()
        channel = self.ready_status_message.channel if self.ready_status_message else None
        await asyncio.sleep(_START_DRAFT_DELAY_S)
        await self._start_draft(channel)

    async def _start_draft(self, channel) -> None:
        result = await self._emit_with_ack("startDraft")
        log.info("startDraft ack for %s: %r", self.session_id, result)
        error_text = _ack_error_text(result)
        if error_text is not None:
            if channel is not None:
                try:
                    await channel.send(
                        f"⚠️ Could not start the draft: {error_text}\n"
                        f"Use `/pod-takeover` to take control of the Draftmancer session manually."
                    )
                except Exception:
                    log.warning("could not post startDraft error", exc_info=True)
            return
        self.drafting = True
        if channel is not None:
            try:
                await channel.send("🎉 All players ready — draft started!")
            except Exception:
                log.warning("could not post draft-started message", exc_info=True)

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

    async def _invalidate_ready_check(self, reason: str) -> None:
        if not self.ready_check_active:
            return
        self.ready_check_active = False
        self.ready_users = set()
        self._ready_check_is_auto = False
        if self._ready_timeout_task is not None:
            self._ready_timeout_task.cancel()
        # If the failed check was the auto one, never auto-trigger again — fall back to manual /ready
        if self.auto_ready_attempted:
            self.auto_ready_disabled = True
        if self.ready_status_message is not None:
            try:
                await self.ready_status_message.channel.send(
                    f"⚠️ Ready check cancelled — {reason}. Run `/ready` to retry."
                )
            except Exception:
                log.warning("could not post invalidation message", exc_info=True)

    async def _auto_initiate_ready_check(self) -> None:
        if self.ready_check_active or self.auto_ready_attempted or self.auto_ready_disabled:
            return
        self.auto_ready_attempted = True
        thread = await self.bot.fetch_channel(self.thread_id)
        log.info("auto-initiating ready check for %s (expected=%d, joined=%d)",
                 self.session_id, self.expected_attendee_count,
                 sum(1 for u in self.session_users if u.get("userName") != _BOT_USER_NAME))
        err = await self.initiate_ready_check(thread)
        if err is not None:
            log.warning("auto-ready failed for %s: %s", self.session_id, err)
            self.auto_ready_disabled = True
        else:
            self._ready_check_is_auto = True


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
    set_code: str, expected_attendee_count: int,
) -> PodDraftManager | None:
    existing = ACTIVE_POD_MANAGERS.get(event_id)
    if existing is not None:
        log.info("manager already active for event %s", event_id)
        return existing
    manager = PodDraftManager(bot, event_id, session_id, thread_id, set_code, expected_attendee_count)
    ACTIVE_POD_MANAGERS[event_id] = manager
    ok = await manager.connect()
    if not ok:
        ACTIVE_POD_MANAGERS.pop(event_id, None)
        await manager._mark_socket_status("error")
        return None
    return manager
