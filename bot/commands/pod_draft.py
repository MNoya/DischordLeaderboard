"""Pod-draft slash commands."""
from __future__ import annotations

import asyncio
import logging
import re

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import any_, select

from bot import audit, emojis
from bot.database import SessionLocal
from bot.discord_helpers import extract_avatar_hash
from bot.models import Player
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_drafts import _normalize_player_name
from bot.services.pod_tournament import (
    _load_event_id_by_name_sync,
    _load_event_id_by_thread_sync,
    _load_event_name_sync,
    _load_event_thread_id_sync,
    _search_event_names_sync,
    build_champion_announcement_view_for_event,
    build_replays_link_button,
    build_standings_embed_for_event,
    build_thread_link_button,
)
from bot.slug import disambiguate_slug, slugify


log = logging.getLogger(__name__)

_ARENA_INPUT_RE = re.compile(r"^.+#\d+$")



class PodDraft(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ready", description="Run a Draftmancer ready check for this pod draft")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_ready(self, interaction: discord.Interaction) -> None:
        manager = _find_manager_for_thread(interaction)
        if manager is None:
            await interaction.response.send_message(
                "No active pod draft session right now.",
                ephemeral=True,
            )
            return
        thread = interaction.channel
        log.info(f"ready-check: {interaction.user} in thread {interaction.channel_id}")
        await interaction.response.defer(ephemeral=True, thinking=False)
        err = await manager.initiate_ready_check(thread)
        if err is not None:
            log.warning(f"ready-check: failed — {err}")
            await interaction.followup.send(f"⚠️ {err}", ephemeral=True)
        else:
            await interaction.followup.send("Ready check started — watch the thread for status.", ephemeral=True)

    @app_commands.command(
        name="pod-link-arena",
        description="Link your MTG Arena handle so pod-draft results recognize you",
    )
    @app_commands.describe(name="Your full MTG Arena handle: ArenaID#12345")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_link_arena(self, interaction: discord.Interaction, name: str) -> None:
        user_id = str(interaction.user.id)
        arena_name = name.strip()
        mention = interaction.user.mention
        audit.event("pod_link_arena_invoked", user_id=user_id, arena_name=arena_name)
        no_pings = discord.AllowedMentions(users=False, everyone=False, roles=False)

        if not _ARENA_INPUT_RE.match(arena_name):
            audit.event("pod_link_arena_bad_format", user_id=user_id, arena_name=arena_name)
            await interaction.response.send_message(
                "❌ Use the full MTG Arena handle: `ArenaID#12345`",
                ephemeral=True,
            )
            return

        normalized = _normalize_player_name(arena_name)

        with SessionLocal() as session:
            collision = session.execute(
                select(Player)
                .where(
                    Player.active.is_(True),
                    Player.discord_id != user_id,
                    normalized == any_(Player.arena_aliases),
                )
                .limit(1)
            ).scalar_one_or_none()
            if collision is not None:
                audit.event("pod_link_arena_collision", user_id=user_id, arena_name=arena_name,
                            collides_with=collision.id)
                await interaction.response.send_message(
                    f"❌ `{arena_name}` is already linked to another player. "
                    "If this is your account, ask an admin for help.",
                    ephemeral=True,
                )
                return

            player = session.execute(
                select(Player).where(Player.discord_id == user_id)
            ).scalar_one_or_none()
            if player is None:
                taken_slugs = set(session.execute(select(Player.slug)).scalars().all())
                slug = disambiguate_slug(slugify(interaction.user.display_name), taken_slugs)
                player = Player(
                    slug=slug,
                    discord_id=user_id,
                    discord_username=interaction.user.name,
                    display_name=interaction.user.display_name,
                    avatar_hash=extract_avatar_hash(interaction.user),
                    arena_name=arena_name,
                    arena_aliases=[normalized],
                    active=True,
                )
                session.add(player)
            else:
                if not (player.arena_name or "").strip():
                    player.arena_name = arena_name
                if normalized not in player.arena_aliases:
                    player.arena_aliases = [*player.arena_aliases, normalized]
            session.flush()
            player_id = player.id
            session.commit()

        audit.event("pod_link_arena_success", user_id=user_id, player_id=player_id)
        log.info(f"pod-link-arena: {interaction.user} linked {arena_name} (player_id={player_id})")
        await interaction.response.send_message(
            f"{emojis.get('mtga')} {mention} is **{arena_name}** on Arena.",
            allowed_mentions=no_pings,
        )

        for manager in list(ACTIVE_POD_MANAGERS.values()):
            asyncio.create_task(manager.refresh_lobby_now())

    @app_commands.command(
        name="pod-draft-standings",
        description="Post the standings embed for a pod-draft event",
    )
    @app_commands.describe(event="Pick an event to publish standings for; defaults to the current thread")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_draft_standings(self, interaction: discord.Interaction, event: str | None = None) -> None:
        await interaction.response.defer(thinking=False)

        if event:
            event_id = await asyncio.to_thread(_load_event_id_by_name_sync, event)
            if event_id is None:
                await interaction.followup.send(f"No pod-draft event named `{event}`.", ephemeral=True)
                return
        else:
            channel = interaction.channel
            thread_id = str(channel.id) if channel is not None else None
            event_id = await asyncio.to_thread(_load_event_id_by_thread_sync, thread_id) if thread_id else None
            if event_id is None:
                await interaction.followup.send(
                    "Run this inside a pod-draft thread, or pass an `event` to publish standings for a specific pod.",
                    ephemeral=True,
                )
                return

        embed = await build_standings_embed_for_event(event_id)
        if embed is None:
            await interaction.followup.send("No standings yet — this pod hasn't started pairings.", ephemeral=True)
            return

        log.info(f"pod-standings: {interaction.user} posted standings for event_id={event_id}")
        thread_id = await asyncio.to_thread(_load_event_thread_id_sync, event_id)
        invoked_outside_thread = thread_id is not None and str(interaction.channel_id) != thread_id
        event_name = await asyncio.to_thread(_load_event_name_sync, event_id)

        view = discord.ui.View()
        if invoked_outside_thread and interaction.guild_id is not None:
            view.add_item(build_thread_link_button(interaction.guild_id, thread_id))
        view.add_item(build_replays_link_button(event_name))

        await interaction.followup.send(embed=embed, view=view)

    @pod_draft_standings.autocomplete("event")
    async def _pod_draft_standings_event_autocomplete(
        self, interaction: discord.Interaction, current: str,
    ) -> list[app_commands.Choice[str]]:
        names = await asyncio.to_thread(_search_event_names_sync, current)
        return [app_commands.Choice(name=n, value=n) for n in names]

    @app_commands.command(
        name="pod-champion",
        description="Re-post the champion announcement for a completed pod-draft event",
    )
    @app_commands.describe(event="Pod-draft event to announce")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_champion(self, interaction: discord.Interaction, event: str) -> None:
        await interaction.response.defer(thinking=False)

        event_id = await asyncio.to_thread(_load_event_id_by_name_sync, event)
        if event_id is None:
            await interaction.followup.send(f"No pod-draft event named `{event}`.", ephemeral=True)
            return

        view = await build_champion_announcement_view_for_event(
            event_id, guild_id=interaction.guild_id,
        )
        if view is None:
            await interaction.followup.send(
                "Champion announcement isn't ready — trophy match has no winner on record yet.",
                ephemeral=True,
            )
            return

        log.info(f"pod-champion: {interaction.user} re-posted champion announcement for event_id={event_id}")
        await interaction.followup.send(view=view)

    @pod_champion.autocomplete("event")
    async def _pod_champion_event_autocomplete(
        self, interaction: discord.Interaction, current: str,
    ) -> list[app_commands.Choice[str]]:
        names = await asyncio.to_thread(_search_event_names_sync, current)
        return [app_commands.Choice(name=n, value=n) for n in names]

    @app_commands.command(name="pod-takeover", description="Take control of the Draftmancer session and disconnect the bot")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_takeover(self, interaction: discord.Interaction) -> None:
        manager = _find_manager_for_thread(interaction)
        if manager is None:
            await interaction.response.send_message("No active pod draft session right now.", ephemeral=True)
            return

        target = _pick_takeover_target(manager, interaction.user.display_name)
        if target is None:
            await interaction.response.send_message(
                "No suitable Draftmancer user found to transfer ownership to. "
                "Make sure you're in the Draftmancer session before running this.",
                ephemeral=True,
            )
            return
        target_user_id, target_user_name = target

        log.info(f"pod-takeover: {interaction.user} → {target_user_name}")
        await interaction.response.defer(ephemeral=False, thinking=False)
        ok, err = await manager.takeover(target_user_id)
        if not ok:
            log.warning(f"pod-takeover: failed — {err}")
            await interaction.followup.send(f"⚠️ Takeover failed: {err}", ephemeral=True)
            return
        await interaction.followup.send(
            f"👑 {interaction.user.mention} is now in control of the Draftmancer session. Bot disconnected."
        )


def _pick_takeover_target(manager, invoker_display_name: str):
    """Prefer the invoker by display_name match; else any non-bot user. Returns (userID, userName) or None."""
    for user in manager.session_users:
        if user.get("userName") == "DisChordBot":
            continue
        if user.get("userName") == invoker_display_name:
            return user.get("userID"), user.get("userName")
    for user in manager.session_users:
        if user.get("userName") != "DisChordBot":
            return user.get("userID"), user.get("userName")
    return None


def _find_manager_for_thread(interaction: discord.Interaction):
    """Pick the manager whose thread matches the invocation, else fall back to any active one."""
    channel_id = str(interaction.channel.id) if interaction.channel else None
    for manager in ACTIVE_POD_MANAGERS.values():
        if str(manager.thread_id) == channel_id:
            return manager
    return next(iter(ACTIVE_POD_MANAGERS.values()), None)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PodDraft(bot))
