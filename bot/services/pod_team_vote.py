"""Team-Draft vote offer posted as its own embed card on a settled small pod: a prompt and the current
voters, with one button to vote. A distinct thread message, not an edit to the lobby card, so it reads as
a call to action — styled like the /pod-table card. The voters are listed plainly with no counter; the
majority is easy to eyeball. The manager owns the tally and the lock; this module owns the card and the
button so the live message and the `!test` preview can't drift.
"""
from __future__ import annotations

import re

import discord
from discord import ui

from bot import emojis
from bot.services.pod_active import ACTIVE_POD_MANAGERS


TEAM_VOTE_POD_SIZE = 6
TEAM_VOTE_PROMPT = "{count} Players locked in! Make it a Team Draft?"
TEAM_VOTE_GATHERING = "Turns into a Team Draft once {needed} players vote."
TEAM_VOTE_LOCKED_TITLE = "🤝 Team Draft is on!"
TEAM_VOTE_TALLY = "Votes ({count})"
TEAM_VOTE_EMOJI = "🤝"
TEAM_VOTE_BUTTON_LABEL = "Team Draft"
VOTE_BUTTON_PREFIX = "podteamvote"


def team_vote_needed(pod_size: int) -> int:
    """Votes to lock Team Draft: a majority of the pod."""
    return pod_size // 2 + 1


def build_team_vote_offer_embed(voter_names: list[str], needed: int, *, locked: bool = False) -> discord.Embed:
    """The offer card, shaped like the pod-table card: the description carries the instruction, a
    `Votes (N)` field carries the voters. While gathering the title is the prompt and the description is
    the vote target; once locked the title flips to the "on" line and the target line drops away — the
    way pod-table drops its "once N join" line once the table opens. Green, like the other pod cards."""
    if locked:
        embed = discord.Embed(color=discord.Color.green(), title=TEAM_VOTE_LOCKED_TITLE)
    else:
        embed = discord.Embed(
            color=discord.Color.green(),
            title=TEAM_VOTE_PROMPT.format(count=emojis.mana_number(TEAM_VOTE_POD_SIZE)),
            description=TEAM_VOTE_GATHERING.format(needed=needed),
        )
    if voter_names:
        embed.add_field(
            name=TEAM_VOTE_TALLY.format(count=len(voter_names)),
            value=", ".join(voter_names), inline=False,
        )
    return embed


class TeamVoteButton(ui.DynamicItem[ui.Button], template=rf"{VOTE_BUTTON_PREFIX}:(?P<event_id>.+)"):
    """The vote button on a Team-Draft offer card. One per pod (event id in the custom_id), so a single
    registration dispatches every offer and the button keeps working after a restart. A click toggles the
    clicker's vote; the manager owns the tally and the lock."""

    def __init__(self, event_id: str) -> None:
        super().__init__(ui.Button(
            style=discord.ButtonStyle.primary, label=TEAM_VOTE_BUTTON_LABEL, emoji=TEAM_VOTE_EMOJI,
            custom_id=f"{VOTE_BUTTON_PREFIX}:{event_id}",
        ))
        self.event_id = event_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: ui.Button, match: re.Match):
        return cls(match["event_id"])

    async def callback(self, interaction: discord.Interaction) -> None:
        manager = ACTIVE_POD_MANAGERS.get(self.event_id)
        if manager is None:
            await interaction.response.send_message(
                "This pod is no longer taking votes.", ephemeral=(interaction.guild is not None),
            )
            return
        await manager.toggle_team_vote(interaction)


def build_team_vote_view(event_id: str) -> ui.View:
    view = ui.View(timeout=None)
    view.add_item(TeamVoteButton(event_id))
    return view
