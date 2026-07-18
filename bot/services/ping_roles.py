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
from bot.commands.messages import MSG_POD_ROLE_GRANTED, MSG_POD_WELCOME
from bot.discord_helpers import post_welcome
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
)
from bot.services.pod_signals import WEEKEND_BUCKETS, slot_event_time, slot_role_name_for_event_time


log = logging.getLogger(__name__)

QUEUE_GRANT_PING = "when a queue opens or needs more players"


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
    PingRole(POD_DRAFTERS_ROLE_NAME, "llu", "Server-Wide Pod Announcements", color="#C0C0C0"),
    PingRole(
        EARLY_POD_ROLE_NAME, "💫", "Weekdays", color="#5CA8E0",
        aliases=("Early Pods", "Early Pod Drafters", "Euro Pod Drafters"), slot_weekday=THURSDAY, auto_grant=True,
    ),
    PingRole(
        LATE_POD_ROLE_NAME, "☄️", "Weekdays", color="#9B8AE6",
        aliases=("Late Pods", "Late Pod Drafters"), slot_weekday=WEDNESDAY, auto_grant=True,
    ),
    PingRole(
        WEEKEND_POD_ROLE_NAME, SLOT_EMOJI_SATURDAY, "", color="#D2B48C",
        aliases=("Weekend Pods", "Weekend Pod Drafters"), slot_weekday=SATURDAY, auto_grant=True,
        grant_when="on weekends",
    ),
    PingRole(POD_QUEUE_ROLE_NAME, "⚡", "Daily Draft Sign-Ups", color="#FFAC33"),
)


def spec_named(name: str) -> PingRole | None:
    for spec in PING_ROLES:
        if spec.name == name:
            return spec
    return None


def button_custom_id(spec: PingRole) -> str:
    return f"role-toggle-{spec.name.lower().replace(' ', '-')}"


def blurb_with_time(spec: PingRole) -> str:
    """A slot role pairs its blurb with its recurring local times: one for a weekday slot, all three
    weekend buckets for the weekend role. Roles with no slot show their blurb alone."""
    if spec.slot_weekday is None:
        return spec.blurb
    slot = slot_by_weekday(spec.slot_weekday)
    if slot is None:
        return spec.blurb
    slot_date = next_slot_datetime(slot).date()
    if spec.slot_weekday >= SATURDAY:
        stamps = [slot_event_time(slot_date, bucket.key) for bucket in WEEKEND_BUCKETS]
    else:
        stamps = [next_slot_datetime(slot)]
    times = ", ".join(f"<t:{int(stamp.timestamp())}:t>" for stamp in stamps)
    return f"{spec.blurb} at {times}" if spec.blurb else f"at {times}"


def display_emoji(spec: PingRole) -> str | None:
    return emojis.resolve(spec.emoji)


def slot_grant_ping(spec: PingRole) -> str:
    return f"for drafts {spec.grant_when}"


def pod_role_grant_text(
    role_mention: str, ping: str, *, emoji: str = "", member_mention: str | None = None,
) -> str:
    """One role-grant line for every surface: `member_mention` set addresses a member by mention for a
    public thread post, unset addresses the clicker for an ephemeral reply."""
    if member_mention:
        subject = f"{emoji} {member_mention} you're".strip()
    else:
        subject = f"{emoji} You're".strip()
    return MSG_POD_ROLE_GRANTED.format(subject=subject, role=role_mention, ping=ping)


def build_grant_embed(
    user_mention: str, role: discord.Role, spec: PingRole, *, ping: str | None = None,
) -> discord.Embed:
    """The embed announcing a fresh auto-grant in the event thread. Shared by the listener and tests.

    A role mention inside an embed never pings (only message content does), so the role tag is safe;
    it renders as the colored role pill from the viewer's role cache.
    """
    message = pod_role_grant_text(
        role.mention, ping or slot_grant_ping(spec),
        emoji=display_emoji(spec) or "", member_mention=user_mention,
    )
    return discord.Embed(
        description=message,
        color=role.color if role.color.value else discord.Color.blurple(),
    )


def build_welcome_view(
    guild: discord.Guild, user_mention: str, slot_role: discord.Role | None, *, ping: str | None = None,
) -> discord.ui.LayoutView:
    """First-pod welcome as a Components V2 container: a green accent card whose text block behaves as
    message content, so the newcomer mention pings where an embed mention would stay silent. Folds in
    the role grant for a one-message welcome; returning drafters get `build_grant_embed` instead."""
    umbrella = discord.utils.get(guild.roles, name=POD_DRAFTERS_ROLE_NAME)
    pod_drafters = umbrella.mention if umbrella is not None else POD_DRAFTERS_ROLE_NAME
    if slot_role is not None and ping is not None:
        grant = f"You're now on {slot_role.mention} and will be pinged {ping}. "
    else:
        grant = ""
    message = MSG_POD_WELCOME.format(user=user_mention, pod_drafters=pod_drafters, grant=grant)
    return _WelcomeView(message)


class _WelcomeView(discord.ui.LayoutView):
    def __init__(self, text: str) -> None:
        super().__init__(timeout=None)
        container = discord.ui.Container(accent_colour=discord.Color.green())
        container.add_item(discord.ui.TextDisplay(text))
        self.add_item(container)


async def announce_pod_grant(
    interaction: discord.Interaction, *, first_pod: bool,
    granted_role: discord.Role | None, welcome_role: discord.Role | None,
    spec: PingRole | None, ping: str | None,
) -> None:
    """The post-join notice every signal surface shares: a first-ever drafter gets the public welcome
    in pod-draft-chat, folding in `welcome_role`; a returning drafter who freshly picked up a slot role
    gets the ephemeral grant embed; anyone else gets nothing. `granted_role` gates the returning case
    on an actual fresh grant, so a re-click never re-announces."""
    if first_pod:
        welcome = build_welcome_view(interaction.guild, interaction.user.mention, welcome_role, ping=ping)
        await post_welcome(interaction, welcome)
    elif granted_role is not None:
        grant = build_grant_embed(interaction.user.mention, granted_role, spec, ping=ping)
        await interaction.followup.send(
            embed=grant, ephemeral=True, allowed_mentions=discord.AllowedMentions.none(),
        )


def auto_grant_spec_for_event(event_time) -> PingRole | None:
    """The ping role auto-granted to RSVPs of the pod at this time, or None. Resolves off the poll
    buckets (weekend + time-of-day), so a launcher pod and a weekly-schedule pod at the same slot map
    to the same role regardless of weekday."""
    role_name = slot_role_name_for_event_time(event_time)
    if role_name is None:
        return None
    spec = spec_named(role_name)
    return spec if spec is not None and spec.auto_grant else None


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


async def strip_pod_roles(member: discord.Member) -> int:
    """Remove the auto-granted pod ping roles — the slot roles plus the Pod Drafters umbrella — from
    one member. Backs `!test reset` so the tester's own re-test starts with no leftover grants; the
    opt-in-only Pod Queue role is left alone. Returns the number of roles removed."""
    target_names = {POD_DRAFTERS_ROLE_NAME} | {spec.name for spec in PING_ROLES if spec.auto_grant}
    roles = [role for role in member.roles if role.name in target_names]
    if not roles:
        return 0
    try:
        await member.remove_roles(*roles, reason="test reset")
    except discord.HTTPException:
        log.warning(f"could not strip pod roles from {member.id} in {member.guild.name}", exc_info=True)
        return 0
    return len(roles)


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
