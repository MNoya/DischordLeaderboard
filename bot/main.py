from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import signal
import traceback
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy import func, select

from bot.commands.delete_account import setup as setup_delete_account
from bot.commands.event_scribe import setup as setup_event_scribe
from bot.commands.help import setup as setup_help
from bot.commands.link_17lands import setup as setup_link_17lands
from bot.commands.leaderboard_visibility import setup as setup_leaderboard_visibility
from bot.commands.leaderboard import (
    LeaderboardView,
    edit_tracked_messages_for_set,
    setup as setup_leaderboard,
)
from bot.commands.pod_backfill import setup as setup_pod_backfill
from bot.commands.mock_draft import setup as setup_mock_draft
from bot.commands.pod_draft import setup as setup_pod_draft
from bot.commands.pod_schedule import setup as setup_pod_schedule
from bot.commands.preview_season_awards import setup as setup_preview_season_awards
from bot.commands.signout import setup as setup_signout
from bot.commands.signup import setup as setup_signup
from bot.commands.stats import setup as setup_stats
from bot.config import settings
from bot.database import SessionLocal, run_migrations
from bot.discord_helpers import refresh_player_profiles
from bot import emojis
from bot.commands.test_group import setup as setup_test_group
from bot.commands.testawards import setup as setup_testawards
from bot.commands.testchampionship import setup as setup_testchampionship
from bot.commands.testcomponent import setup as setup_testcomponent
from bot.commands.testlobby import setup as setup_testlobby
from bot.commands.testschedule import setup as setup_testschedule
from bot.commands.testformatschedule import setup as setup_testformatschedule
from bot.commands.testscribe import setup as setup_testscribe
from bot.listeners.auto_link_listener import setup as setup_auto_link_listener
from bot.listeners.pod_screenshots import setup as setup_pod_screenshots
from bot.listeners.rotate_image import setup as setup_rotate_image
from bot.listeners.sesh_listener import reschedule_pending_events, setup as setup_sesh_listener
from bot.models import LeaderboardMessage, Player, PodDraftEvent
from bot.services.bot_log import BotLog
from bot.services.lobby_embed import LobbyReadyButtonView
from bot.services.pod_draft_manager import rehydrate_active_lobbies
from bot.services.pod_tournament import (
    reconcile_unannounced_championships,
    register_persistent_views as register_pod_views,
    rehydrate_active_tournaments,
)
from bot.services.media_sync import sync_media, SyncResult
from bot.services.active_set import resolve_active_set
from bot.services.refresh import refresh_active_players
from bot.services.seventeenlands import MinIntervalLimiter, SeventeenLandsClient
from bot.sets import active_set_code
from bot.tasks.pod_draft_reminder import init_reminder
from bot.tasks.format_schedule_post import init_format_schedule
from bot.tasks.pod_schedule_post import init_schedule_post
from bot.tasks.pod_underfill import init_underfill


log = logging.getLogger("bot.main")

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

AUTO_REFRESH_TZ = ZoneInfo("America/Montevideo")
AUTO_REFRESH_TIMES = [
    dtime(hour=2, minute=0, tzinfo=AUTO_REFRESH_TZ),
    dtime(hour=8, minute=0, tzinfo=AUTO_REFRESH_TZ),
    dtime(hour=14, minute=0, tzinfo=AUTO_REFRESH_TZ),
    dtime(hour=20, minute=0, tzinfo=AUTO_REFRESH_TZ),
]
AUTO_REFRESH_17L_INTERVAL_S = 3.0

MEDIA_SYNC_TIME = dtime(hour=3, minute=30, tzinfo=AUTO_REFRESH_TZ)

MSG_GENERIC_ERROR = "⚠️ Something went wrong handling that command. The bot owner has been notified."


def main() -> None:
    if settings.discord_bot_token is None or settings.discord_guild_id is None:
        raise SystemExit("DISCORD_BOT_TOKEN and DISCORD_GUILD_ID must be set to run the bot")

    _restart_banner()
    configure_logging()
    run_migrations()

    signal.signal(signal.SIGTERM, lambda *_: signal.raise_signal(signal.SIGINT))

    bot = build_bot(settings.discord_guild_id)
    bot.run(settings.discord_bot_token.get_secret_value(), log_handler=None)


def configure_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    formatter = logging.Formatter(
        fmt="{asctime} {levelname} [{process:d}][{module}.{funcName}:{lineno:d}] {message}",
        style="{",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "bot.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [file_handler, console_handler]

    for noisy in ("discord.http", "engineio.client", "socketio.client"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class LoggingCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        command = interaction.command
        if command is not None:
            log.info(f"command: /{command.qualified_name} by {interaction.user}")
        return True


def build_bot(guild_id: int) -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.dm_messages = True
    intents.members = True
    bot = commands.Bot(command_prefix="!", intents=intents, tree_cls=LoggingCommandTree)
    guild = discord.Object(id=guild_id)

    @bot.event
    async def setup_hook() -> None:
        # Discord doesn't auto-populate owner_id; fetch it so /command crashes can DM the right person
        app_info = await bot.application_info()
        bot.owner_id = app_info.owner.id

        bot.bot_log = BotLog(bot, settings.discord_botlog_channel_id)

        await emojis.load(bot)

        # Pod-draft scheduler — in-memory; on_ready() runs a sweep that re-arms any
        # pending T-5 reminders so restarts don't lose work
        bot.pod_scheduler = AsyncIOScheduler()
        bot.pod_scheduler.start()
        init_reminder(bot)
        init_underfill(bot)
        init_schedule_post(bot)
        init_format_schedule(bot)

        # Load cogs into memory and mirror to the guild tree so dispatch works.
        # Discord-side sync is handled by the owner-only `!sync` text command, not on startup.
        await setup_signup(bot)
        await setup_signout(bot)
        await setup_delete_account(bot)
        await setup_leaderboard(bot)
        await setup_stats(bot)
        await setup_help(bot)
        await setup_event_scribe(bot)
        await setup_link_17lands(bot)
        await setup_leaderboard_visibility(bot)
        await setup_pod_draft(bot)
        await setup_mock_draft(bot)
        await setup_pod_backfill(bot)
        await setup_pod_schedule(bot)
        await setup_preview_season_awards(bot)
        await setup_sesh_listener(bot)
        await setup_pod_screenshots(bot)
        await setup_rotate_image(bot)
        await setup_auto_link_listener(bot)
        await setup_test_group(bot)
        await setup_testlobby(bot)
        await setup_testcomponent(bot)
        await setup_testawards(bot)
        await setup_testschedule(bot)
        await setup_testscribe(bot)
        await setup_testformatschedule(bot)
        await setup_testchampionship(bot)
        reschedule_pending_events(bot)
        register_pod_views(bot)
        _log_startup_summary()
        bot.tree.copy_global_to(guild=guild)

        # Register the persistent leaderboard view so Join buttons on previously-posted
        # messages keep dispatching after a bot restart
        bot.add_view(LeaderboardView())
        bot.add_view(LobbyReadyButtonView())

        log.info("setup_hook: cogs loaded; run `!sync` to publish slash commands to Discord")

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction, error: app_commands.AppCommandError,
    ) -> None:
        """Catch-all so a crashed handler doesn't leave 'thinking…' indefinitely.

        Surfaces a generic ephemeral apology to the invoker and DMs the bot owner
        with the traceback for diagnosis.
        """
        original = getattr(error, "original", error)
        log.exception(f"app command crashed: {original}", exc_info=original)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(MSG_GENERIC_ERROR, ephemeral=True)
            else:
                await interaction.response.send_message(MSG_GENERIC_ERROR, ephemeral=True)
        except discord.HTTPException:
            log.warning("could not send generic error to user", exc_info=True)

        cmd_name = interaction.command.qualified_name if interaction.command else "unknown"
        invoker = f"{interaction.user} (`{interaction.user.id}`)"
        opts = ", ".join(f"{k}={v!r}" for k, v in interaction.namespace) or "no args"
        tb = "".join(traceback.format_exception(type(original), original, original.__traceback__))
        await _notify_owner(bot, f"⚠️ `/{cmd_name}` crashed (invoked by {invoker}, args: {opts}):", tb)

    async def _reply_quietly(ctx: commands.Context, message: str) -> None:
        """Reply via DM. Invoke `!sync` from a DM with the bot to keep everything private."""
        await ctx.author.send(message)

    @bot.command(name="sync")
    @commands.is_owner()
    async def sync_commands(ctx: commands.Context, scope: str = "all") -> None:
        """Owner-only. Sync slash commands to Discord.

        `!sync`        — full sync: DM-capable commands (allowed_contexts dms=True) go global so they
                         reach DMs; the rest stay guild-scoped, where schema changes appear instantly
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

        # A command goes global — the only registration DMs can see — when its allowed_contexts
        # permits DMs; the rest stay guild-scoped, where schema changes appear instantly. Each
        # command's decorator is the source of truth, so a new DM command needs no list to edit here.
        global_names = {command.name for command in bot.tree.get_commands()
                        if getattr(command, "allowed_contexts", None) and command.allowed_contexts.dm_channel}

        bot.tree.copy_global_to(guild=guild)
        # Strip globally-registered commands from the guild tree to avoid duplicate registration
        for name in global_names:
            bot.tree.remove_command(name, guild=guild)
        synced_guild = await bot.tree.sync(guild=guild)

        if scope == "guild":
            await _reply_quietly(ctx, f"✅ Synced {len(synced_guild)} guild commands.")
            return

        hidden = [c for c in bot.tree.get_commands() if c.name not in global_names]
        for c in hidden:
            bot.tree.remove_command(c.name)
        try:
            synced_global = await bot.tree.sync()
        finally:
            # Restore so future syncs and in-memory dispatch keep all commands available
            for c in hidden:
                bot.tree.add_command(c)

        await _reply_quietly(ctx, f"✅ Synced: {len(synced_guild)} guild, {len(synced_global)} global.")

    async def run_refresh(*, trigger: str) -> dict:
        """Pull 17lands data, recompute scores, repaint live messages, post a report to bot-spam.

        ``trigger`` is "manual" (``!refresh`` DM) or "auto" (periodic tick); both use the
        same active-set window. Tag is included in the channel post so the source is obvious.
        """
        msg_invalidated_dm = (
            "⚠️ Your 17lands token appears to be invalid (possibly regenerated). "
            "Please use `/link-17lands` to provide your new token."
        )

        def _do_db_work() -> dict:
            limiter = (
                MinIntervalLimiter(min_interval_s=AUTO_REFRESH_17L_INTERVAL_S)
                if trigger == "auto" else None
            )
            client = SeventeenLandsClient(limiter=limiter)
            with SessionLocal() as session:
                # Full-history rebuilds live in bot/scripts/refresh_stats.py — too slow for a live command
                return refresh_active_players(session, client)

        # 17lands fetches and SQLAlchemy work are blocking; running them inline
        # would freeze the gateway heartbeat. Push to a worker thread so the
        # event loop stays free to dispatch other commands while this runs
        summary = await asyncio.to_thread(_do_db_work)

        invalidated_ids = list(summary.get("invalidated_players", []))
        invalidated_players: list[Player] = []
        if invalidated_ids:
            with SessionLocal() as session:
                invalidated_players = list(session.execute(
                    select(Player).where(Player.id.in_(invalidated_ids))
                ).scalars().all())
                for p in invalidated_players:
                    session.expunge(p)

        for player in invalidated_players:
            if not player.discord_id:
                continue
            try:
                user = await bot.fetch_user(int(player.discord_id))
                await user.send(msg_invalidated_dm)
            except discord.HTTPException as e:
                log.warning(f"could not DM player {player.id}: {e}")

        avatar_summary = {"checked": 0, "updated": 0, "skipped": 0, "errors": 0}
        try:
            with SessionLocal() as session:
                active_players = list(
                    session.execute(
                        select(Player).where(Player.active.is_(True))
                    ).scalars().all()
                )
                avatar_summary = await refresh_player_profiles(bot, session, active_players)
        except Exception:
            log.warning("profile refresh sweep failed", exc_info=True)

        edit_summary = {"edited": 0, "pruned": 0}
        with SessionLocal() as session:
            ms = resolve_active_set(session)
            if ms is not None:
                edit_summary = await edit_tracked_messages_for_set(bot, ms)

        result = {
            "summary": summary,
            "avatar_summary": avatar_summary,
            "edit_summary": edit_summary,
            "trigger": trigger,
        }

        await _post_refresh_report(result)

        return result

    async def _post_refresh_report(result: dict) -> None:
        summary = result["summary"]
        per_player = summary.get("per_player", [])
        n_players = len(per_player)
        elapsed = _fmt_elapsed(summary.get("elapsed_s", 0.0))
        avg = f"{summary['elapsed_s'] / n_players:.1f}s avg" if n_players else ""
        trigger = result["trigger"].title()

        rows: list[str] = [
            f"{trigger} Refresh | {elapsed} | {n_players} Players{avg}",
            f"Updated {summary['updated']} | Invalidated {summary['invalidated']} | Errors {summary['errors']}",
            f"Messages: {result['edit_summary']['edited']} edited | {result['edit_summary']['pruned']} pruned",
        ]
        unknown = summary.get("unknown_formats") or {}
        if unknown:
            tally = "  ".join(f"{fmt} ×{n}" for fmt, n in sorted(unknown.items(), key=lambda kv: (-kv[1], kv[0])))
            rows.append(f"⚠️  New formats (stored, not scoring): {tally}")
        unrouted = summary.get("unrouted_expansions") or {}
        if unrouted:
            tally = "  ".join(f"{exp} ×{n}" for exp, n in sorted(unrouted.items(), key=lambda kv: (-kv[1], kv[0])))
            rows.append(f"⚠️  Unrouted expansions (add to sets.py): {tally}")
        for row in rows:
            log.info(row)

        body = f"🔄 {trigger} refresh complete · {elapsed} · {n_players} players"
        if avg:
            body += f" · {avg}"
        if summary["errors"]:
            body += (
                f"\nUpdated: {summary['updated']} · "
                f"Invalidated: {summary['invalidated']} · "
                f"Errors: {summary['errors']}"
            )
        edits = result["edit_summary"]
        msg_line = f"Live messages: {edits['edited']} edited"
        if edits["pruned"]:
            msg_line += f" · {edits['pruned']} pruned"
        body += f"\n{msg_line}"
        if unknown:
            tally = ", ".join(f"`{fmt}` ×{n}" for fmt, n in sorted(unknown.items(), key=lambda kv: (-kv[1], kv[0])))
            body += f"\n⚠️ New format(s) observed (stored, not scoring): {tally}"
        if unrouted:
            tally = ", ".join(f"`{exp}` ×{n}" for exp, n in sorted(unrouted.items(), key=lambda kv: (-kv[1], kv[0])))
            body += f"\n⚠️ Unrouted expansion(s) — events stored without a set (add to bot/sets.py): {tally}"

        await bot.bot_log.post_plain(body)

    @bot.command(name="refresh")
    @commands.is_owner()
    async def refresh_cmd(ctx: commands.Context) -> None:
        """Owner-only. Refresh the active set for every active player (same window as the periodic tick)."""
        await _reply_quietly(ctx, "⏳ Refreshing all sets…")
        await run_refresh(trigger="manual")

    @tasks.loop(time=AUTO_REFRESH_TIMES)
    async def auto_refresh_tick() -> None:
        try:
            log.info("auto-refresh: scheduled tick firing (periodic window)")
            await run_refresh(trigger="auto")
        except Exception:
            log.exception("auto-refresh tick failed")
            await _notify_owner(bot, "⚠️ auto-refresh tick crashed:", traceback.format_exc())

    @auto_refresh_tick.before_loop
    async def _before_auto_refresh() -> None:
        await bot.wait_until_ready()

    async def run_media_sync() -> SyncResult:
        def _do_sync() -> SyncResult:
            with SessionLocal() as session:
                return sync_media(session)

        return await asyncio.to_thread(_do_sync)

    @bot.command(name="sync-media")
    @commands.is_owner()
    async def sync_media_cmd(ctx: commands.Context) -> None:
        """Owner-only. Pull the podcast feed + YouTube channel into the episodes table."""
        await _reply_quietly(ctx, "⏳ Syncing episodes…")
        result = await run_media_sync()
        await _reply_quietly(
            ctx,
            f"✅ Synced {result.total} episodes ({result.matched} matched, {result.videos_only} video-only, "
            f"{result.podcasts_only} podcast-only, {result.with_set} with a set).",
        )

    @tasks.loop(time=MEDIA_SYNC_TIME)
    async def media_sync_tick() -> None:
        try:
            log.info("media-sync: scheduled tick firing")
            await run_media_sync()
        except Exception:
            log.exception("media-sync tick failed")
            await _notify_owner(bot, "⚠️ media-sync tick crashed:", traceback.format_exc())

    @media_sync_tick.before_loop
    async def _before_media_sync() -> None:
        await bot.wait_until_ready()

    bot.startup_announced = False

    @bot.event
    async def on_ready() -> None:
        log.info(f"logged in as {bot.user} (id={bot.user.id if bot.user else '?'})")
        await bot.change_presence(activity=discord.Activity(
            type=discord.ActivityType.competing,
            name="dischord.pages.dev | /join",
        ))
        if not bot.startup_announced:
            bot.startup_announced = True
            await bot.bot_log.post_plain(_deploy_announcement())
            await rehydrate_active_tournaments(bot)
            await rehydrate_active_lobbies(bot)
            await reconcile_unannounced_championships(bot)
        if not settings.auto_refresh_enabled:
            log.info("AUTO_REFRESH_ENABLED=false; skipping the scheduled 17lands refresh tick")
            return
        if not auto_refresh_tick.is_running():
            auto_refresh_tick.start()
        if settings.media_sync_enabled and not media_sync_tick.is_running():
            media_sync_tick.start()

    return bot


async def _notify_owner(bot: commands.Bot, header: str, body: str) -> None:
    """Best-effort DM the bot's owner. Crashes inside the notifier itself are swallowed."""
    owner_id = bot.owner_id
    if owner_id is None:
        return
    try:
        owner = bot.get_user(owner_id) or await bot.fetch_user(owner_id)
        # Discord caps message body at 2000 chars; truncate the traceback to fit comfortably
        snippet = body[-1700:]
        await owner.send(f"{header}\n```\n{snippet}\n```")
    except discord.HTTPException:
        log.warning("could not DM owner about crash", exc_info=True)


def _fmt_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, sec = divmod(int(round(seconds)), 60)
    return f"{minutes}m {sec}s"


def _fmt_eta(delta: object) -> str:
    total = int(delta.total_seconds())
    if total < 0:
        return "overdue"
    h, rem = divmod(total, 3600)
    m = rem // 60
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def _deploy_announcement() -> str:
    """Build the startup channel post, enriching with Railway's git env vars if present."""
    sha = os.environ.get("RAILWAY_GIT_COMMIT_SHA") or ""
    if not sha:
        return "🚀 Bot redeployed"
    short = sha[:7]
    link = f"[`{short}`](<https://github.com/MNoya/DischordLeaderboard/commit/{sha}>)"
    raw = (os.environ.get("RAILWAY_GIT_COMMIT_MESSAGE") or "").strip()
    subject = raw.split("\n", 1)[0].strip() if raw else ""
    if subject:
        if len(subject) > 120:
            subject = subject[:119] + "…"
        return f"🚀 Bot redeployed: {link} {subject}"
    return f"🚀 Bot redeployed: {link}"


def _log_startup_summary() -> None:
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        active_set = resolve_active_set(session)
        player_count = session.execute(select(func.count()).select_from(Player)).scalar()
        lb_count = session.execute(select(func.count()).select_from(LeaderboardMessage)).scalar()
        upcoming = session.execute(
            select(PodDraftEvent)
            .where(PodDraftEvent.socket_status.in_(["pending", "open", "drafting", "in_progress"]))
            .order_by(PodDraftEvent.event_time)
        ).scalars().all()

    set_code = active_set.code if active_set else active_set_code()
    header = f"{set_code} | {player_count} Players"
    lb_line = f"{lb_count} Leaderboard Messages"
    if upcoming:
        pod_lines = [
            f"{ev.name:<28}  {ev.event_time.strftime('%Y-%m-%d %H:%M UTC')}  (in {_fmt_eta(ev.event_time - now)})"
            for ev in upcoming
        ]
    else:
        pod_lines = ["No Upcoming Pod Drafts"]

    log.info(header)
    log.info(lb_line)
    for line in pod_lines:
        log.info(line)


def _restart_banner() -> None:
    """Bright ANSI banner on stderr to delimit restarts in the dev terminal."""
    import sys
    from datetime import datetime
    line = f"═══════════ BOT RESTART @ {datetime.now():%Y-%m-%d %H:%M:%S} ═══════════"
    print(f"\033[1;33m{line}\033[0m", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
