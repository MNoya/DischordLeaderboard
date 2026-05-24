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
from bot.commands.help import setup as setup_help
from bot.commands.leaderboard import (
    LeaderboardView,
    edit_tracked_messages_for_set,
    process_leaderboard,
    render_embed as render_leaderboard_embed,
    setup as setup_leaderboard,
)
from bot.commands.pod_draft import setup as setup_pod_draft
from bot.commands.signout import setup as setup_signout
from bot.commands.signup import setup as setup_signup
from bot.commands.stats import setup as setup_stats
from bot.commands.update_profile import setup as setup_update_profile
from bot.config import settings
from bot.database import SessionLocal, run_migrations
from bot.discord_helpers import refresh_player_avatars
from bot import emojis
from bot.commands.testcomponent import setup as setup_testcomponent
from bot.commands.testlobby import setup as setup_testlobby
from bot.listeners.auto_link_listener import setup as setup_auto_link_listener
from bot.listeners.pod_screenshots import setup as setup_pod_screenshots
from bot.listeners.sesh_listener import reschedule_pending_events, setup as setup_sesh_listener
from bot.models import LeaderboardMessage, MagicSet, Player, PodDraftEvent
from bot.services.bot_log import BotLog
from bot.services.lobby_embed import LobbyReadyButtonView
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_tournament import (
    register_persistent_views as register_pod_views,
)
from bot.services.refresh import refresh_active_players
from bot.services.seventeenlands import MinIntervalLimiter, SeventeenLandsClient
from bot.sets import ACTIVE_SET_CODE
from bot.tasks.pod_draft_reminder import fire_reminder, init_reminder


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


def build_bot(guild_id: int) -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.dm_messages = True
    intents.members = True
    bot = commands.Bot(command_prefix="!", intents=intents)
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

        # Load cogs into memory and mirror to the guild tree so dispatch works.
        # Discord-side sync is handled by the owner-only `!sync` text command, not on startup.
        await setup_signup(bot)
        await setup_signout(bot)
        await setup_update_profile(bot)
        await setup_delete_account(bot)
        await setup_leaderboard(bot)
        await setup_stats(bot)
        await setup_help(bot)
        await setup_pod_draft(bot)
        await setup_sesh_listener(bot)
        await setup_pod_screenshots(bot)
        await setup_auto_link_listener(bot)
        await setup_testlobby(bot)
        await setup_testcomponent(bot)
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
        tb = "".join(traceback.format_exception(type(original), original, original.__traceback__))
        await _notify_owner(bot, f"⚠️ `/{cmd_name}` crashed (invoked by {invoker}):", tb)

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
        GLOBAL_COMMANDS = {"leaderboard", "leaderboard-full", "join", "retire", "relink", "exile", "stats", "help"}

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

    async def run_refresh(*, trigger: str) -> dict:
        """Pull 17lands data, recompute scores, repaint live messages, post a report to bot-spam.

        ``trigger`` is "manual" (``!refresh`` DM) or "auto" (periodic tick); both use the
        same active-set window. Tag is included in the channel post so the source is obvious.
        """
        msg_invalidated_dm = (
            "⚠️ Your 17lands token appears to be invalid (possibly regenerated). "
            "Please use `/relink` to provide your new token."
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
                avatar_summary = await refresh_player_avatars(bot, session, active_players)
        except Exception:
            log.warning("avatar refresh sweep failed", exc_info=True)

        edit_summary = {"edited": 0, "pruned": 0, "errors": 0}
        with SessionLocal() as session:
            ms = session.execute(
                select(MagicSet).where(MagicSet.code == ACTIVE_SET_CODE)
            ).scalar_one_or_none()
            if ms is not None:
                edit_summary = await edit_tracked_messages_for_set(bot, ms)

        result = {
            "summary": summary,
            "avatar_summary": avatar_summary,
            "edit_summary": edit_summary,
            "trigger": trigger,
        }

        await _post_refresh_report(result)

        with SessionLocal() as session:
            full_data = process_leaderboard(session, viewer_discord_id=None, top_n=10**6)
        if full_data is not None and full_data.top and bot.owner_id is not None:
            try:
                owner = bot.get_user(bot.owner_id) or await bot.fetch_user(bot.owner_id)
                await owner.send(embed=render_leaderboard_embed(full_data))
            except discord.HTTPException:
                log.warning("could not DM owner the full leaderboard preview", exc_info=True)

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
            f"Messages: {result['edit_summary']['edited']} edited | {result['edit_summary']['pruned']} pruned | {result['edit_summary']['errors']} failed",
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

        body = (
            f"🔄 {trigger} refresh complete\n"
            f"Elapsed: {elapsed} · Players: {n_players} · {avg}\n"
            f"Updated: {summary['updated']} · "
            f"Invalidated: {summary['invalidated']} · "
            f"Errors: {summary['errors']}\n"
            f"Live messages: {result['edit_summary']['edited']} edited, "
            f"{result['edit_summary']['pruned']} pruned, "
            f"{result['edit_summary']['errors']} failed"
        )
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

    @bot.command(name="start")
    @commands.is_owner()
    async def start_pod(ctx: commands.Context, identifier: str | None = None) -> None:
        """Owner-only.

        In a pod-draft thread → force-starts the draft past a stuck ready check.
        Elsewhere:
        `!start`            — picks the lone pending pod; lists candidates if there's more than one
        `!start <id>`       — explicit pick by event UUID, thread ID, or sesh message ID
        """
        channel_id = str(ctx.channel.id) if ctx.channel else None
        if channel_id and identifier is None:
            manager = next(
                (m for m in ACTIVE_POD_MANAGERS.values() if str(m.thread_id) == channel_id),
                None,
            )
            if manager is not None:
                log.info(f"!start force-start: {ctx.author} in thread {channel_id}")
                await ctx.send("⚙️ Force-starting the draft…")
                err = await manager.force_start()
                if err is not None:
                    await ctx.send(f"⚠️ {err}")
                return

        target = await asyncio.to_thread(_resolve_pending_pod, identifier)
        if isinstance(target, str):
            await _reply_quietly(ctx, target)
            return
        await _reply_quietly(ctx, f"⏳ Opening lobby for **{target['name']}**…")
        await fire_reminder(target["id"], early=True)
        await _reply_quietly(ctx, f"✅ Lobby opened — bot is joining `{target['session_id']}`.")

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
        if not settings.auto_refresh_enabled:
            log.info("AUTO_REFRESH_ENABLED=false; skipping the scheduled 17lands refresh tick")
            return
        if not auto_refresh_tick.is_running():
            auto_refresh_tick.start()

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


def _resolve_pending_pod(identifier: str | None) -> dict | str:
    """Resolve `identifier` to a single pending PodDraftEvent. Returns a dict with id / name /
    session_id on success, or a string error message ready to relay to the caller.

    With no identifier, returns the lone pending event if exactly one is queued, otherwise lists
    all candidates so the caller can be specific. Pending = `socket_status == 'pending'`.
    """
    with SessionLocal() as session:
        pending = session.execute(
            select(PodDraftEvent).where(PodDraftEvent.socket_status == "pending")
            .order_by(PodDraftEvent.event_time.asc())
        ).scalars().all()
        if identifier:
            ident = identifier.strip()
            match = next(
                (e for e in pending
                 if e.id == ident or e.discord_thread_id == ident or e.sesh_message_id == ident),
                None,
            )
            if match is None:
                return f"❌ No pending pod-draft matches `{ident}` (id, thread, or sesh message)."
            return {"id": match.id, "name": match.name, "session_id": match.draftmancer_session}

        if not pending:
            return "❌ No pending pod-draft events to open."
        if len(pending) > 1:
            lines = [
                f"- `{e.id}` · {e.name} · {e.event_time:%Y-%m-%d %H:%M %Z} · thread `{e.discord_thread_id}`"
                for e in pending
            ]
            return "⚠️ Multiple pending pods — pick one with `!start <id>`:\n" + "\n".join(lines)
        e = pending[0]
        return {"id": e.id, "name": e.name, "session_id": e.draftmancer_session}


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
    link = f"[`{short}`](https://github.com/MNoya/DischordLeaderboard/commit/{sha})"
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
        active_set = session.execute(
            select(MagicSet).where(MagicSet.code == ACTIVE_SET_CODE)
        ).scalar_one_or_none()
        player_count = session.execute(select(func.count()).select_from(Player)).scalar()
        lb_count = session.execute(select(func.count()).select_from(LeaderboardMessage)).scalar()
        upcoming = session.execute(
            select(PodDraftEvent)
            .where(PodDraftEvent.socket_status.in_(["pending", "open", "drafting", "in_progress"]))
            .order_by(PodDraftEvent.event_time)
        ).scalars().all()

    set_code = active_set.code if active_set else ACTIVE_SET_CODE
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
