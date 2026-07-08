"""/pod-split — open an overflow "Table N" pod for a full lobby, with no sesh RSVP.

Players claim a seat on a button; once the threshold is reached the bot clones the source pod into a
new event, opens a Draftmancer lobby in a fresh thread, pings the claimers in, and hands off to the
ordinary tournament path. The claim list lives in memory on the view — a mid-gather restart just
means re-running the command.

`build_split_view` is the single entry point the slash command and the `!test split` preview both
call, so the claim card, materialize flow, and lobby copy never diverge between them.
"""
from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import audit, emojis
from bot.commands import descriptions as desc
from bot.commands.messages import (
    MSG_ADMIN_ONLY,
    MSG_SPLIT_BUTTON,
    MSG_SPLIT_CREATED,
    MSG_SPLIT_GATHERING,
    MSG_SPLIT_GOTO,
    MSG_SPLIT_INTRO,
    MSG_SPLIT_JOINED,
    MSG_SPLIT_LOBBY_STARTER,
    MSG_SPLIT_NO_SOURCE,
    MSG_SPLIT_UNKNOWN_EVENT,
)
from bot.config import settings
from bot.database import SessionLocal
from bot.models import PodDraftEvent
from bot.services.pod_draft_manager import start_manager
from bot.services.pod_drafts import (
    draftmancer_url_for,
    load_event_id_by_name_sync,
    load_event_id_by_thread_sync,
    load_event_thread_id_sync,
    preview_split_target_sync,
    record_split_event,
    search_event_names_sync,
)


log = logging.getLogger(__name__)


def _mention_block(claims: dict[int, str]) -> str:
    """Space-joined mentions for joiners with a real Discord id, used to pull them into the new thread.
    Fixture joiners (negative ids used by `!test split`) fall back to their plain name."""
    parts = []
    for user_id, name in claims.items():
        parts.append(f"<@{user_id}>" if user_id > 0 else name)
    return " ".join(parts)


async def materialize_table2(
    bot: commands.Bot, source_event_id: str, lobby_channel: discord.abc.Messageable, claims: dict[int, str],
) -> discord.Thread:
    """Clone the source pod into a live table: new event row, thread, Draftmancer lobby. Pings the
    joiners to pull them into the thread, then starts the ordinary tournament manager, which posts the
    live lobby card with the join link. Returns the created thread."""
    with SessionLocal() as session:
        event = record_split_event(session, source_event_id=source_event_id)
        event_id, session_id, event_name, set_code = (
            event.id, event.draftmancer_session, event.name, event.set_code,
        )
        session.commit()

    draftmancer_url = draftmancer_url_for(session_id)
    starter = await lobby_channel.send(MSG_SPLIT_LOBBY_STARTER.format(
        draftmancer_emoji=emojis.get("draftmancer"), event_name=event_name,
    ))
    thread = await starter.create_thread(name=event_name, reason="Pod split table")

    with SessionLocal() as session:
        session.get(PodDraftEvent, event_id).discord_thread_id = str(thread.id)
        session.commit()

    mention_block = _mention_block(claims)
    if mention_block:
        await thread.send(mention_block, allowed_mentions=discord.AllowedMentions(users=True))

    await start_manager(
        bot, event_id, session_id, thread.id, set_code, len(claims),
        event_name=event_name, draftmancer_url=draftmancer_url,
    )
    log.info(f"pod-split: materialized {event_name} event={event_id} session={session_id} joined={len(claims)}")
    return thread


class Table2ClaimView(discord.ui.View):
    """The join card. Below the threshold, clicking toggles a spot; the (threshold)th distinct joiner
    opens the table. Once open, the button turns into a link to the new thread."""

    def __init__(
        self, bot: commands.Bot, source_event_id: str, *, table_index: int, source_name: str,
        threshold: int, lobby_channel: discord.abc.Messageable,
        preseeded_claims: list[tuple[int, str]] | None = None,
    ) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.source_event_id = source_event_id
        self.table_index = table_index
        self.source_name = source_name
        self.threshold = threshold
        self.lobby_channel = lobby_channel
        self.claims: dict[int, str] = dict(preseeded_claims or [])
        self.materialized = False
        self.thread: discord.Thread | None = None
        self.claim_message: discord.Message | None = None
        self._lock = asyncio.Lock()

        self._join_button = discord.ui.Button(
            label=MSG_SPLIT_BUTTON.format(table=table_index), style=discord.ButtonStyle.primary, emoji="🪑",
        )
        self._join_button.callback = self._on_claim
        self.add_item(self._join_button)

    def render_embed(self) -> discord.Embed:
        name = f"{self.source_name} - Table {self.table_index}"
        open_now = self.materialized and self.thread is not None
        if open_now:
            title = MSG_SPLIT_CREATED.format(name=name)
            description = MSG_SPLIT_INTRO
        else:
            title = name
            description = f"{MSG_SPLIT_INTRO}\n\n{MSG_SPLIT_GATHERING.format(threshold=self.threshold)}"
        embed = discord.Embed(color=discord.Color.green(), title=title, description=description)
        if self.claims:
            embed.add_field(
                name=MSG_SPLIT_JOINED.format(count=len(self.claims)),
                value=", ".join(self.claims.values()), inline=False,
            )
        return embed

    async def _on_claim(self, interaction: discord.Interaction) -> None:
        if self.materialized:
            await interaction.response.defer()
            return
        user_id = interaction.user.id
        if user_id in self.claims:
            del self.claims[user_id]
        else:
            self.claims[user_id] = interaction.user.display_name
        await interaction.response.edit_message(embed=self.render_embed(), view=self)
        if len(self.claims) >= self.threshold:
            await self._materialize()

    async def _materialize(self) -> None:
        async with self._lock:
            if self.materialized:
                return
            self.materialized = True
            self.thread = await materialize_table2(
                self.bot, self.source_event_id, self.lobby_channel, dict(self.claims),
            )
            self.remove_item(self._join_button)
            self.add_item(discord.ui.Button(
                label=MSG_SPLIT_GOTO.format(table=self.table_index),
                style=discord.ButtonStyle.link, url=self.thread.jump_url,
            ))
            if self.claim_message is not None:
                await self.claim_message.edit(embed=self.render_embed(), view=self)


async def build_split_view(
    bot: commands.Bot, source_event_id: str, *, lobby_channel: discord.abc.Messageable,
    preseeded_claims: list[tuple[int, str]] | None = None,
) -> "Table2ClaimView | None":
    """Build the join card view for a new table off `source_event_id`, or None when the source event
    has vanished. The caller posts it and assigns the resulting message to `view.claim_message` — the
    slash command posts it as a public interaction response, `!test split` via a channel send."""
    preview = await asyncio.to_thread(preview_split_target_sync, source_event_id)
    if preview is None:
        return None
    source_name, table_index = preview
    return Table2ClaimView(
        bot, source_event_id, table_index=table_index, source_name=source_name,
        threshold=settings.pod_split_open_threshold, lobby_channel=lobby_channel,
        preseeded_claims=preseeded_claims,
    )


class PodSplit(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="pod-split", description=desc.POD_SPLIT)
    @app_commands.describe(event="Pod to split from; defaults to the current thread")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_split(self, interaction: discord.Interaction, event: str | None = None) -> None:
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(MSG_ADMIN_ONLY, ephemeral=True)
            return

        source_id = await self._resolve_source(interaction, event)
        if source_id is None:
            message = MSG_SPLIT_UNKNOWN_EVENT.format(event=event) if event else MSG_SPLIT_NO_SOURCE
            await interaction.response.send_message(message, ephemeral=True)
            return

        lobby_channel = await self._resolve_lobby_channel(source_id, interaction)
        view = await build_split_view(self.bot, source_id, lobby_channel=lobby_channel)
        if view is None:
            await interaction.response.send_message(MSG_SPLIT_NO_SOURCE, ephemeral=True)
            return

        audit.event("pod_split_invoked", user_id=str(interaction.user.id), source_event_id=source_id)
        await interaction.response.send_message(embed=view.render_embed(), view=view)
        view.claim_message = await interaction.original_response()

    async def _resolve_source(self, interaction: discord.Interaction, event: str | None) -> str | None:
        if event:
            return await asyncio.to_thread(load_event_id_by_name_sync, event)
        channel = interaction.channel
        if not isinstance(channel, discord.Thread):
            return None
        return await asyncio.to_thread(load_event_id_by_thread_sync, str(channel.id))

    async def _resolve_lobby_channel(
        self, source_event_id: str, interaction: discord.Interaction,
    ) -> discord.abc.Messageable:
        """The channel the Table N thread hangs off — the source pod's parent channel so the overflow
        table sits beside Table 1, falling back to wherever the command ran."""
        thread_id = await asyncio.to_thread(load_event_thread_id_sync, source_event_id)
        if thread_id is not None and thread_id != "pending":
            source_thread = interaction.guild.get_thread(int(thread_id)) if interaction.guild else None
            if source_thread is not None and source_thread.parent is not None:
                return source_thread.parent
        channel = interaction.channel
        if isinstance(channel, discord.Thread) and channel.parent is not None:
            return channel.parent
        return channel

    @pod_split.autocomplete("event")
    async def _event_autocomplete(
        self, interaction: discord.Interaction, current: str,
    ) -> list[app_commands.Choice[str]]:
        names = await asyncio.to_thread(search_event_names_sync, current)
        return [app_commands.Choice(name=n, value=n) for n in names]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PodSplit(bot))
