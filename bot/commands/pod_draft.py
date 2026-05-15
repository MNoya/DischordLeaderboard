"""Pod-draft slash commands."""
from __future__ import annotations

import logging
import re

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import func, select

from bot import audit
from bot.database import SessionLocal
from bot.discord_helpers import MTGA_EMOJI, extract_avatar_hash
from bot.models import MagicSet, Player
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_drafts import list_champions, player_pod_stats
from bot.sets import ACTIVE_SET_CODE
from bot.slug import disambiguate_slug, slugify


log = logging.getLogger(__name__)

_ARENA_INPUT_RE = re.compile(r"^.+#\d+$")

_LAST_POD_LEADERBOARD_MESSAGES: dict[tuple[str, str], int] = {}



class PodDraft(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ready", description="Run a Draftmancer ready check for this pod draft.")
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
        await interaction.response.defer(ephemeral=True, thinking=False)
        err = await manager.initiate_ready_check(thread)
        if err is not None:
            await interaction.followup.send(f"⚠️ {err}", ephemeral=True)
        else:
            await interaction.followup.send("Ready check started — watch the thread for status.", ephemeral=True)

    @app_commands.command(
        name="pod-link-arena",
        description="Link your MTG Arena handle so pod-draft results recognize you.",
    )
    @app_commands.describe(name="Your full MTG Arena handle: ArenaID#1234")
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
                "❌ Use the full MTG Arena handle: `ArenaID#1234`.",
                ephemeral=True,
            )
            return

        with SessionLocal() as session:
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
                    active=True,
                )
                session.add(player)
            else:
                player.arena_name = arena_name
            session.flush()
            player_id = player.id
            session.commit()

        audit.event("pod_link_arena_success", user_id=user_id, player_id=player_id)
        await interaction.response.send_message(
            f"{MTGA_EMOJI} {mention} is **{arena_name}** on Arena.",
            allowed_mentions=no_pings,
        )

    @app_commands.command(
        name="pod-leaderboard",
        description="Pod-draft champion history for a set.",
    )
    @app_commands.describe(set="Set code (defaults to the current active set)")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_leaderboard(self, interaction: discord.Interaction, set: str | None = None) -> None:
        set_code = (set or ACTIVE_SET_CODE).upper()
        audit.event("pod_leaderboard_invoked", user_id=str(interaction.user.id), set_code=set_code)
        with SessionLocal() as session:
            champions = list_champions(session, set_code=set_code)
            magic_set = session.execute(
                select(MagicSet).where(func.upper(MagicSet.code) == set_code)
            ).scalar_one_or_none()

        if magic_set is None:
            await interaction.response.send_message(
                f"Unknown set code `{set_code}`.", ephemeral=True,
            )
            return
        if not champions:
            await interaction.response.send_message(
                f"No pod-draft history yet for `{set_code}`.", ephemeral=True,
            )
            return

        standard = [c for c in champions if not c["format_label"]]
        special = [c for c in champions if c["format_label"]]
        lines: list[str] = []
        for c in standard:
            who = f"<@{c['discord_id']}>" if c["discord_id"] else f"**{c['champion_display_name']}**"
            lines.append(f"🥇 {c['event_date'].strftime('%b %d')} · {c['event_name']} — {who}")
        if special:
            lines.append("")
            lines.append("**Cube / Special**")
            for c in special:
                who = f"<@{c['discord_id']}>" if c["discord_id"] else f"**{c['champion_display_name']}**"
                lines.append(
                    f"{c['event_date'].strftime('%b %d')} · {c['event_name']} "
                    f"({c['format_label']}) — {who}"
                )

        embed = discord.Embed(
            title=f"{MTGA_EMOJI} Pod-draft champions — {set_code}",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        embed.set_footer(text=magic_set.name)
        no_pings = discord.AllowedMentions(users=False, everyone=False, roles=False)

        if interaction.guild is None:
            await interaction.response.send_message(embed=embed, allowed_mentions=no_pings)
            return

        channel_id = str(interaction.channel_id)
        key = (channel_id, magic_set.id)
        prior = _LAST_POD_LEADERBOARD_MESSAGES.get(key)
        await interaction.response.defer()
        sent = await interaction.followup.send(embed=embed, allowed_mentions=no_pings, wait=True)
        _LAST_POD_LEADERBOARD_MESSAGES[key] = sent.id
        if prior and prior != sent.id:
            try:
                old = await interaction.channel.fetch_message(prior)
                await old.delete()
            except discord.HTTPException:
                pass

    @app_commands.command(
        name="pod-stats",
        description="Pod-draft career stats for a player.",
    )
    @app_commands.describe(player="Player display name (defaults to you)")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def pod_stats(self, interaction: discord.Interaction, player: str | None = None) -> None:
        user_id = str(interaction.user.id)
        audit.event("pod_stats_invoked", user_id=user_id, player=player)
        ephemeral = interaction.guild is not None

        with SessionLocal() as session:
            if player:
                target = session.execute(
                    select(Player).where(
                        func.lower(Player.display_name) == player.lower(),
                        Player.active.is_(True),
                    )
                ).scalar_one_or_none()
            else:
                target = session.execute(
                    select(Player).where(Player.discord_id == user_id)
                ).scalar_one_or_none()
            if target is None:
                msg = (
                    f"No active player named `{player}`." if player
                    else "You're not on the leaderboard. Run `/join` or `/pod-link-arena` first."
                )
                await interaction.response.send_message(msg, ephemeral=ephemeral)
                return
            stats = player_pod_stats(session, target.discord_id)

        if stats is None or stats["events_played"] == 0:
            await interaction.response.send_message(
                f"No pod-draft history yet for **{target.display_name}**.", ephemeral=ephemeral,
            )
            return

        total_games = stats["wins"] + stats["losses"]
        winrate = f"{stats['wins'] / total_games:.0%}" if total_games else "—"
        by_set = sorted(stats["trophies_by_set"].items())
        description_lines = [
            f"🏆 **{stats['lifetime_trophies']}** lifetime trophies",
            f"**{stats['events_played']}** events · {stats['wins']}-{stats['losses']} ({winrate})",
        ]
        if by_set:
            description_lines.append("")
            description_lines.append("**Trophies by set**")
            description_lines.extend(f"• **{code}**: {n} 🏆" for code, n in by_set)

        embed = discord.Embed(
            title=f"{MTGA_EMOJI} Pod-draft stats — {target.display_name}",
            description="\n".join(description_lines),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

    @app_commands.command(name="pod-takeover", description="Take control of the Draftmancer session and disconnect the bot.")
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

        await interaction.response.defer(ephemeral=False, thinking=False)
        ok, err = await manager.takeover(target_user_id)
        if not ok:
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
