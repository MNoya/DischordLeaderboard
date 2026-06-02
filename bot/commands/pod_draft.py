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
from bot.commands import descriptions as desc
from bot.config import settings
from bot.database import SessionLocal
from bot.discord_helpers import display_width, extract_avatar_hash, player_url
from bot.models import Player
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_draft_manager import set_event_format, set_event_pairing_mode, set_event_seating
from bot.services.pod_drafts import (
    load_event_id_by_name_sync,
    load_event_id_by_thread_sync,
    load_event_name_sync,
    load_event_pairing_mode_sync,
    load_event_sesh_message_id_sync,
    load_event_set_code_sync,
    load_event_thread_id_sync,
    normalize_player_name,
    search_event_names_sync,
)
from bot.services.player_stats import SeededAttendee, seed_attendees
from bot.sets import ACTIVE_SET_CODE
from bot.services.pod_settings_view import PodSettingsView
from bot.services.pod_tournament import (
    actor_label,
    build_champion_announcement_view_for_event,
    build_live_submit_deck_button,
    build_replays_link_button,
    build_standings_embed_for_event,
    build_thread_link_button,
)
from bot.slug import disambiguate_slug, slugify


log = logging.getLogger(__name__)

_ARENA_INPUT_RE = re.compile(r"^.+#\d+$")

YES_EMOJI = "✅"
MAYBE_EMOJI = "🤷"
CHAMPIONSHIP_CUT = 8

MSG_SEEDING_NOT_POD_THREAD = "Run this inside a pod-draft thread."
MSG_SEEDING_NO_SESH = "Couldn't read the sesh post for this pod — it may have been deleted."
MSG_SEEDING_NO_RSVPS = f"No {YES_EMOJI} or {MAYBE_EMOJI} RSVPs on this pod yet."



class PodDraft(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="pod-ready", description=desc.POD_READY)
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
        err = await manager.initiate_ready_check(thread, initiated_by=actor_label(interaction))
        if err is not None:
            log.warning(f"ready-check: failed — {err}")
            await interaction.followup.send(f"⚠️ {err}", ephemeral=True)
        else:
            await interaction.followup.send("Ready Check initiated, watch the thread for status.", ephemeral=True)

    @app_commands.command(name="pod-start", description=desc.POD_START)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_start(self, interaction: discord.Interaction) -> None:
        manager = _find_manager_for_thread(interaction)
        if manager is None:
            await interaction.response.send_message(
                "No active pod draft session right now.",
                ephemeral=True,
            )
            return
        log.info(f"pod-start: {interaction.user} force-starting in thread {interaction.channel_id}")
        await interaction.response.defer(ephemeral=True, thinking=False)
        err = await manager.force_start()
        if err is not None:
            log.warning(f"pod-start: failed — {err}")
            await interaction.followup.send(f"⚠️ {err}", ephemeral=True)
        else:
            await interaction.followup.send("Force-starting the draft, watch the thread.", ephemeral=True)

    @app_commands.command(name="pod-settings", description=desc.POD_SETTINGS)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_settings(self, interaction: discord.Interaction) -> None:
        thread_id = str(interaction.channel_id) if interaction.channel_id else None
        event_id = await asyncio.to_thread(load_event_id_by_thread_sync, thread_id) if thread_id else None
        if event_id is None:
            await interaction.response.send_message(
                "Run this inside a pod-draft thread.",
                ephemeral=True,
            )
            return
        current_code = await asyncio.to_thread(load_event_set_code_sync, event_id)
        current_mode = await asyncio.to_thread(load_event_pairing_mode_sync, event_id)

        async def on_format(inter: discord.Interaction, code: str) -> str | None:
            return await set_event_format(event_id, code)

        async def on_pairing(inter: discord.Interaction, mode: str) -> str | None:
            return await set_event_pairing_mode(event_id, mode)

        manager = ACTIVE_POD_MANAGERS.get(event_id)
        on_seating = None
        seat_order_provider = None
        if manager is not None:
            async def on_seating(inter: discord.Interaction, ordered_user_names: list[str]) -> str | None:
                return await set_event_seating(event_id, ordered_user_names)
            seat_order_provider = manager.seating_lobby_order

        log.info(f"pod-settings: {interaction.user} opened panel for event_id={event_id}")
        await interaction.response.send_message(
            view=PodSettingsView(
                on_format=on_format, on_pairing=on_pairing,
                current_code=current_code, current_mode=current_mode,
                on_seating=on_seating, seat_order_provider=seat_order_provider,
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="link-arena",
        description=desc.LINK_ARENA,
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

        normalized = normalize_player_name(arena_name)

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
                    leaderboard_opt_in=False,
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

    @app_commands.command(name="pod-seeding", description=desc.POD_SEEDING)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_seeding(self, interaction: discord.Interaction) -> None:
        thread_id = str(interaction.channel_id) if interaction.channel_id else None
        event_id = await asyncio.to_thread(load_event_id_by_thread_sync, thread_id) if thread_id else None
        if event_id is None:
            await interaction.response.send_message(MSG_SEEDING_NOT_POD_THREAD, ephemeral=True)
            return

        await interaction.response.defer(thinking=False)
        sesh_message_id = await asyncio.to_thread(load_event_sesh_message_id_sync, event_id)
        rsvps = await self._read_rsvp_reactions(sesh_message_id) if sesh_message_id else None
        if rsvps is None:
            await interaction.followup.send(MSG_SEEDING_NO_SESH, ephemeral=True)
            return

        yes, maybe = rsvps
        if not yes and not maybe:
            await interaction.followup.send(MSG_SEEDING_NO_RSVPS, ephemeral=True)
            return

        yes_seeded, maybe_seeded = await asyncio.to_thread(_seed_rsvps, yes, maybe)

        log.info(f"pod-seeding: {interaction.user} for event_id={event_id} ({len(yes)} yes, {len(maybe)} maybe)")
        await interaction.followup.send(embed=_build_seeding_embed(yes_seeded, maybe_seeded))

    async def _read_rsvp_reactions(self, sesh_message_id: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]] | None:
        """Fetch the sesh post and return (yes, maybe) reactor lists as (discord_id, display_name) pairs.

        Returns None if the message can't be fetched. Bots are skipped (sesh seeds the reactions),
        and a Yes reactor is dropped from Maybe so nobody is double-counted.
        """
        try:
            channel = await self.bot.fetch_channel(settings.pod_draft_channel_id)
            message = await channel.fetch_message(int(sesh_message_id))
        except (discord.HTTPException, ValueError):
            log.warning(f"pod-seeding: could not fetch sesh message {sesh_message_id}", exc_info=True)
            return None

        guild = message.guild
        yes: list[tuple[str, str]] = []
        maybe: list[tuple[str, str]] = []
        for reaction in message.reactions:
            emoji = str(reaction.emoji)
            if emoji == YES_EMOJI:
                bucket = yes
            elif emoji.startswith(MAYBE_EMOJI):
                bucket = maybe
            else:
                continue
            async for user in reaction.users():
                if user.bot:
                    continue
                member = guild.get_member(user.id) if guild else None
                bucket.append((str(user.id), member.display_name if member else user.display_name))

        yes_ids = {did for did, _ in yes}
        maybe = [entry for entry in maybe if entry[0] not in yes_ids]
        return yes, maybe

    @app_commands.command(
        name="pod-draft-standings",
        description=desc.POD_DRAFT_STANDINGS,
    )
    @app_commands.describe(event="Pick an event to publish standings for; defaults to the current thread")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_draft_standings(self, interaction: discord.Interaction, event: str | None = None) -> None:
        await interaction.response.defer(thinking=False)

        if event:
            event_id = await asyncio.to_thread(load_event_id_by_name_sync, event)
            if event_id is None:
                await interaction.followup.send(f"No pod-draft event named `{event}`.", ephemeral=True)
                return
        else:
            channel = interaction.channel
            thread_id = str(channel.id) if channel is not None else None
            event_id = await asyncio.to_thread(load_event_id_by_thread_sync, thread_id) if thread_id else None
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
        thread_id = await asyncio.to_thread(load_event_thread_id_sync, event_id)
        invoked_outside_thread = thread_id is not None and str(interaction.channel_id) != thread_id
        event_name = await asyncio.to_thread(load_event_name_sync, event_id)

        view = discord.ui.View()
        if invoked_outside_thread and interaction.guild_id is not None:
            view.add_item(build_thread_link_button(interaction.guild_id, thread_id))
        view.add_item(build_replays_link_button(event_name))
        if not invoked_outside_thread:
            view.add_item(build_live_submit_deck_button())

        await interaction.followup.send(embed=embed, view=view)

    @pod_draft_standings.autocomplete("event")
    async def _pod_draft_standings_event_autocomplete(
        self, interaction: discord.Interaction, current: str,
    ) -> list[app_commands.Choice[str]]:
        names = await asyncio.to_thread(search_event_names_sync, current)
        return [app_commands.Choice(name=n, value=n) for n in names]

    @app_commands.command(
        name="pod-champion",
        description=desc.POD_CHAMPION,
    )
    @app_commands.describe(event="Pod-draft event to announce")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_champion(self, interaction: discord.Interaction, event: str) -> None:
        await interaction.response.defer(thinking=False)

        event_id = await asyncio.to_thread(load_event_id_by_name_sync, event)
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
        names = await asyncio.to_thread(search_event_names_sync, current)
        return [app_commands.Choice(name=n, value=n) for n in names]

    @app_commands.command(name="pod-takeover", description=desc.POD_TAKEOVER)
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


def _seed_rsvps(
    yes: list[tuple[str, str]], maybe: list[tuple[str, str]],
) -> tuple[list[SeededAttendee], list[SeededAttendee]]:
    with SessionLocal() as session:
        return seed_attendees(session, yes), seed_attendees(session, maybe)


def _build_seeding_embed(yes: list[SeededAttendee], maybe: list[SeededAttendee]) -> discord.Embed:
    parts: list[str] = []
    if yes:
        cut = CHAMPIONSHIP_CUT if len(yes) > CHAMPIONSHIP_CUT else None
        parts.append(f"**{YES_EMOJI} Yes ({len(yes)})**\n" + _seeding_block(yes, numbered=True, cut_after=cut))
    if maybe:
        parts.append(f"**{MAYBE_EMOJI} Maybe ({len(maybe)})**\n" + _seeding_block(maybe, numbered=False))
    return discord.Embed(
        title=f"🏆 Pod Seeding · {ACTIVE_SET_CODE}",
        description="\n\n".join(parts),
        color=discord.Color.gold(),
    )


def _seeding_block(attendees: list[SeededAttendee], *, numbered: bool, cut_after: int | None = None) -> str:
    """Inline-code rows (monospace) linked to each player's page, same trick /leaderboard uses.

    Columns: ordinal # (Yes only, drives the cut), Player, Rnk (#N global rank), Pts, 🏆.
    Unranked attendees show — and link nowhere.
    """
    def rnk(a: SeededAttendee) -> str:
        return f"#{a.rank}" if a.rank is not None else "—"

    def pts(a: SeededAttendee) -> str:
        return "—" if a.score is None else str(round(a.score))

    def trophies(a: SeededAttendee) -> str:
        return "—" if a.trophies is None else str(a.trophies)

    cols = (
        ("Player", "l", lambda a: a.display_name),
        ("Rnk", "r", rnk),
        ("Pts", "r", pts),
        ("🏆", "r", trophies),
    )

    def fmt(value: str, width: int, align: str) -> str:
        pad = max(0, width - display_width(value))
        return value + " " * pad if align == "l" else " " * pad + value

    ord_w = len(f"{len(attendees)}.")
    header_cells: list[str] = []
    row_cells: list[list[str]] = [[] for _ in attendees]
    for header, align, cell in cols:
        values = [cell(a) for a in attendees]
        is_wide = header == "🏆"
        width = max(max(display_width(v) for v in values), 2 if is_wide else len(header))
        header_cells.append(fmt(header, width - 1 if is_wide else width, "l" if align == "l" else "r"))
        for i, v in enumerate(values):
            row_cells[i].append(fmt(v, width, align))

    def line(lead: str, cells: list[str]) -> str:
        prefix = f"{lead:<{ord_w}} " if numbered else ""
        return prefix + "  ".join(cells)

    header_line = line("#", header_cells)
    lines = [f"`{header_line}`"]
    for i, a in enumerate(attendees):
        if cut_after is not None and i == cut_after:
            lines.append(f"`{'─' * display_width(header_line)}`")
        inner = line(f"{i + 1}.", row_cells[i])
        if a.slug:
            lines.append(f"[`{inner}`](<{player_url(a.slug, ACTIVE_SET_CODE)}>)")
        else:
            lines.append(f"`{inner}`")
    return "\n".join(lines)


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
