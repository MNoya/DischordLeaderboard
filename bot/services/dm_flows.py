"""Shared helpers for DM-driven token flows (/join, /link-17lands).

`is_in_flight` lets the auto-link DM listener skip a reply that an active
slash-command wait_for will already consume. `run_latest_flow` makes a fresh
invocation cancel any in-progress flow for the same user (newest wins).
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Awaitable

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

IN_FLIGHT_DM_FLOWS: set[str] = set()
ACTIVE_FLOW_TASKS: dict[str, asyncio.Task] = {}

INSTRUCTIONS_IMAGE = Path(__file__).resolve().parents[2] / "bot" / "assets" / "signup_event_history.png"


async def send_token_instructions(send, content: str) -> None:
    """Send walkthrough `content` via `send`, attaching the 17lands event-history screenshot when present.

    Falls back to text-only when the image is missing or the upload is rejected; re-raises Forbidden so
    the caller can surface the DMs-blocked path.
    """
    if INSTRUCTIONS_IMAGE.exists():
        try:
            await send(content=content, file=discord.File(INSTRUCTIONS_IMAGE))
            return
        except discord.Forbidden:
            raise
        except discord.HTTPException as exc:
            logger.warning(f"token instructions attachment failed ({exc}); text-only")
    await send(content)


@contextmanager
def dm_flow(discord_id: str):
    IN_FLIGHT_DM_FLOWS.add(discord_id)
    try:
        yield
    finally:
        IN_FLIGHT_DM_FLOWS.discard(discord_id)


def is_in_flight(discord_id: str) -> bool:
    if discord_id in IN_FLIGHT_DM_FLOWS:
        return True
    task = ACTIVE_FLOW_TASKS.get(discord_id)
    return task is not None and not task.done()


async def run_latest_flow(discord_id: str, coro: Awaitable[None]) -> None:
    """Run a DM flow, cancelling any in-progress flow for the same user first (newest wins)."""
    previous = ACTIVE_FLOW_TASKS.get(discord_id)
    if previous is not None and not previous.done():
        previous.cancel()
    task = asyncio.ensure_future(coro)
    ACTIVE_FLOW_TASKS[discord_id] = task
    try:
        await task
    except asyncio.CancelledError:
        pass
    finally:
        if ACTIVE_FLOW_TASKS.get(discord_id) is task:
            ACTIVE_FLOW_TASKS.pop(discord_id, None)


async def wait_for_token_reply(
    bot: commands.Bot, interaction: discord.Interaction, *, timeout_s: float,
) -> str | None:
    """Wait for the invoker's next DM and return its text, or None on timeout."""
    def is_user_dm(m: discord.Message) -> bool:
        return m.author.id == interaction.user.id and m.guild is None

    try:
        reply = await bot.wait_for("message", check=is_user_dm, timeout=timeout_s)
    except asyncio.TimeoutError:
        return None
    return reply.content
