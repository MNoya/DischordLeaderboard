"""Print the raw embed JSON for a Discord message. One-shot dev tool.

    DISCORD_BOT_TOKEN=... python -m bot.scripts.dump_message_embed \\
        <channel_id> <message_id>
"""
from __future__ import annotations

import asyncio
import json
import sys

import discord

from bot.config import settings


async def main(channel_id: int, message_id: int) -> None:
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        channel = await client.fetch_channel(channel_id)
        message = await channel.fetch_message(message_id)
        print(json.dumps({
            "message_id": str(message.id),
            "author_id": str(message.author.id),
            "author_name": str(message.author),
            "content": message.content,
            "embeds": [e.to_dict() for e in message.embeds],
            "thread": (
                {"id": str(message.thread.id), "name": message.thread.name}
                if message.thread else None
            ),
        }, indent=2, ensure_ascii=False))
        await client.close()

    await client.start(settings.discord_bot_token.get_secret_value())


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    asyncio.run(main(int(sys.argv[1]), int(sys.argv[2])))
