from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import audit, emojis
from bot.commands import descriptions as desc
from bot.commands import token_messages as tmsg
from bot.commands.leaderboard import broadcast_current_set_safely
from bot.commands.messages import MSG_JOINED_LEADERBOARD
from bot.database import SessionLocal
from bot.discord_helpers import extract_avatar_hash
from bot.models import Player
from bot.services import bot_log
from bot.services.dm_flows import run_latest_flow, send_token_instructions, wait_for_token_reply
from bot.services.refresh import refresh_one_player_for_all_sets
from bot.services.seventeenlands import SeventeenLandsClient
from bot.services.token_link import link_token, outcome_log_suffix

logger = logging.getLogger(__name__)

DM_TIMEOUT_S = 10 * 60
PROMPT_TIMEOUT_S = 10 * 60

LEADERBOARD_URL = "https://dischord.pages.dev/leaderboard"

INSTRUCTIONS = (
    "**Link your 17lands profile** to track your games.\n"
    + tmsg.WALKTHROUGH_STEPS + "\n"
    "\n"
    + tmsg.TOKEN_PRIVACY_NOTE
)

MSG_DM_SENT = "📬 Check your DMs to finish linking 17lands."
MSG_TIMEOUT = "⏱️ Timed out. Run `/link-17lands` whenever you're ready to try again."
MSG_LINK_OFF_BOARD = f"17lands linked! Want to join the [live leaderboard](<{LEADERBOARD_URL}>)?"
MSG_LINK_ON_BOARD = f"17lands updated! You're on the [leaderboard](<{LEADERBOARD_URL}>)."
MSG_LEFT = "👋 You've left the leaderboard. Your games still count for pods — run `/join` anytime to return."
MSG_STAYED_OFF = "👍 You're off the leaderboard. Your games are still tracked for pods, and you can `/join` anytime."
MSG_STAYED_ON = "👍 You're still on the leaderboard."


def link_prompt(currently_in: bool) -> str:
    icon = emojis.get("17lands") or "✅"
    return f"{icon} {MSG_LINK_ON_BOARD if currently_in else MSG_LINK_OFF_BOARD}"


class LeaderboardChoicePrompt(discord.ui.View):
    """Post-link choice that lets a player join or leave the leaderboard from whichever state they're in."""

    def __init__(self, bot: commands.Bot, user_id: str, player_id: str, *, currently_in: bool) -> None:
        super().__init__(timeout=PROMPT_TIMEOUT_S)
        self.bot = bot
        self.user_id = user_id
        self.player_id = player_id
        self.currently_in = currently_in
        self.message: discord.Message | None = None

        if currently_in:
            self._add_button("Leave the leaderboard", discord.ButtonStyle.danger, self._leave)
            self._add_button("Stay on", discord.ButtonStyle.secondary, self._keep)
        else:
            self._add_button("Join the leaderboard", discord.ButtonStyle.success, self._join)
            self._add_button("Stay off", discord.ButtonStyle.secondary, self._keep)

    def _add_button(self, label: str, style: discord.ButtonStyle, callback) -> None:
        button = discord.ui.Button(label=label, style=style)
        button.callback = callback
        self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    async def _join(self, interaction: discord.Interaction) -> None:
        display_name = self._set_membership(active=True, opt_in=True)
        audit.event("link_17lands_join", user_id=self.user_id, player_id=self.player_id)
        await self._finish(interaction, MSG_JOINED_LEADERBOARD)
        await broadcast_current_set_safely(self.bot)
        if display_name:
            await bot_log.get(self.bot).post_plain(f"🆕 **{display_name}** joined the leaderboard")

    async def _leave(self, interaction: discord.Interaction) -> None:
        display_name = self._set_membership(opt_in=False)
        audit.event("link_17lands_leave", user_id=self.user_id, player_id=self.player_id)
        await self._finish(interaction, MSG_LEFT)
        await broadcast_current_set_safely(self.bot)
        if display_name:
            await bot_log.get(self.bot).post_plain(f"👋 **{display_name}** left the leaderboard")

    async def _keep(self, interaction: discord.Interaction) -> None:
        audit.event("link_17lands_no_change", user_id=self.user_id, player_id=self.player_id)
        await self._finish(interaction, MSG_STAYED_ON if self.currently_in else MSG_STAYED_OFF)

    async def _finish(self, interaction: discord.Interaction, content: str) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=content, view=self)
        self.stop()

    def _set_membership(self, *, opt_in: bool, active: bool | None = None) -> str | None:
        with SessionLocal() as session:
            player = session.get(Player, self.player_id)
            if player is None:
                return None
            player.leaderboard_opt_in = opt_in
            if active is not None:
                player.active = active
            display_name = player.display_name
            session.commit()
        return display_name


class Link17Lands(commands.Cog):
    def __init__(self, bot: commands.Bot, client: SeventeenLandsClient | None = None) -> None:
        self.bot = bot
        self.client = client or SeventeenLandsClient()

    @app_commands.command(name="link-17lands", description=desc.LINK_17LANDS)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def link_17lands(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        username = str(interaction.user)
        audit.event("link_17lands_invoked", user_id=user_id, username=username)
        logger.info(f"link-17lands: {username} invoked")

        await run_latest_flow(user_id, self._run_link_flow(interaction, user_id, username))

    async def _run_link_flow(self, interaction: discord.Interaction, user_id: str, username: str) -> None:
        in_guild = interaction.guild is not None
        await interaction.response.defer(ephemeral=in_guild, thinking=True)
        try:
            dm = await interaction.user.create_dm()
            if in_guild:
                await send_token_instructions(dm.send, INSTRUCTIONS)
                await interaction.followup.send(MSG_DM_SENT, ephemeral=True)
            else:
                await send_token_instructions(interaction.followup.send, INSTRUCTIONS)
        except discord.Forbidden:
            audit.event("link_17lands_dms_disabled", user_id=user_id)
            logger.warning(f"link-17lands: {username} DMs blocked")
            await interaction.followup.send(tmsg.DMS_DISABLED, ephemeral=in_guild)
            return

        audit.event("link_17lands_dm_sent", user_id=user_id)

        reply_text = await wait_for_token_reply(self.bot, interaction, timeout_s=DM_TIMEOUT_S)
        if reply_text is None:
            audit.event("link_17lands_timeout", user_id=user_id)
            logger.info(f"link-17lands: {username} timed out")
            await dm.send(MSG_TIMEOUT)
            return

        await dm.send(tmsg.CHECKING)

        with SessionLocal() as session:
            result = link_token(
                session, self.client, user_id, username,
                interaction.user.display_name, reply_text, extract_avatar_hash(interaction.user),
                opt_in=False,
            )

        audit.event("link_17lands_result", user_id=user_id, kind=result.kind, player_id=result.player_id)
        logger.info(f"link-17lands: {username} → {result.kind} {outcome_log_suffix(result.kind, reply_text)}")

        if result.kind == "invalid_format":
            await dm.send(tmsg.INVALID_FORMAT)
            return
        if result.kind == "rejected_by_17lands":
            await dm.send(tmsg.REJECTED)
            return
        if result.kind == "token_in_use":
            await dm.send(tmsg.TOKEN_IN_USE)
            return

        with SessionLocal() as session:
            refresh_one_player_for_all_sets(session, self.client, result.player_id)
            session.commit()

        with SessionLocal() as session:
            player = session.get(Player, result.player_id)
            currently_in = bool(player and player.active and player.leaderboard_opt_in)

        if currently_in:
            await broadcast_current_set_safely(self.bot)

        view = LeaderboardChoicePrompt(self.bot, user_id, result.player_id, currently_in=currently_in)
        view.message = await dm.send(link_prompt(currently_in), view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Link17Lands(bot))
