"""`/roles` — self-serve toggle menu for the self-assignable ping roles in PING_ROLES.

A Components V2 LayoutView: one Section per registry role, its blurb (and local time, if it maps to a
slot) on the left and a toggle button on the right (green = subscribed). Each click toggles the role
for the caller and edits the message in place. The view is persistent (timeout=None, static custom_ids
derived from role names) and registered at startup so buttons keep dispatching after a restart.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.commands import descriptions as desc
from bot.config import settings
from bot.services.ping_roles import PING_ROLES, blurb_with_time, button_custom_id, display_emoji
from bot.services.pod_roles import find_role, grant_pod_drafters, grant_role, toggle_role
from bot.services.pod_schedule import POD_DRAFTERS_ROLE_NAME


log = logging.getLogger(__name__)

MSG_INTRO = "Toggle your notifications. Green means subscribed. Times shown in your timezone."
MSG_NO_GUILD = "Run `/roles` in the server to manage your notifications."
MSG_ROLE_MISSING = "That role isn't set up on the server. Ask an admin."
MSG_ROLE_TOGGLE_FAILED = "Couldn't update that role. The bot is missing the Manage Roles permission."


class _RoleToggleButton(discord.ui.Button):
    """A unicode emoji rides in the label so it renders right of the name; a custom emoji can't
    appear in label text, so it stays in the emoji slot on the left."""

    def __init__(self, role_name: str, emoji: str | None, custom_id: str, held: bool) -> None:
        unicode_emoji = emoji if emoji is not None and not emoji.startswith("<") else None
        super().__init__(
            label=f"{role_name} {unicode_emoji}" if unicode_emoji else role_name,
            emoji=None if unicode_emoji else emoji,
            custom_id=custom_id,
            style=discord.ButtonStyle.success if held else discord.ButtonStyle.secondary,
        )
        self.role_name = role_name

    async def callback(self, interaction: discord.Interaction) -> None:
        member, guild = await _resolve_member(interaction)
        if member is None or guild is None:
            await interaction.response.send_message(MSG_NO_GUILD, ephemeral=True)
            return
        role = find_role(guild, self.role_name)
        if role is None:
            await interaction.response.send_message(MSG_ROLE_MISSING, ephemeral=True)
            return
        new_state = await toggle_role(member, role)
        if new_state is None:
            await interaction.response.send_message(MSG_ROLE_TOGGLE_FAILED, ephemeral=True)
            return
        refreshed = guild.get_member(member.id) or member
        held = {held_role.name for held_role in refreshed.roles}
        held.add(self.role_name) if new_state else held.discard(self.role_name)
        if new_state and self.role_name != POD_DRAFTERS_ROLE_NAME:
            if await grant_pod_drafters(refreshed):
                held.add(POD_DRAFTERS_ROLE_NAME)
        if not new_state and self.role_name == POD_DRAFTERS_ROLE_NAME:
            held -= {spec.name for spec in PING_ROLES}
        await interaction.response.edit_message(view=RolesView(held, guild))


class RolesView(discord.ui.LayoutView):
    def __init__(self, held: set[str] | None = None, guild: discord.Guild | None = None) -> None:
        super().__init__(timeout=None)
        held = held or set()
        self.add_item(discord.ui.TextDisplay(MSG_INTRO))
        for spec in PING_ROLES:
            button = _RoleToggleButton(spec.name, display_emoji(spec), button_custom_id(spec), spec.name in held)
            role = find_role(guild, spec.name)
            blurb = blurb_with_time(spec)
            line = f"{role.mention} {blurb}" if role else blurb
            self.add_item(discord.ui.Section(discord.ui.TextDisplay(line), accessory=button))


async def _resolve_member(
    interaction: discord.Interaction,
) -> tuple[discord.Member | None, discord.Guild | None]:
    if interaction.guild is not None and isinstance(interaction.user, discord.Member):
        return interaction.user, interaction.guild
    guild = interaction.client.get_guild(settings.discord_guild_id) if settings.discord_guild_id else None
    if guild is None:
        return None, None
    member = guild.get_member(interaction.user.id)
    if member is None:
        try:
            member = await guild.fetch_member(interaction.user.id)
        except discord.HTTPException:
            return None, None
    return member, guild


class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Dropping Pod Drafters means leaving pod notifications entirely: the umbrella carries the
        one name color for pod players, so the slot roles go with it instead of surviving as a
        colored back door. The server's onboarding question removes the umbrella directly, which is
        what lands here."""
        before_names = {role.name for role in before.roles}
        after_names = {role.name for role in after.roles}
        if POD_DRAFTERS_ROLE_NAME not in before_names or POD_DRAFTERS_ROLE_NAME in after_names:
            return
        other_ping_roles = {spec.name for spec in PING_ROLES if spec.name != POD_DRAFTERS_ROLE_NAME}
        held = [role for role in after.roles if role.name in other_ping_roles]
        if not held:
            return
        try:
            await after.remove_roles(*held, reason="Pod Drafters removed; clearing slot roles with it")
            log.info(f"cleared {[role.name for role in held]} from {after} after {POD_DRAFTERS_ROLE_NAME} removal")
        except discord.HTTPException:
            log.warning(f"could not clear slot roles from {after}", exc_info=True)

    @app_commands.command(name="roles", description=desc.ROLES)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def roles(self, interaction: discord.Interaction) -> None:
        member, guild = await _resolve_member(interaction)
        if member is None:
            await interaction.response.send_message(MSG_NO_GUILD, ephemeral=True)
            return
        held = {role.name for role in member.roles}
        await interaction.response.send_message(
            view=RolesView(held, guild),
            ephemeral=(interaction.guild is not None),
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Roles(bot))

    @bot.command(name="grant-roles")
    @commands.is_owner()
    async def grant_roles(ctx: commands.Context) -> None:
        """Owner-only, idempotent: grant Pod Drafters to every member holding any other ping role,
        so anyone in anything pod-related wears the umbrella name color."""
        reports = []
        for guild in bot.guilds:
            umbrella = find_role(guild, POD_DRAFTERS_ROLE_NAME)
            if umbrella is None:
                reports.append(f"{guild.name}: missing {POD_DRAFTERS_ROLE_NAME} — run after the startup reconcile")
                continue
            holders_by_role: dict[str, set[discord.Member]] = {}
            for spec in PING_ROLES:
                if spec.name == POD_DRAFTERS_ROLE_NAME:
                    continue
                role = find_role(guild, spec.name)
                if role is not None:
                    holders_by_role[spec.name] = set(role.members)
            holders = set().union(*holders_by_role.values()) if holders_by_role else set()
            newly_granted: set[discord.Member] = set()
            for member in holders:
                if await grant_role(member, umbrella):
                    newly_granted.add(member)
            by_role = ", ".join(
                f"{name} {len(newly_granted & members)}"
                for name, members in holders_by_role.items()
                if newly_granted & members
            )
            breakdown = f" ({by_role})" if by_role else ""
            reports.append(
                f"{guild.name}: granted {umbrella.name} to {len(newly_granted)} of {len(holders)} "
                f"pod-role members{breakdown}"
            )
        await ctx.send("\n".join(reports) if reports else "No guilds.")
