from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import audit, emojis
from bot.commands import descriptions as desc
from bot.commands import token_messages as tmsg
from bot.commands.leaderboard import broadcast_current_set_safely
from bot.database import SessionLocal
from bot.discord_helpers import extract_avatar_hash
from bot.models import Player
from bot.services import bot_log
from bot.services.dm_flows import run_latest_flow, wait_for_token_reply
from bot.services.leaderboard_visibility import MSG_JOINED_LEADERBOARD
from bot.services.refresh import refresh_one_player_for_all_sets
from bot.services.seventeenlands import SeventeenLandsClient
from bot.services.token_link import link_token, outcome_log_suffix

logger = logging.getLogger(__name__)

DM_TIMEOUT_S = 10 * 60
PROMPT_TIMEOUT_S = 10 * 60

INSTRUCTIONS = (
    "Reply with your **17lands profile URL or token**, for example:\n"
    "`https://www.17lands.com/user_history/10c0f8918a2b4fa7b230448caee0b2ca`\n"
    "\n"
    "*Your token is stored securely and only used to fetch your game data.*"
)

MSG_DM_SENT = "📬 Check your DMs to finish linking 17lands."
MSG_TIMEOUT = "⏱️ Timed out. Run `/link-17lands` whenever you're ready to try again."
MSG_LINKED_PROMPT = "✅ 17lands linked! Do you also want to join the [live leaderboard](https://dischord.pages.dev/leaderboard)?"
MSG_STAYED_OFF = "👍 You're off the leaderboard. Your games are still tracked for pods, and you can `/join` anytime"
MSG_UPDATED = "Updated. Your latest stats are on the [leaderboard](https://dischord.pages.dev/leaderboard)"
MSG_UPDATED_HIDDEN = "Updated. Your rank stays hidden. Run `/join` to appear on the [leaderboard](https://dischord.pages.dev/leaderboard)"


def updated_message(opted_in: bool) -> str:
    icon = emojis.get("17lands") or "✅"
    return f"{icon} {MSG_UPDATED if opted_in else MSG_UPDATED_HIDDEN}"


class JoinLeaderboardPrompt(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: str, player_id: str) -> None:
        super().__init__(timeout=PROMPT_TIMEOUT_S)
        self.bot = bot
        self.user_id = user_id
        self.player_id = player_id
        self.message: discord.Message | None = None

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

    @discord.ui.button(label="Join the leaderboard", style=discord.ButtonStyle.success)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        with SessionLocal() as session:
            player = session.get(Player, self.player_id)
            display_name = player.display_name if player else None
            if player is not None:
                player.leaderboard_opt_in = True
                session.commit()
        audit.event("link_17lands_join", user_id=self.user_id, player_id=self.player_id)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=MSG_JOINED_LEADERBOARD, view=self)
        self.stop()
        await broadcast_current_set_safely(self.bot)
        if display_name:
            await bot_log.get(self.bot).post_plain(f"🆕 **{display_name}** joined the leaderboard")

    @discord.ui.button(label="No thanks", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        audit.event("link_17lands_decline", user_id=self.user_id, player_id=self.player_id)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=MSG_STAYED_OFF, view=self)
        self.stop()


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
        try:
            dm = await interaction.user.create_dm()
            if in_guild:
                await dm.send(INSTRUCTIONS)
                await interaction.response.send_message(MSG_DM_SENT, ephemeral=True)
            else:
                await interaction.response.send_message(INSTRUCTIONS)
        except discord.Forbidden:
            audit.event("link_17lands_dms_disabled", user_id=user_id)
            logger.warning(f"link-17lands: {username} DMs blocked")
            await interaction.response.send_message(tmsg.DMS_DISABLED, ephemeral=in_guild)
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

        if result.relinked:
            with SessionLocal() as session:
                player = session.get(Player, result.player_id)
                opted_in = bool(player and player.leaderboard_opt_in)
            await dm.send(updated_message(opted_in))
            return

        view = JoinLeaderboardPrompt(self.bot, user_id, result.player_id)
        view.message = await dm.send(MSG_LINKED_PROMPT, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Link17Lands(bot))
