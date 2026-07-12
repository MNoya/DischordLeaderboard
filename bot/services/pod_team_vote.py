"""Team-Draft vote offer posted as its own embed card on a settled six-player pod: a prompt, a tally
button, and the current voters. It is a distinct thread message, not an edit to the lobby card, so it
reads as a call to action — styled like the /pod-table card. Presentation only — the tally, the lock
threshold, and the pairing-mode switch live in the lobby flow. Kept in one place so the `!test` preview
and the live message share it.
"""
from __future__ import annotations

import discord


TEAM_VOTE_PROMPT = "6️⃣ Players locked in! Make it a Team Draft?"
TEAM_VOTE_EMOJI = "🤝"


def team_vote_needed(player_count: int) -> int:
    """Votes to lock Team Draft: a majority of the pod."""
    return player_count // 2 + 1


def team_vote_button_label(votes: int, needed: int) -> str:
    return f"Team Draft ({votes}/{needed})"


def build_team_vote_offer_embed(voter_names: list[str]) -> discord.Embed:
    """The offer card: the prompt as the title, current voters as the body. Bare names — the 🤝 button's
    tally and the prompt above are context enough. Green, like the other pod-draft cards."""
    embed = discord.Embed(color=discord.Color.green(), title=TEAM_VOTE_PROMPT)
    if voter_names:
        embed.description = ", ".join(voter_names)
    return embed
