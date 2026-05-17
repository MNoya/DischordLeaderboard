"""Lobby embed renderer for pod-draft events.

Shared between `!testlobby` (sandbox) and the live `PodDraftManager` so both produce the same
visual. The Ready Check button is a persistent View (stable custom_id) registered once at
startup; clicks dispatch to the active manager for the thread.
"""
from __future__ import annotations

import logging
import re

import discord

from bot import emojis


log = logging.getLogger("bot.lobby_embed")

READY_CHECK_CUSTOM_ID = "pod-draft:ready-check"


class LobbyReadyButtonView(discord.ui.View):
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
        label="Ready Check", style=discord.ButtonStyle.success,
        custom_id=READY_CHECK_CUSTOM_ID,
    )
    async def ready_check(
        self, interaction: discord.Interaction, button: discord.ui.Button,
    ) -> None:
        from bot.services.pod_active import ACTIVE_POD_MANAGERS
        channel = interaction.channel
        channel_id = channel.id if channel else None
        manager = next(
            (m for m in ACTIVE_POD_MANAGERS.values() if m.thread_id == channel_id),
            None,
        )
        if manager is None:
            await interaction.response.send_message(
                "No active pod-draft session in this thread.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        thread = await interaction.client.fetch_channel(manager.thread_id)
        err = await manager.initiate_ready_check(thread)
        if err:
            await interaction.followup.send(f"⚠️ {err}", ephemeral=True)


def render(
    title: str,
    rsvps_yes: list[str],
    rsvps_maybe: list[str],
    in_session: list[tuple[str, str | None]],
    *,
    state: str,
    draftmancer_url: str | None = None,
    ready_count: int | None = None,
    decliner_name: str | None = None,
    cancel_reason: str | None = None,
    display_name_by_mention_id: dict[int, str] | None = None,
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
    mention_map = display_name_by_mention_id or {}
    in_session_keys = {dn.lower() for _, dn in in_draftmancer if dn}
    waiting_yes = [
        name for name in rsvps_yes
        if _rsvp_dedup_key(name, mention_map) not in in_session_keys
    ]
    waiting_maybe = [
        name for name in rsvps_maybe
        if _rsvp_dedup_key(name, mention_map) not in in_session_keys
    ]
    show_pending = state not in ("ready", "drafting", "complete")

    ready_total = len(in_draftmancer)
    ready_now = ready_count if ready_count is not None else max(ready_total - 1, 0)
    if state == "ready":
        status = "### 🔔 Draftmancer Ready Check in progress!"
        color = discord.Color.gold()
    elif state == "notready":
        if decliner_name is None and cancel_reason is None:
            # testlobby fallback: pick the trailing in-Draftmancer entry as the decliner
            decliner_name = (
                in_draftmancer[ready_now][0] if ready_now < len(in_draftmancer) else "(unknown)"
            )
        if decliner_name:
            status = f"### ❌ `{decliner_name}` is not ready, click Ready Check to retry"
        else:
            status = f"### ❌ {cancel_reason}, click Ready Check to retry"
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

    def _block(lines: list[str], *, trailing: str = "") -> str:
        """`> name`-prefix each line so Discord renders the blockquote vertical bar."""
        if not lines:
            return "​"
        return "\n".join(f"> {line}" for line in lines) + trailing

    if state == "ready":
        ready_players = in_draftmancer[:ready_now]
        pending_players = in_draftmancer[ready_now:]
        ready_trailing = "\n​" if len(ready_players) > len(pending_players) else ""
        embed.add_field(
            name=f"✅ Ready ({len(ready_players)})",
            value=_block([f"{dn} | {arena}" for arena, dn in ready_players], trailing=ready_trailing),
            inline=True,
        )
        embed.add_field(
            name=f"⏳ Pending ({len(pending_players)})",
            value=_block([f"{dn} | {arena}" for arena, dn in pending_players]),
            inline=True,
        )
    elif in_draftmancer:
        trailing = "\n​" if show_pending else ""
        in_drft_label = "Players" if state == "complete" else "In Draftmancer"
        embed.add_field(
            name=f"✅ {in_drft_label} ({len(in_draftmancer)})",
            value=_block([dn for _, dn in in_draftmancer], trailing=trailing),
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
            value=_block(waiting_yes, trailing=waiting_trailing),
            inline=True,
        )
        embed.add_field(
            name=f"🤷 Maybe ({len(waiting_maybe)})",
            value=_block(waiting_maybe),
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
