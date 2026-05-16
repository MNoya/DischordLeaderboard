from __future__ import annotations

import asyncio
import logging
import logging.handlers
import signal
import traceback
from datetime import time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy import select

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
from bot.listeners.sesh_listener import reschedule_pending_events, setup as setup_sesh_listener
from bot.models import MagicSet, Player, PodDraftEvent
from bot.services.pod_active import ACTIVE_POD_MANAGERS
from bot.services.pod_tournament import (
    HollowManager,
    RoundResultsView,
    register_persistent_views as register_pod_views,
    reset_event_matches,
    start_tournament,
)
from bot.services.refresh import refresh_active_players
from bot.services.seventeenlands import MinIntervalLimiter, SeventeenLandsClient
from bot.sets import ACTIVE_SET_CODE
from bot.tasks.pod_draft_reminder import init_reminder


log = logging.getLogger("bot.main")

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

AUTO_REFRESH_TZ = ZoneInfo("America/Montevideo")
AUTO_REFRESH_TIMES = [
    dtime(hour=8, minute=0, tzinfo=AUTO_REFRESH_TZ),
    dtime(hour=20, minute=0, tzinfo=AUTO_REFRESH_TZ),
]
AUTO_REFRESH_17L_INTERVAL_S = 3.0


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


MSG_GENERIC_ERROR = "⚠️ Something went wrong handling that command. The bot owner has been notified."


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
        reschedule_pending_events(bot)
        register_pod_views(bot)
        bot.tree.copy_global_to(guild=guild)

        # Register the persistent leaderboard view so Join buttons on previously-posted
        # messages keep dispatching after a bot restart
        bot.add_view(LeaderboardView())

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
        log.exception("app command crashed: %s", original, exc_info=original)
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

    @bot.command(name="testlobby")
    @commands.is_owner()
    async def test_lobby(ctx: commands.Context, state: str = "") -> None:
        """Owner-only. Render the pod-draft lobby embed in this channel.

        `state` is one of: empty | partial | linked | unlinked | ready | notready | drafting | complete.
        With no arg, posts every state in sequence (one message per state). With a specific state,
        first call posts a new embed; subsequent calls edit the last one in place."""
        valid = (
            "empty", "partial", "linked", "unlinked", "ready", "notready",
            "drafting", "complete", "round1",
        )
        if state and state not in valid:
            await ctx.send(f"unknown state `{state}`; pick one of: {', '.join(valid)}")
            return

        thread_name = "SOS Pod Draft #3 - May 15"
        draftmancer_url = "https://draftmancer.com/?session=LLUT-SOS-May-15-D"
        rsvps_yes = ["Noya", "MNG", "Foo", "Bar", "Baz", "Qux", "Quux", "Corge", "Grault", "Garply"]
        rsvps_maybe = ["Waldo", "Plugh", "Xyzzy"]

        linked_eight = [
            ("Noya#08011", "Noya"),
            ("MNG#61656", "MNG"),
            ("FooArena#1001", "Foo"),
            ("BarArena#1002", "Bar"),
            ("BazArena#1003", "Baz"),
            ("QuxArena#1004", "Qux"),
            ("QuuxArena#1005", "Quux"),
            ("CorgeArena#1006", "Corge"),
        ]

        def _build(s: str) -> tuple[discord.Embed, discord.ui.View | None]:
            if s == "round1":
                pairings = [("Noya", "MNG"), ("Foo", "Bar"), ("Baz", "Qux"), ("Quux", "Corge")]
                match_states = [
                    {
                        "match_id": f"testlobby-m{i}",
                        "a_name": a,
                        "b_name": b,
                        "a_record": "0-0",
                        "b_record": "0-0",
                        "winner_name": None,
                        "score": None,
                    }
                    for i, (a, b) in enumerate(pairings, start=1)
                ]
                description = (
                    f"{emojis.get('mtga')} Get your decks ready, then challenge your opponent below\n\n"
                    + "\n".join(f"⚔️ {a}  vs  {b}" for a, b in pairings)
                )
                embed = discord.Embed(
                    title="━━━ Round 1 Pairings ━━━",
                    description=description,
                    color=discord.Color.green(),
                )
                return embed, RoundResultsView(match_states)

            if s == "empty":
                in_session = []
            elif s == "partial":
                in_session = linked_eight[:2]
            elif s == "unlinked":
                in_session = linked_eight[:7] + [("Stranger#12345", None)]
            else:
                in_session = linked_eight
            ready_count = 3 if s in ("ready", "notready") else None
            embed = _render_lobby_embed_v2(
                thread_name, rsvps_yes, rsvps_maybe, in_session,
                state=s, draftmancer_url=draftmancer_url, ready_count=ready_count,
            )
            has_unrecognized = any(dn is None for _, dn in in_session)
            view: discord.ui.View | None = (
                None if s in ("drafting", "complete")
                else _LobbyReadyButtonView(
                    draftmancer_url=draftmancer_url,
                    ready_disabled=(s == "ready" or has_unrecognized),
                )
            )
            return embed, view

        if state == "":
            for s in valid:
                embed, view = _build(s)
                await ctx.send(embed=embed, view=view)
            return

        embed, view = _build(state)
        last = _LAST_TESTLOBBY_MESSAGE.get(ctx.channel.id)
        if last is not None:
            try:
                await last.edit(embed=embed, view=view, attachments=[])
                return
            except discord.HTTPException:
                _LAST_TESTLOBBY_MESSAGE.pop(ctx.channel.id, None)
        msg = await ctx.send(embed=embed, view=view)
        _LAST_TESTLOBBY_MESSAGE[ctx.channel.id] = msg

    async def run_refresh(target_code: str, *, trigger: str) -> dict | None:
        """Pull 17lands data, recompute scores, repaint live messages, DM the owner a report.

        Returns None if the set code is unknown; otherwise a dict with the
        per-stage summaries and total elapsed time. ``trigger`` is "manual" or
        "auto" — surfaced in the owner DM so the source is obvious.
        """
        msg_invalidated_dm = (
            "⚠️ Your 17lands token appears to be invalid (possibly regenerated). "
            "Please use `/relink` to provide your new token."
        )

        def _do_db_work() -> dict | None:
            limiter = (
                MinIntervalLimiter(min_interval_s=AUTO_REFRESH_17L_INTERVAL_S)
                if trigger == "auto" else None
            )
            client = SeventeenLandsClient(limiter=limiter)
            with SessionLocal() as session:
                magic_set = session.execute(
                    select(MagicSet).where(MagicSet.code == target_code)
                ).scalar_one_or_none()
                if magic_set is None:
                    return None
                return refresh_active_players(session, client, magic_set)

        # 17lands fetches and SQLAlchemy work are blocking; running them inline
        # would freeze the gateway heartbeat. Push to a worker thread so the
        # event loop stays free to dispatch other commands while this runs
        summary = await asyncio.to_thread(_do_db_work)
        if summary is None:
            return None

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
                log.warning("could not DM player %s: %s", player.id, e)

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
                select(MagicSet).where(MagicSet.code == target_code)
            ).scalar_one_or_none()
            if ms is not None:
                edit_summary = await edit_tracked_messages_for_set(bot, ms)

        result = {
            "summary": summary,
            "avatar_summary": avatar_summary,
            "edit_summary": edit_summary,
            "trigger": trigger,
        }

        await _dm_owner_refresh_report(target_code, result)

        with SessionLocal() as session:
            full_data = process_leaderboard(session, viewer_discord_id=None, top_n=10**6)
        if full_data is not None and full_data.top and bot.owner_id is not None:
            try:
                owner = bot.get_user(bot.owner_id) or await bot.fetch_user(bot.owner_id)
                await owner.send(embed=render_leaderboard_embed(full_data))
            except discord.HTTPException:
                log.warning("could not DM owner the full leaderboard preview", exc_info=True)

        return result

    async def _dm_owner_refresh_report(target_code: str, result: dict) -> None:
        if bot.owner_id is None:
            return
        summary = result["summary"]
        per_player = summary.get("per_player", [])
        n_players = len(per_player)
        avg_line = (
            f" · Avg {summary['elapsed_s'] / n_players:.1f}s/player"
            if n_players else ""
        )
        trigger_tag = " (auto)" if result["trigger"] == "auto" else ""
        body = (
            f"🔄 Refresh complete for `{target_code}`{trigger_tag}\n"
            f"Elapsed: {_fmt_elapsed(summary.get('elapsed_s', 0.0))} · "
            f"Players: {n_players}{avg_line}\n"
            f"Updated: {summary['updated']} · "
            f"Invalidated: {summary['invalidated']} · "
            f"Errors: {summary['errors']}\n"
            f"Live messages: {result['edit_summary']['edited']} edited, "
            f"{result['edit_summary']['pruned']} pruned, "
            f"{result['edit_summary']['errors']} failed"
        )
        try:
            owner = bot.get_user(bot.owner_id) or await bot.fetch_user(bot.owner_id)
            await owner.send(content=body)
        except discord.HTTPException:
            log.warning("could not DM owner the refresh report", exc_info=True)

    @bot.command(name="testbracket")
    @commands.is_owner()
    async def test_bracket_cmd(ctx: commands.Context) -> None:
        """Owner-only. Inside a pod-draft thread, wipe its matches and re-run the post-draft Python-Swiss flow with POD_DRAFT_TEST_ROSTER."""
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("Run this inside a pod-draft thread.")
            return
        roster = [n.strip() for n in settings.pod_draft_test_roster.split(",") if n.strip()]
        if len(roster) < 2 or len(roster) % 2 != 0:
            await ctx.send(f"POD_DRAFT_TEST_ROSTER needs an even count (got {len(roster)}).")
            return

        thread_id = str(ctx.channel.id)
        def _find_event():
            with SessionLocal() as session:
                event = session.execute(
                    select(PodDraftEvent).where(PodDraftEvent.discord_thread_id == thread_id)
                ).scalar_one_or_none()
                if event is None:
                    return None
                return event.id

        event_id = await asyncio.to_thread(_find_event)
        if event_id is None:
            await ctx.send("No pod_draft_event tied to this thread.")
            return

        await reset_event_matches(event_id)
        manager = HollowManager(bot, event_id, ctx.channel.id, roster)
        ACTIVE_POD_MANAGERS[event_id] = manager
        await start_tournament(manager)

    @bot.command(name="refresh")
    @commands.is_owner()
    async def refresh_cmd(ctx: commands.Context, set_code: str | None = None) -> None:
        """Owner-only. Re-pull stats from 17lands for all active players.

        `!refresh`         — refresh the current set (ACTIVE_SET_CODE in bot/sets.py)
        `!refresh CODE`    — refresh a specific set, e.g. `!refresh ECL`
        """
        target_code = set_code or ACTIVE_SET_CODE
        await _reply_quietly(ctx, f"⏳ Refreshing `{target_code}`…")
        result = await run_refresh(target_code, trigger="manual")
        if result is None:
            await _reply_quietly(ctx, f"❌ No set with code `{target_code}`.")
            return

    @tasks.loop(time=AUTO_REFRESH_TIMES)
    async def auto_refresh_tick() -> None:
        try:
            log.info("auto-refresh: scheduled tick firing for %s", ACTIVE_SET_CODE)
            await run_refresh(ACTIVE_SET_CODE, trigger="auto")
        except Exception:
            log.exception("auto-refresh tick failed")
            await _notify_owner(bot, "⚠️ auto-refresh tick crashed:", traceback.format_exc())

    @auto_refresh_tick.before_loop
    async def _before_auto_refresh() -> None:
        await bot.wait_until_ready()

    @bot.event
    async def on_ready() -> None:
        log.info("logged in as %s (id=%s)", bot.user, bot.user.id if bot.user else "?")
        await bot.change_presence(activity=discord.CustomActivity(name="dischord.pages.dev | /join"))
        if not settings.auto_refresh_enabled:
            log.info("AUTO_REFRESH_ENABLED=false; skipping the scheduled 17lands refresh tick")
            return
        if not auto_refresh_tick.is_running():
            auto_refresh_tick.start()

    return bot


_LAST_TESTLOBBY_MESSAGE: dict[int, discord.Message] = {}


class _LobbyReadyButtonView(discord.ui.View):
    def __init__(
        self, draftmancer_url: str | None = None, ready_disabled: bool = False,
    ) -> None:
        super().__init__(timeout=None)
        if ready_disabled:
            self.ready_check.disabled = True
        if draftmancer_url:
            self.add_item(discord.ui.Button(
                label="Join Draftmancer",
                style=discord.ButtonStyle.link,
                url=draftmancer_url,
                emoji=emojis.get_emoji("draftmancer"),
                disabled=ready_disabled,
            ))

    @discord.ui.button(
        label="Ready Check", style=discord.ButtonStyle.success, custom_id="testlobby:ready",
    )
    async def ready_check(
        self, interaction: discord.Interaction, button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_message("Ready Check triggered (test).", ephemeral=True)


def _render_lobby_embed_v2(
    title: str,
    rsvps_yes: list[str],
    rsvps_maybe: list[str],
    in_session: list[tuple[str, str | None]],
    *,
    state: str,
    draftmancer_url: str | None = None,
    ready_count: int | None = None,
) -> discord.Embed:
    """Lobby embed. `title` is the thread/event name; `rsvps_yes` / `rsvps_maybe` are sesh display
    names by RSVP type; `in_session` is Draftmancer sessionUsers as (arena_name,
    linked_display_name_or_None). `draftmancer_url` appears under the header; `ready_count`
    (ready state only) is how many of in_draftmancer have responded.

    Buckets: In Draftmancer (linked + in session), Unrecognized name (in session, no Player row),
    Waiting on (Yes RSVP not in session), Maybe (Maybe RSVP not in session). Waiting + Maybe are
    hidden once ready check fires."""
    in_draftmancer = [(arena, dn) for arena, dn in in_session if dn is not None]
    unrecognized = [arena for arena, dn in in_session if dn is None]
    in_session_display_names = {dn for _, dn in in_draftmancer}
    waiting_yes = [name for name in rsvps_yes if name not in in_session_display_names]
    waiting_maybe = [name for name in rsvps_maybe if name not in in_session_display_names]
    show_pending = state not in ("ready", "drafting", "complete")

    ready_total = len(in_draftmancer)
    ready_now = ready_count if ready_count is not None else max(ready_total - 1, 0)
    if state == "ready":
        status = "### 🔔 Draftmancer Ready Check in progress!"
        color = discord.Color.gold()
    elif state == "notready":
        decliner = in_draftmancer[ready_now][0] if ready_now < len(in_draftmancer) else "(unknown)"
        status = f"### ❌ `{decliner}` is not ready, click Ready Check to retry"
        color = discord.Color.red()
    elif state == "drafting":
        status = "### 🎉 All players ready! Draft started"
        color = discord.Color.green()
    elif state == "complete":
        status = f"### {emojis.get('draftmancer')} Draft complete!"
        color = discord.Color.green()
    elif unrecognized:
        status = "### ⏳ Ready Check on hold until everyone is linked"
        color = discord.Color.orange()
    else:
        status = ""
        color = discord.Color.blurple()

    header_lines: list[str] = []
    if draftmancer_url:
        header_lines.append(f"### {draftmancer_url}")
    if status:
        header_lines.append(status)
    description = "\n".join(header_lines) if header_lines else None

    embed = discord.Embed(title=title, description=description, color=color)

    if state == "ready":
        ready_players = in_draftmancer[:ready_now]
        pending_players = in_draftmancer[ready_now:]
        ready_trailing = "\n​" if len(ready_players) > len(pending_players) else ""
        embed.add_field(
            name=f"✅ Ready ({len(ready_players)})",
            value=("\n".join(f"{dn} | {arena}" for arena, dn in ready_players) or "​") + ready_trailing,
            inline=True,
        )
        embed.add_field(
            name=f"⏳ Pending ({len(pending_players)})",
            value=("\n".join(f"{dn} | {arena}" for arena, dn in pending_players) or "​"),
            inline=True,
        )
    elif in_draftmancer:
        trailing = "\n​" if show_pending else ""
        in_drft_label = "Players" if state == "complete" else "In Draftmancer"
        embed.add_field(
            name=f"✅ {in_drft_label} ({len(in_draftmancer)})",
            value="\n".join(dn for _, dn in in_draftmancer) + trailing,
            inline=True,
        )
        embed.add_field(
            name="​",
            value="\n".join(f"`{arena}`" for arena, _ in in_draftmancer) + trailing,
            inline=True,
        )
        if show_pending:
            embed.add_field(name="​", value="​", inline=True)

    if show_pending:
        if unrecognized:
            embed.add_field(
                name=f"⚠️ Unrecognized ({len(unrecognized)})",
                value="\n".join(f"`{arena}`" for arena in unrecognized) + "\n​",
                inline=True,
            )
            embed.add_field(
                name="👉 How to fix",
                value="Run `/pod-link-arena` from inside this thread\n​",
                inline=True,
            )
            embed.add_field(name="​", value="​", inline=True)
        waiting_trailing = "\n​" if len(waiting_yes) > len(waiting_maybe) else ""
        embed.add_field(
            name=f"⌛ Waiting on ({len(waiting_yes)})",
            value=("\n".join(waiting_yes) or "​") + waiting_trailing,
            inline=True,
        )
        embed.add_field(
            name=f"🤷 Maybe ({len(waiting_maybe)})",
            value="\n".join(waiting_maybe) or "​",
            inline=True,
        )
        embed.add_field(name="​", value="​", inline=True)

    if state != "complete":
        embed.add_field(
            name="🤖 Commands",
            value=(
                "`/pod-takeover` — take ownership of the Draftmancer session if required\n"
                "`/pod-link-arena` — link your MTG Arena handle"
            ),
            inline=False,
        )
    return embed


def main() -> None:
    if settings.discord_bot_token is None or settings.discord_guild_id is None:
        raise SystemExit("DISCORD_BOT_TOKEN and DISCORD_GUILD_ID must be set to run the bot")

    configure_logging()
    run_migrations()

    signal.signal(signal.SIGTERM, lambda *_: signal.raise_signal(signal.SIGINT))

    bot = build_bot(settings.discord_guild_id)
    bot.run(settings.discord_bot_token.get_secret_value(), log_handler=None)


if __name__ == "__main__":
    main()
