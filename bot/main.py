from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord.ext import commands
from sqlalchemy import select

from bot.config import settings
from bot.database import run_migrations
from bot.models import MagicSet, Player
from bot.services.refresh import refresh_active_players
from bot.services.seventeenlands import SeventeenLandsClient
from bot.sets import ACTIVE_SET_CODE


log = logging.getLogger(__name__)

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def configure_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = logging.FileHandler(LOG_DIR / "bot.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Replace any pre-existing handlers (e.g. from imports that called basicConfig)
    root.handlers = [file_handler, console_handler]


def build_bot(guild_id: int) -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.dm_messages = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    guild = discord.Object(id=guild_id)

    @bot.event
    async def setup_hook() -> None:
        from bot.commands.signup import setup as setup_signup
        from bot.commands.signout import setup as setup_signout
        from bot.commands.update_profile import setup as setup_update_profile
        from bot.commands.delete_account import setup as setup_delete_account
        from bot.commands.leaderboard import setup as setup_leaderboard
        from bot.commands.stats import setup as setup_stats
        from bot.commands.help import setup as setup_help

        # Load cogs into memory and mirror to the guild tree so dispatch works.
        # Discord-side sync is handled by the owner-only `!sync` text command, not on startup.
        await setup_signup(bot)
        await setup_signout(bot)
        await setup_update_profile(bot)
        await setup_delete_account(bot)
        await setup_leaderboard(bot)
        await setup_stats(bot)
        await setup_help(bot)
        bot.tree.copy_global_to(guild=guild)
        log.info("setup_hook: cogs loaded; run `!sync` to publish slash commands to Discord")

    async def _reply_quietly(ctx: commands.Context, message: str) -> None:
        """Reply via DM. Invoke `!sync` from a DM with the bot to keep everything private."""
        await ctx.author.send(message)

    @bot.command(name="sync")
    @commands.is_owner()
    async def sync_commands(ctx: commands.Context, scope: str = "all") -> None:
        """Owner-only. Sync slash commands to Discord.

        `!sync`        — full sync: guild gets server-visible commands, global gets only the DM-only ones (relink, exile)
        `!sync guild`  — guild sync only (skip the global publish)
        `!sync clear`  — wipe every command registration (recovery only)
        """
        if scope == "clear":
            bot.tree.clear_commands(guild=guild)
            bot.tree.clear_commands(guild=None)
            await bot.tree.sync(guild=guild)
            await bot.tree.sync()
            await _reply_quietly(ctx, "✅ Cleared all command registrations.")
            return

        # Commands registered globally (their allowed_contexts decides where they're visible).
        # Only /refresh is guild-scoped (admin command) — everything else goes global.
        GLOBAL_COMMANDS = {"leaderboard", "join", "retire", "relink", "exile", "stats", "help"}

        bot.tree.copy_global_to(guild=guild)
        # Strip globally-registered commands from the guild tree to avoid duplicate registration
        for name in GLOBAL_COMMANDS:
            bot.tree.remove_command(name, guild=guild)
        synced_guild = await bot.tree.sync(guild=guild)

        if scope == "guild":
            await _reply_quietly(ctx, f"✅ Synced {len(synced_guild)} guild commands.")
            return

        # Global sync: only GLOBAL_COMMANDS go in
        all_global = list(bot.tree.get_commands())
        hidden = [c for c in all_global if c.name not in GLOBAL_COMMANDS]
        for c in hidden:
            bot.tree.remove_command(c.name)
        try:
            synced_global = await bot.tree.sync()
        finally:
            # Restore so future syncs and in-memory dispatch keep all commands available
            for c in hidden:
                bot.tree.add_command(c)

        await _reply_quietly(ctx, f"✅ Synced: {len(synced_guild)} guild, {len(synced_global)} global.")

    @bot.command(name="refresh")
    @commands.is_owner()
    async def refresh_cmd(ctx: commands.Context, set_code: str | None = None) -> None:
        """Owner-only. Re-pull stats from 17lands for all active players.

        `!refresh`         — refresh the current set (ACTIVE_SET_CODE in bot/sets.py)
        `!refresh CODE`    — refresh a specific set, e.g. `!refresh ECL`
        """
        msg_invalidated_dm = (
            "⚠️ Your 17lands token appears to be invalid (possibly regenerated). "
            "Please use `/relink` (in DM with the bot) to provide your new token."
        )

        from bot.database import SessionLocal

        target_code = set_code or ACTIVE_SET_CODE
        client = SeventeenLandsClient()

        with SessionLocal() as session:
            magic_set = session.execute(
                select(MagicSet).where(MagicSet.code == target_code)
            ).scalar_one_or_none()
            if magic_set is None:
                await _reply_quietly(ctx, f"❌ No set with code `{target_code}`.")
                return

            summary = refresh_active_players(session, client, magic_set)
            invalidated_ids = list(summary.get("invalidated_players", []))
            invalidated_players: list[Player] = []
            if invalidated_ids:
                invalidated_players = session.execute(
                    select(Player).where(Player.id.in_(invalidated_ids))
                ).scalars().all()
                # Detach so we can use them after the session closes
                for p in invalidated_players:
                    session.expunge(p)

        # DM each invalidated player so they know to /relink
        for player in invalidated_players:
            if not player.discord_id:
                continue
            try:
                user = await bot.fetch_user(int(player.discord_id))
                await user.send(msg_invalidated_dm)
            except discord.HTTPException as e:
                log.warning("could not DM player %s: %s", player.id, e)

        await _reply_quietly(
            ctx,
            f"✅ Refresh complete for `{target_code}`: "
            f"{summary['updated']} updated, "
            f"{summary['invalidated']} invalidated, "
            f"{summary['errors']} errors.",
        )

    @bot.event
    async def on_ready() -> None:
        log.info("logged in as %s (id=%s)", bot.user, bot.user.id if bot.user else "?")

    return bot


def main() -> None:
    if settings.discord_bot_token is None or settings.discord_guild_id is None:
        raise SystemExit("DISCORD_BOT_TOKEN and DISCORD_GUILD_ID must be set to run the bot")

    configure_logging()
    run_migrations()

    bot = build_bot(settings.discord_guild_id)
    bot.run(settings.discord_bot_token.get_secret_value(), log_handler=None)


if __name__ == "__main__":
    main()
