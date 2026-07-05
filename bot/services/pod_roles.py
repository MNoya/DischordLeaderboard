"""Pod-draft notification roles — resolve, grant, and toggle the Pod Drafters / Euro Pod Drafter roles.

Logic only; the role-name constants live in bot/services/pod_schedule.py and the user-facing copy
lives with each caller (sesh listener auto-grant, /pod-roles toggle).
"""
from __future__ import annotations

import logging
import re

import discord


log = logging.getLogger(__name__)

_MENTION_RE = re.compile(r"^<@!?(\d+)>$")


def find_role(guild: discord.Guild | None, name: str) -> discord.Role | None:
    if guild is None:
        return None
    return discord.utils.get(guild.roles, name=name)


async def grant_role(member: discord.Member, role: discord.Role) -> bool:
    """Add the role if the member lacks it; True when a grant actually happened."""
    if role in member.roles:
        return False
    try:
        await member.add_roles(role, reason="pod-draft auto-grant")
        return True
    except discord.HTTPException:
        log.warning(f"could not grant {role.name} to {member}", exc_info=True)
        return False


async def toggle_role(member: discord.Member, role: discord.Role) -> bool | None:
    """Flip role membership for a member; returns the new held-state, or None on failure."""
    held = role in member.roles
    try:
        if held:
            await member.remove_roles(role, reason="pod-roles toggle")
        else:
            await member.add_roles(role, reason="pod-roles toggle")
        return not held
    except discord.HTTPException:
        log.warning(f"could not toggle {role.name} for {member}", exc_info=True)
        return None


async def resolve_member(guild: discord.Guild, token: str) -> discord.Member | None:
    """Map a sesh attendee token — either a <@id> mention or a display/username — to a guild member."""
    match = _MENTION_RE.match(token)
    if match is not None:
        user_id = int(match.group(1))
        member = guild.get_member(user_id)
        if member is not None:
            return member
        try:
            return await guild.fetch_member(user_id)
        except discord.HTTPException:
            return None
    lowered = token.lower()
    for member in guild.members:
        if member.display_name.lower() == lowered or member.name.lower() == lowered:
            return member
    return None
