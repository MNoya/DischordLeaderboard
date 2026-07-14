"""Self-assignable ping roles — the single registry every guild reconciles against.

`PING_ROLES` is the source of truth: name, color, the toggle-menu blurb, and an optional slot the
role is tied to (for showing its local time and auto-granting on RSVP). `reconcile_ping_roles`
makes every guild match this list — creating missing roles, recoloring drift, and renaming in place
when a name moves to `aliases`. To rename a role, set the new `name` and list the old name in
`aliases`; the reconcile finds the existing role by the alias and renames it instead of orphaning it.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import discord

from bot import emojis
from bot.services.pod_schedule import (
    EARLY_POD_ROLE_NAME,
    LATE_POD_ROLE_NAME,
    POD_DRAFTERS_ROLE_NAME,
    POD_QUEUE_ROLE_NAME,
    SATURDAY,
    SLOT_EMOJI_SATURDAY,
    THURSDAY,
    WEDNESDAY,
    WEEKEND_POD_ROLE_NAME,
    next_slot_datetime,
    slot_by_weekday,
    slot_for_event_time,
)


log = logging.getLogger(__name__)

MSG_ROLE_GRANTED = (
    "{emoji} {user} you're now on {role} and will be pinged for drafts {when}. "
    "Run `/roles` to manage your notifications."
)


@dataclass(frozen=True)
class PingRole:
    name: str
    emoji: str
    blurb: str
    color: str | None = None
    aliases: tuple[str, ...] = ()
    slot_weekday: int | None = None
    auto_grant: bool = False
    grant_when: str = "at this time of day"


PING_ROLES: tuple[PingRole, ...] = (
    PingRole(POD_DRAFTERS_ROLE_NAME, "llu", "Server-Wide Pod Announcements", color="#BFC9D4"),
    PingRole(
        EARLY_POD_ROLE_NAME, "💫", "Weekdays", color="#5CA8E0",
        aliases=("Early Pods", "Early Pod Drafters", "Euro Pod Drafters"), slot_weekday=THURSDAY, auto_grant=True,
    ),
    PingRole(
        LATE_POD_ROLE_NAME, "☄️", "Weekdays", color="#9B8AE6",
        aliases=("Late Pods", "Late Pod Drafters"), slot_weekday=WEDNESDAY, auto_grant=True,
    ),
    PingRole(
        WEEKEND_POD_ROLE_NAME, SLOT_EMOJI_SATURDAY, "Weekends", color="#D2B48C",
        aliases=("Weekend Pods", "Weekend Pod Drafters"), slot_weekday=SATURDAY, auto_grant=True,
        grant_when="on weekends",
    ),
    PingRole(POD_QUEUE_ROLE_NAME, "⚡", "On-Demand Pods with `/draft`", color="#FFAC33"),
)


def spec_named(name: str) -> PingRole | None:
    for spec in PING_ROLES:
        if spec.name == name:
            return spec
    return None


def button_custom_id(spec: PingRole) -> str:
    return f"role-toggle-{spec.name.lower().replace(' ', '-')}"


def blurb_with_time(spec: PingRole) -> str:
    """A slot role's menu line is its next occurrence, always in the future; the blurb text is the
    fallback for roles without a slot."""
    if spec.slot_weekday is None:
        return spec.blurb
    slot = slot_by_weekday(spec.slot_weekday)
    if slot is None:
        return spec.blurb
    unix = int(next_slot_datetime(slot).timestamp())
    return f"<t:{unix}:F>"


def display_emoji(spec: PingRole) -> str | None:
    return emojis.resolve(spec.emoji)


def build_grant_embed(user_mention: str, role: discord.Role, spec: PingRole) -> discord.Embed:
    """The embed announcing a fresh auto-grant in the event thread. Shared by the listener and tests.

    A role mention inside an embed never pings (only message content does), so the role tag is safe;
    it renders as the colored role pill from the viewer's role cache.
    """
    message = MSG_ROLE_GRANTED.format(
        emoji=display_emoji(spec) or "", user=user_mention, role=role.mention, when=spec.grant_when,
    )
    return discord.Embed(
        description=message,
        color=role.color if role.color.value else discord.Color.blurple(),
    )


def auto_grant_spec_for_event(event_time) -> PingRole | None:
    """The ping role auto-granted to RSVPs of the pod at this time, or None."""
    slot = slot_for_event_time(event_time)
    if slot is None:
        return None
    for spec in PING_ROLES:
        if spec.auto_grant and spec.slot_weekday == slot.weekday:
            return spec
    return None


async def reconcile_ping_roles(bot: discord.Client) -> None:
    """Make every guild's roles match PING_ROLES — create, rename-via-alias, and recolor as needed."""
    for guild in bot.guilds:
        me = guild.me
        if me is None or not me.guild_permissions.manage_roles:
            log.info(f"ping-role reconcile skipped in {guild.name}: missing Manage Roles")
            continue
        for spec in PING_ROLES:
            await _ensure_role(guild, spec)
        await _keep_umbrella_on_top(guild)


async def _keep_umbrella_on_top(guild: discord.Guild) -> None:
    """Members wear the gray Pod Drafters umbrella for their name color; every other ping role must
    sit below it in the hierarchy so its color stays a cosmetic mention-pill color."""
    umbrella = discord.utils.get(guild.roles, name=POD_DRAFTERS_ROLE_NAME)
    if umbrella is None:
        return
    for spec in PING_ROLES:
        if spec.name == POD_DRAFTERS_ROLE_NAME:
            continue
        role = discord.utils.get(guild.roles, name=spec.name)
        if role is None or role.position < umbrella.position:
            continue
        try:
            await role.edit(position=umbrella.position, reason="ping-role reorder below umbrella")
            log.info(f"moved {spec.name!r} below {POD_DRAFTERS_ROLE_NAME!r} in {guild.name}")
        except discord.HTTPException:
            log.warning(f"could not reorder {spec.name!r} in {guild.name}", exc_info=True)


async def _ensure_role(guild: discord.Guild, spec: PingRole) -> None:
    role = discord.utils.get(guild.roles, name=spec.name) or await _adopt_alias(guild, spec)
    if role is None:
        await _create_role(guild, spec)
        return
    for alias in spec.aliases:
        if discord.utils.get(guild.roles, name=alias) is not None:
            log.warning(f"both {spec.name!r} and stale alias {alias!r} exist in {guild.name}; delete the alias role")
    if spec.color is not None:
        wanted = discord.Colour.from_str(spec.color)
        if role.colour != wanted:
            try:
                await role.edit(colour=wanted, reason="ping-role recolor")
                log.info(f"recolored {spec.name!r} in {guild.name}")
            except discord.HTTPException:
                log.warning(f"could not recolor {spec.name!r} in {guild.name}", exc_info=True)


async def _adopt_alias(guild: discord.Guild, spec: PingRole) -> discord.Role | None:
    for alias in spec.aliases:
        existing = discord.utils.get(guild.roles, name=alias)
        if existing is None:
            continue
        try:
            await existing.edit(name=spec.name, reason="ping-role rename")
            log.info(f"renamed {alias!r} -> {spec.name!r} in {guild.name}")
        except discord.HTTPException:
            log.warning(f"could not rename {alias!r} in {guild.name}", exc_info=True)
        return existing
    return None


async def _create_role(guild: discord.Guild, spec: PingRole) -> None:
    kwargs = {"name": spec.name, "reason": "ping-role create"}
    if spec.color is not None:
        kwargs["colour"] = discord.Colour.from_str(spec.color)
    try:
        await guild.create_role(**kwargs)
        log.info(f"created {spec.name!r} in {guild.name}")
    except discord.HTTPException:
        log.warning(f"could not create {spec.name!r} in {guild.name}", exc_info=True)
