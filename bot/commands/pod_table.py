"""/pod-table — open another "Table N" draft off an existing pod, with no sesh RSVP.

Serves both an overflow table for a full lobby and a rematch table for players wanting another go.
Players claim a seat on a button; once the threshold is reached the bot clones the source pod into a
new event, opens a Draftmancer lobby in a fresh thread, pings the claimers in, and hands off to the
ordinary tournament path. The claim list lives in memory on the view — a mid-gather restart just
means re-running the command.

`build_table_view` is the single entry point the slash command and the `!test table` preview both
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
    MSG_TABLE_BUTTON,
    MSG_TABLE_CREATED,
    MSG_TABLE_GATHERING,
    MSG_TABLE_GOTO,
    MSG_TABLE_INTRO,
    MSG_TABLE_JOINED,
    MSG_TABLE_LOBBY_STARTER,
    MSG_TABLE_NO_SOURCE,
    MSG_TABLE_SUPERSEDED,
    MSG_TABLE_UNKNOWN_EVENT,
)
from bot.config import settings
from bot.database import SessionLocal
from bot.models import PodDraftEvent
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_draft_manager import start_manager
from bot.services.pod_drafts import (
    draftmancer_url_for,
    load_event_id_by_name_sync,
    load_event_id_by_thread_sync,
    load_event_thread_id_sync,
    preview_table_target_sync,
    record_table_event,
    search_event_names_sync,
)


log = logging.getLogger(__name__)

ACTIVE_TABLE_VIEWS: dict[str, "TableClaimView"] = {}


def _mention_block(claims: dict[int, str]) -> str:
    """Space-joined mentions for joiners with a real Discord id, used to pull them into the new thread.
    Fixture joiners (negative ids used by `!test table`) fall back to their plain name."""
    parts = []
    for user_id, name in claims.items():
        parts.append(f"<@{user_id}>" if user_id > 0 else name)
    return " ".join(parts)


async def materialize_table(
    bot: commands.Bot, source_event_id: str, lobby_channel: discord.abc.Messageable, claims: dict[int, str],
) -> discord.Thread:
    """Clone the source pod into a live table: new event row, thread, Draftmancer lobby. Pings the
    joiners to pull them into the thread, then starts the ordinary tournament manager, which posts the
    live lobby card with the join link. Returns the created thread."""
    with SessionLocal() as session:
        event = record_table_event(session, source_event_id=source_event_id)
        event_id, session_id, event_name, set_code = (
            event.id, event.draftmancer_session, event.name, event.set_code,
        )
        session.commit()

    draftmancer_url = draftmancer_url_for(session_id)
    starter = await lobby_channel.send(MSG_TABLE_LOBBY_STARTER.format(
        draftmancer_emoji=emojis.get("draftmancer"), event_name=event_name,
    ))
    thread = await starter.create_thread(name=event_name, reason="Pod table")

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
    log.info(f"pod-table: materialized {event_name} event={event_id} session={session_id} joined={len(claims)}")
    manager = ACTIVE_POD_MANAGERS.get(event_id)
    if manager is not None:
        manager.arm_team_vote_offer(len(claims))
    return thread


class TableClaimView(discord.ui.View):
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
        self.superseded = False
        self.thread: discord.Thread | None = None
        self.claim_message: discord.Message | None = None
        self._lock = asyncio.Lock()

        self._join_button = discord.ui.Button(
            label=MSG_TABLE_BUTTON.format(table=table_index), style=discord.ButtonStyle.primary, emoji="🪑",
        )
        self._join_button.callback = self._on_claim
        self.add_item(self._join_button)

    def render_embed(self) -> discord.Embed:
        name = f"{self.source_name} - Table {self.table_index}"
        open_now = self.materialized and self.thread is not None
        if self.superseded:
            title = name
            description = MSG_TABLE_SUPERSEDED.format(table=self.table_index)
        elif open_now:
            title = MSG_TABLE_CREATED.format(name=name)
            description = MSG_TABLE_INTRO
        else:
            title = name
            description = f"{MSG_TABLE_INTRO}\n\n{MSG_TABLE_GATHERING.format(threshold=self.threshold)}"
        embed = discord.Embed(color=discord.Color.green(), title=title, description=description)
        if self.claims:
            embed.add_field(
                name=MSG_TABLE_JOINED.format(count=len(self.claims)),
                value=", ".join(self.claims.values()), inline=False,
            )
        return embed

    async def activate(self) -> None:
        """Register this card as the live table for its source, retiring any earlier live card first so a
        re-run of `/pod-table` leaves exactly one joinable table per source. Call after `claim_message`
        is set — the retire step edits the prior card."""
        prior = ACTIVE_TABLE_VIEWS.get(self.source_event_id)
        if prior is not None and prior is not self:
            await prior._supersede()
        ACTIVE_TABLE_VIEWS[self.source_event_id] = self

    async def _supersede(self) -> None:
        async with self._lock:
            if self.materialized or self.superseded:
                return
            self.superseded = True
            self._join_button.disabled = True
        await self._edit_card()

    async def _edit_card(self) -> None:
        """Edit the posted claim card through the bot token rather than the command's interaction
        webhook, so the swap lands even past the interaction token's 15-minute expiry."""
        if self.claim_message is None:
            return
        editable = self.claim_message.channel.get_partial_message(self.claim_message.id)
        await editable.edit(embed=self.render_embed(), view=self)

    async def _on_claim(self, interaction: discord.Interaction) -> None:
        if self.materialized or self.superseded:
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
            self.thread = await materialize_table(
                self.bot, self.source_event_id, self.lobby_channel, dict(self.claims),
            )
            self.remove_item(self._join_button)
            self.add_item(discord.ui.Button(
                label=MSG_TABLE_GOTO.format(table=self.table_index),
                style=discord.ButtonStyle.link, url=self.thread.jump_url,
            ))
            if ACTIVE_TABLE_VIEWS.get(self.source_event_id) is self:
                del ACTIVE_TABLE_VIEWS[self.source_event_id]
            await self._edit_card()


async def build_table_view(
    bot: commands.Bot, source_event_id: str, *, lobby_channel: discord.abc.Messageable,
    preseeded_claims: list[tuple[int, str]] | None = None,
) -> "TableClaimView | None":
    """Build the join card view for a new table off `source_event_id`, or None when the source event
    has vanished. The caller posts it and assigns the resulting message to `view.claim_message` — the
    slash command posts it as a public interaction response, `!test table` via a channel send."""
    preview = await asyncio.to_thread(preview_table_target_sync, source_event_id)
    if preview is None:
        return None
    source_name, table_index = preview
    return TableClaimView(
        bot, source_event_id, table_index=table_index, source_name=source_name,
        threshold=settings.pod_table_open_threshold, lobby_channel=lobby_channel,
        preseeded_claims=preseeded_claims,
    )


class PodTable(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="pod-table", description=desc.POD_TABLE)
    @app_commands.describe(event="Pod to base the new table on; defaults to the current thread")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_table(self, interaction: discord.Interaction, event: str | None = None) -> None:
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(MSG_ADMIN_ONLY, ephemeral=True)
            return

        source_id = await self._resolve_source(interaction, event)
        if source_id is None:
            message = MSG_TABLE_UNKNOWN_EVENT.format(event=event) if event else MSG_TABLE_NO_SOURCE
            await interaction.response.send_message(message, ephemeral=True)
            return

        lobby_channel = await self._resolve_lobby_channel(source_id, interaction)
        view = await build_table_view(self.bot, source_id, lobby_channel=lobby_channel)
        if view is None:
            await interaction.response.send_message(MSG_TABLE_NO_SOURCE, ephemeral=True)
            return

        audit.event("pod_table_invoked", user_id=str(interaction.user.id), source_event_id=source_id)
        await interaction.response.send_message(embed=view.render_embed(), view=view)
        view.claim_message = await interaction.original_response()
        await view.activate()

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

    @pod_table.autocomplete("event")
    async def _event_autocomplete(
        self, interaction: discord.Interaction, current: str,
    ) -> list[app_commands.Choice[str]]:
        names = await asyncio.to_thread(search_event_names_sync, current)
        return [app_commands.Choice(name=n, value=n) for n in names]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PodTable(bot))
