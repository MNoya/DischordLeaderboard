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
from bot.services.ping_roles import PING_ROLES, blurb_with_time, button_custom_id
from bot.services.pod_roles import find_role, toggle_role


log = logging.getLogger(__name__)

MSG_INTRO = "Toggle your notifications. Green means subscribed. Times shown in your timezone."
MSG_NO_GUILD = "Run `/roles` in the server to manage your notifications."
MSG_ROLE_MISSING = "That role isn't set up on the server. Ask an admin."
MSG_ROLE_TOGGLE_FAILED = "Couldn't update that role. The bot is missing the Manage Roles permission."


class _RoleToggleButton(discord.ui.Button):
    def __init__(self, role_name: str, emoji: str, custom_id: str, held: bool) -> None:
        super().__init__(
            label=role_name, emoji=emoji, custom_id=custom_id,
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
        await interaction.response.edit_message(view=RolesView(held))


class RolesView(discord.ui.LayoutView):
    def __init__(self, held: set[str] | None = None) -> None:
        super().__init__(timeout=None)
        held = held or set()
        self.add_item(discord.ui.TextDisplay(MSG_INTRO))
        for spec in PING_ROLES:
            button = _RoleToggleButton(spec.name, spec.emoji, button_custom_id(spec), spec.name in held)
            self.add_item(discord.ui.Section(discord.ui.TextDisplay(blurb_with_time(spec)), accessory=button))


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

    @app_commands.command(name="roles", description=desc.ROLES)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def roles(self, interaction: discord.Interaction) -> None:
        member, _ = await _resolve_member(interaction)
        if member is None:
            await interaction.response.send_message(MSG_NO_GUILD, ephemeral=True)
            return
        held = {role.name for role in member.roles}
        await interaction.response.send_message(view=RolesView(held), ephemeral=(interaction.guild is not None))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Roles(bot))
