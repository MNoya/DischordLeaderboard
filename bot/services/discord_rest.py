"""Gateway-free Discord REST calls for the standalone refresh cron job.

The cron refresh has no live gateway connection, so it posts its bot-spam report
and invalidation DMs straight through Discord's HTTP API using the bot token.
"""
from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://discord.com/api/v10"
MESSAGE_MAX_CHARS = 1900


class DiscordRest:
    def __init__(self, bot_token: str, timeout_s: float = 15.0) -> None:
        self._headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
        }
        self.timeout_s = timeout_s

    def post_channel_message(self, channel_id: int, content: str) -> bool:
        return self._send(channel_id, content)

    def send_dm(self, user_id: int, content: str) -> bool:
        try:
            resp = requests.post(
                f"{API_BASE}/users/@me/channels",
                headers=self._headers,
                json={"recipient_id": str(user_id)},
                timeout=self.timeout_s,
            )
        except requests.RequestException:
            logger.warning(f"could not open DM channel for user {user_id}", exc_info=True)
            return False
        if resp.status_code != 200:
            logger.warning(f"could not open DM channel for user {user_id}: {resp.status_code}")
            return False
        return self._send(resp.json()["id"], content)

    def _send(self, channel_id: int | str, content: str) -> bool:
        if len(content) > MESSAGE_MAX_CHARS:
            content = content[:MESSAGE_MAX_CHARS]
        try:
            resp = requests.post(
                f"{API_BASE}/channels/{channel_id}/messages",
                headers=self._headers,
                json={"content": content},
                timeout=self.timeout_s,
            )
        except requests.RequestException:
            logger.warning(f"discord message send to {channel_id} failed", exc_info=True)
            return False
        if resp.status_code not in (200, 201):
            logger.warning(f"discord message send to {channel_id} failed: {resp.status_code} {resp.text[:200]}")
            return False
        return True
