"""Lobby embed renderer for pod-draft events.

Shared between `!testlobby` (sandbox) and the live `PodDraftManager` so both produce the same
visual. The Ready Check button is a persistent View (stable custom_id) registered once at
startup; clicks dispatch to the active manager for the thread.
"""
from __future__ import annotations

import logging

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
