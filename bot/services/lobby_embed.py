"""Lobby embed renderer for pod-draft events.

Shared between `!test` (sandbox) and the live `PodDraftManager` so both produce the same
visual. The Ready Check button is a persistent View (stable custom_id) registered once at
startup; clicks dispatch to the active manager for the thread.
"""
from __future__ import annotations

import asyncio
import logging
import re

import discord

from bot import emojis
from bot.commands import descriptions as desc
from bot.discord_helpers import command_line
from bot.services.pod_drafts import load_event_id_by_thread_sync
from bot.services.pod_tournament import actor_label


log = logging.getLogger("bot.lobby_embed")

READY_CHECK_CUSTOM_ID = "pod-draft:ready-check"
SETTINGS_CUSTOM_ID = "pod-draft:settings"

_NO_ACTIVE_POD_MSG = "No active pod-draft session in this thread."


class LobbyReadyButtonView(discord.ui.View):
    def __init__(
        self, draftmancer_url: str | None = None, ready_disabled: bool = False,
    ) -> None:
        super().__init__(timeout=None)
        if ready_disabled:
            self.ready_check.disabled = True
        self.add_item(SettingsButton())
        if draftmancer_url:
            self.add_item(discord.ui.Button(
                label="Join Draftmancer",
                style=discord.ButtonStyle.link,
                url=draftmancer_url,
                emoji=emojis.get_emoji("draftmancer"),
            ))

    @discord.ui.button(
        label="Ready Check", style=discord.ButtonStyle.success,
        custom_id=READY_CHECK_CUSTOM_ID,
    )
    async def ready_check(
        self, interaction: discord.Interaction, button: discord.ui.Button,
    ) -> None:
        from bot.services.pod_active import ACTIVE_POD_MANAGERS
        channel = interaction.channel
        channel_id = channel.id if channel else None
        actor = actor_label(interaction)
        manager = next(
            (m for m in ACTIVE_POD_MANAGERS.values() if m.thread_id == channel_id),
            None,
        )
        if manager is None:
            log.info(f"{actor} clicked Ready Check in channel={channel_id} (no active pod)")
            await interaction.response.send_message(_NO_ACTIVE_POD_MSG, ephemeral=True)
            return
        log.info(f"[{manager.event_name}] {actor} clicked Ready Check")
        await interaction.response.defer(ephemeral=True)
        thread = await interaction.client.fetch_channel(manager.thread_id)
        err = await manager.initiate_ready_check(thread, initiated_by=actor)
        if err:
            await interaction.followup.send(f"⚠️ {err}", ephemeral=True)


class SettingsButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(
            label="Settings", style=discord.ButtonStyle.grey,
            custom_id=SETTINGS_CUSTOM_ID, emoji="⚙️",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await open_settings_panel(interaction)


async def open_settings_panel(interaction: discord.Interaction) -> None:
    """Resolve the thread's pod-draft event and open the ephemeral Settings panel. Resolution goes
    through the DB rather than ACTIVE_POD_MANAGERS so the button works from registration onward,
    before the Draftmancer session launches."""
    from bot.commands.pod_draft import build_pod_settings_view
    channel_id = interaction.channel_id
    actor = actor_label(interaction)
    thread_id = str(channel_id) if channel_id else None
    event_id = await asyncio.to_thread(load_event_id_by_thread_sync, thread_id) if thread_id else None
    if event_id is None:
        if _settings_preview_factory is not None:
            await interaction.response.send_message(view=_settings_preview_factory(), ephemeral=True)
            return
        log.info(f"{actor} clicked Settings in channel={channel_id} (no pod-draft event)")
        await interaction.response.send_message(_NO_ACTIVE_POD_MSG, ephemeral=True)
        return
    log.info(f"{actor} clicked Settings for event {event_id}")
    is_owner = await interaction.client.is_owner(interaction.user)
    await interaction.response.send_message(
        view=await build_pod_settings_view(interaction.client, event_id, is_owner=is_owner),
        ephemeral=True,
    )


def render(
    title: str,
    rsvps_yes: list[str],
    rsvps_maybe: list[str],
    in_session: list[tuple[str, str | None]],
    *,
    state: str,
    draftmancer_url: str | None = None,
    decliner_name: str | None = None,
    cancel_reason: str | None = None,
    initiated_by: str | None = None,
    display_name_by_mention_id: dict[int, str] | None = None,
    spectators: list[str] | None = None,
    format_label: str | None = None,
    pairing_label: str | None = None,
    seating_label: str | None = None,
) -> discord.Embed:
    """Lobby embed. `title` is the thread/event name; `rsvps_yes` / `rsvps_maybe` are sesh display
    names by RSVP type; `in_session` is Draftmancer sessionUsers as (arena_name,
    linked_display_name_or_None). `draftmancer_url` appears under the header.

    Buckets: In Draftmancer (linked + in session), Unrecognized name (in session, no Player row),
    Waiting on (Yes RSVP not in session), Maybe (Maybe RSVP not in session). Waiting + Maybe are
    hidden once ready check fires; the live Ready/Pending split lives on the separate ready-check
    progress card, not here. `spectators` lists Draftmancer sessionSpectators comma-separated below
    Maybe whenever any are present, regardless of state."""
    in_draftmancer = [(arena, dn) for arena, dn in in_session if dn is not None]
    unrecognized = [arena for arena, dn in in_session if dn is None]
    mention_map = display_name_by_mention_id or {}
    in_session_keys = {dn.lower() for _, dn in in_draftmancer if dn}
    in_session_keys |= {arena.lower() for arena, _ in in_session}
    waiting_yes = [
        name for name in rsvps_yes
        if _rsvp_dedup_key(name, mention_map) not in in_session_keys
    ]
    waiting_maybe = [
        name for name in rsvps_maybe
        if _rsvp_dedup_key(name, mention_map) not in in_session_keys
    ]
    show_pending = state not in ("ready", "drafting", "complete")

    banner_state = state
    if state not in ("ready", "notready", "drafting", "complete") and unrecognized:
        banner_state = "onhold"
    status_lines, color = ready_status_banner(
        banner_state, decliner_name=decliner_name, cancel_reason=cancel_reason,
        initiated_by=initiated_by,
    )

    header_lines: list[str] = []
    if draftmancer_url:
        header_lines.append(f"### {draftmancer_url}")
    header_lines.extend(status_lines)
    description = "\n".join(header_lines) if header_lines else None

    embed = discord.Embed(title=title, description=description, color=color)
    _set_settings_footer(embed, format_label, pairing_label, seating_label)

    if in_draftmancer:
        trailing = "\n​" if show_pending else ""
        in_drft_label = "Players" if state == "complete" else "In Draftmancer"
        _player_columns(
            embed, f"✅ {in_drft_label} ({len(in_draftmancer)})", in_draftmancer,
            trailing=trailing, spacer=show_pending,
        )

    if show_pending:
        if unrecognized:
            embed.add_field(
                name=f"⚠️ Unrecognized ({len(unrecognized)})",
                value="\n".join(f"`{arena}`" for arena in unrecognized) + "\n​",
                inline=True,
            )
            embed.add_field(
                name="👉 How to fix",
                value="Run `/link-arena` with your Arena handle\n​",
                inline=True,
            )
            embed.add_field(name="​", value="​", inline=True)
        waiting_trailing = "\n​" if len(waiting_yes) > len(waiting_maybe) else ""
        embed.add_field(
            name=f"⌛ Waiting on ({len(waiting_yes)})",
            value=_quote_block(waiting_yes, trailing=waiting_trailing),
            inline=True,
        )
        embed.add_field(
            name=f"🤷 Maybe ({len(waiting_maybe)})",
            value=_quote_block(waiting_maybe),
            inline=True,
        )
        embed.add_field(name="​", value="​", inline=True)

    if spectators:
        embed.add_field(
            name=f"👀 Spectators ({len(spectators)})",
            value=", ".join(spectators),
            inline=False,
        )

    if state != "complete":
        embed.add_field(
            name="🤖 Commands",
            value="\n".join([
                command_line("/link-arena", desc.LINK_ARENA_LOBBY),
                command_line("/pod-ready", desc.POD_READY),
                command_line("/pod-start", desc.POD_START),
                command_line("/pod-takeover", desc.POD_TAKEOVER),
            ]),
            inline=False,
        )
    return embed


def _set_settings_footer(
    embed: discord.Embed,
    format_label: str | None,
    pairing_label: str | None,
    seating_label: str | None,
) -> None:
    """Sticky Format / Pairings / Seats footer shared by the lobby card and the ready-check progress
    card so the pod's settings stay visible through every state."""
    parts = []
    if format_label:
        parts.append(f"Format: {format_label}")
    if pairing_label:
        parts.append(f"Pairings: {pairing_label}")
    if seating_label:
        parts.append(f"Seats: {seating_label}")
    if parts:
        embed.set_footer(text="  •  ".join(parts))


def render_ready_check_progress(
    title: str,
    in_session: list[tuple[str, str | None]],
    *,
    state: str,
    draftmancer_url: str | None = None,
    ready_arena_names: set[str] | None = None,
    decliner_name: str | None = None,
    cancel_reason: str | None = None,
    superseded: bool = False,
    initiated_by: str | None = None,
    ready_count: int | None = None,
    total_count: int | None = None,
    format_label: str | None = None,
    pairing_label: str | None = None,
    seating_label: str | None = None,
) -> discord.Embed:
    """Compact ready-check progress card.

    Posted fresh each ready check and updated in place as players respond, so the active card
    stays at the bottom of the thread even when the main lobby card has scrolled away.
    `state` mirrors the lobby state machine: 'ready', 'notready', 'drafting', 'complete', and
    falls through to a neutral header otherwise.

    A declined card ('notready', including the `superseded` stale variant) collapses to two lines —
    `❌ <name> is Not Ready` + `✅ ready_count/total_count Ready` — with no link, buttons, or roster,
    since the retry controls live on the main lobby card.
    """
    in_draftmancer = [(arena, dn) for arena, dn in in_session if dn is not None]

    declined = state == "notready"
    status_lines, color = ready_status_banner(
        state, decliner_name=decliner_name, cancel_reason=cancel_reason,
        initiated_by=initiated_by, retry_hint=False if declined else not superseded,
    )
    if not status_lines:
        status_lines = ["### Ready Check"]
    header_lines = [f"### {draftmancer_url}"] if draftmancer_url and not declined else []
    header_lines.extend(status_lines)
    if declined and ready_count is not None and total_count is not None:
        header_lines.append(f"### ✅ {ready_count}/{total_count} Ready")
    embed = discord.Embed(title=title, description="\n".join(header_lines), color=color)
    _set_settings_footer(embed, format_label, pairing_label, seating_label)

    if declined or superseded:
        return embed

    if state in ("drafting", "complete"):
        ready_players = in_draftmancer
        pending_players = []
    elif ready_arena_names is not None:
        ready_players = [(a, dn) for a, dn in in_draftmancer if a in ready_arena_names]
        pending_players = [(a, dn) for a, dn in in_draftmancer if a not in ready_arena_names]
    else:
        ready_players = []
        pending_players = in_draftmancer

    ready_label = "Players" if state == "complete" else "Ready"
    two_groups = bool(pending_players) or state == "ready"
    _player_columns(embed, f"✅ {ready_label} ({len(ready_players)})", ready_players, spacer=two_groups)
    if two_groups:
        _player_columns(embed, f"⏳ Pending ({len(pending_players)})", pending_players, spacer=True)
    return embed


def ready_status_banner(
    state: str,
    *,
    decliner_name: str | None = None,
    cancel_reason: str | None = None,
    initiated_by: str | None = None,
    retry_hint: bool = True,
) -> tuple[list[str], discord.Color]:
    """Status banner lines + color shared by the lobby card and the ready-check progress card so
    their wording never drifts. `retry_hint` appends the retry tail on a live failed check; pass
    False on a stale superseded card. Returns ([], blurple) for states with no banner."""
    if state == "ready":
        lines = ["### 🔔 Ready Check initiated! Accept on Draftmancer to start the draft"]
        if initiated_by:
            lines.append(f"-# Started by {initiated_by}")
        return lines, discord.Color.gold()
    if state == "drafting":
        return ["### 🎉 All players ready! Draft started"], discord.Color.green()
    if state == "complete":
        return [f"### {emojis.get('draftmancer')} Draft complete!"], discord.Color.green()
    if state == "notready":
        retry = "! Click Ready Check to retry" if retry_hint else ""
        reason = f"`{decliner_name}` is Not Ready" if decliner_name else (cancel_reason or "Ready Check cancelled")
        return [f"### ❌ {reason}{retry}"], discord.Color.red()
    if state == "onhold":
        return ["### ⏳ Ready Check on hold until everyone is linked"], discord.Color.orange()
    return [], discord.Color.blurple()


def _quote_block(lines: list[str], *, trailing: str = "") -> str:
    """`> `-prefix each line so Discord renders the blockquote vertical bar."""
    if not lines:
        return "​"
    return "\n".join(f"> {line}" for line in lines) + trailing


def _player_columns(
    embed: discord.Embed, label: str, players: list[tuple[str, str]], *,
    trailing: str = "", spacer: bool = False,
) -> None:
    """Two columns from `players` (arena_name, display_name): blockquoted names | code Arena
    handles. `spacer` closes the inline row when another group follows."""
    embed.add_field(name=label, value=_quote_block([dn for _, dn in players], trailing=trailing), inline=True)
    arenas = "\n".join(f"`{arena}`" for arena, _ in players)
    embed.add_field(name="​", value=(arenas or "​") + trailing, inline=True)
    if spacer:
        embed.add_field(name="​", value="​", inline=True)


def _rsvp_dedup_key(rsvp: str, display_name_by_mention_id: dict[int, str]) -> str:
    """Normalize an rsvp line to a lowercase comparison key. Handles both sesh formats:
    when sesh's `Display Usernames as Plain Text` is on, lines are bare display names;
    when off, lines are `<@id>` mention strings — we resolve those via the guild map."""
    text = rsvp.strip()
    mention_regex = re.compile(r"^<@!?(\d+)>$")
    m = mention_regex.match(text)
    if m:
        resolved = display_name_by_mention_id.get(int(m.group(1)))
        if resolved:
            return resolved.lower()
    return text.lower()

# testlobby injects a no-op Settings panel factory so the UI is previewable without a live pod
_settings_preview_factory = None


def register_settings_preview(factory) -> None:
    """Let the testlobby sandbox preview the Settings panel even though it has no live pod manager."""
    global _settings_preview_factory
    _settings_preview_factory = factory
