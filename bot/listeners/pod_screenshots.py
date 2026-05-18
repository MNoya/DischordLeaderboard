"""Capture the first image a participant posts in a pod-draft thread → stash on participant row.

On capture we trigger _announce_or_update_champion so the announcement (Components V2 layout)
either posts for the first time (rank-1 screenshot is the trigger) or edits in place with the
new image / caption. If the author is a champion, we also react 🏆 on the message itself.
"""
from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from bot.database import SessionLocal
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_drafts import (
    active_event_for_discord_user_in_dm,
    capture_first_deck_screenshot,
    is_pod_thread_champion,
)
from bot.services.pod_tournament import _announce_or_update_champion


log = logging.getLogger(__name__)


class PodScreenshotListener(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        image_url = _first_image_url(message)
        if image_url is None:
            return

        if isinstance(message.channel, discord.DMChannel):
            await self._redirect_dm_image(message)
            return

        if not isinstance(message.channel, discord.Thread):
            return

        thread_id = str(message.channel.id)
        discord_id = str(message.author.id)
        caption = (message.content or "").strip() or None

        event_id = await asyncio.to_thread(_capture_sync, thread_id, discord_id, image_url, caption)

        is_champion_in_memory = False
        if event_id is not None:
            manager = ACTIVE_POD_MANAGERS.get(event_id)
            if manager is not None:
                await _announce_or_update_champion(manager)
                is_champion_in_memory = discord_id in manager.champion_discord_ids

        is_champion_in_db = await asyncio.to_thread(_is_thread_champion_sync, thread_id, discord_id)
        if is_champion_in_memory or is_champion_in_db:
            try:
                await message.add_reaction("🏆")
            except discord.HTTPException:
                log.info("could not add 🏆 reaction", exc_info=True)

    async def _redirect_dm_image(self, message: discord.Message) -> None:
        """User posted an image in DM — point them at the pod thread so the screenshot is publicly
        viewable. DM CDN URLs carry signed expiries and aren't reliably embeddable on the frontend."""
        discord_id = str(message.author.id)
        target = await asyncio.to_thread(_resolve_active_pod_thread_sync, discord_id)
        if target is None:
            return
        _event_id, thread_id = target
        try:
            thread = self.bot.get_channel(int(thread_id)) or await self.bot.fetch_channel(int(thread_id))
            link = thread.jump_url
        except discord.HTTPException:
            return
        try:
            await message.reply(
                f"📸 Post your deck screenshot in the pod-draft thread so everyone can see it: {link}"
            )
        except discord.HTTPException:
            log.warning("could not reply to DM image", exc_info=True)


def _first_image_url(message: discord.Message) -> str | None:
    for att in message.attachments:
        ct = (att.content_type or "").lower()
        if ct.startswith("image/"):
            return att.url
    return None


def _capture_sync(thread_id: str, discord_id: str, image_url: str, caption: str | None) -> str | None:
    with SessionLocal() as session:
        event_id = capture_first_deck_screenshot(session, thread_id, discord_id, image_url, caption)
        if event_id is not None:
            session.commit()
        return event_id


def _is_thread_champion_sync(thread_id: str, discord_id: str) -> bool:
    with SessionLocal() as session:
        return is_pod_thread_champion(session, thread_id, discord_id)


def _resolve_active_pod_thread_sync(discord_id: str) -> tuple[str, str] | None:
    with SessionLocal() as session:
        return active_event_for_discord_user_in_dm(session, discord_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PodScreenshotListener(bot))
