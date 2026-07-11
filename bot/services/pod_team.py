"""Team-draft pairer for pod drafts. Pure functions only; the manager handles side effects.

A team draft splits an even roster into two teams by draft-seat parity — Draftmancer's team-draft mode
seats the teams alternating (seat 0, 2, 4… vs 1, 3, 5…), so the seat index a player drafted from *is*
their team. Each round pairs every Team A player against a Team B player, rotating the opponent so over
three rounds each player faces three distinct opponents. The team with more match wins takes the draft.

Individual match records still fall out of these matches unchanged, so per-player scoring and the Swiss
standings code apply as-is; this module only decides who plays whom and which team a win belongs to.
"""
from __future__ import annotations

from dataclasses import dataclass


TEAM_A = "A"
TEAM_B = "B"

TEAM_EMOJI = {TEAM_A: "🟩", TEAM_B: "🟦"}  # single home so future custom team logos swap in one place


def team_label(team: str) -> str:
    """Human label for a team key. Green/Blue match the report-button colours (green win, blurple win).
    Kept in one place so the naming can change without a migration."""
    return "Green Team" if team == TEAM_A else "Blue Team"


def team_emoji(team: str) -> str:
    return TEAM_EMOJI[TEAM_A if team == TEAM_A else TEAM_B]


@dataclass(frozen=True)
class TeamMember:
    name: str          # stable per-tournament identifier (draftmancer_name)
    team: str          # TEAM_A or TEAM_B
    order: int         # position within the team, ascending; drives the pairing rotation


def assign_teams(names_in_seat_order: list[str]) -> dict[str, str]:
    """Map name → team by seat parity: even seats are Team A, odd seats Team B.

    `names_in_seat_order` is the roster ordered by draft seat (seat 0 first). Falls back to the given
    order when seats are unknown, which still yields two balanced alternating teams.
    """
    return {name: (TEAM_A if i % 2 == 0 else TEAM_B) for i, name in enumerate(names_in_seat_order)}


def team_rosters(names_in_seat_order: list[str], teams: dict[str, str]) -> tuple[list[str], list[str]]:
    """Return (team_a_names, team_b_names) preserving seat order within each team."""
    team_a = [name for name in names_in_seat_order if teams.get(name) == TEAM_A]
    team_b = [name for name in names_in_seat_order if teams.get(name) == TEAM_B]
    return team_a, team_b


def pair_round(team_a: list[str], team_b: list[str], round_num: int) -> list[tuple[str, str]]:
    """Cross-team pairings for round_num as (team_a_player, team_b_player).

    Rotates each Team A player's opponent by round so nobody replays an opponent across the three
    rounds. Team A is always the left side of the pairing, so a match's winning team is read from which
    column the winner sits in. Raises ValueError when the teams are unequal or empty.
    """
    if not team_a or not team_b:
        raise ValueError("team draft needs a non-empty roster on both teams")
    if len(team_a) != len(team_b):
        raise ValueError(f"unequal teams: {len(team_a)} vs {len(team_b)}")
    size = len(team_a)
    pairings: list[tuple[str, str]] = []
    for i, a in enumerate(team_a):
        b = team_b[(i + round_num - 1) % size]
        pairings.append((a, b))
    return pairings


def team_match_wins(
    matches: list[tuple[str, str]], teams: dict[str, str],
) -> tuple[int, int]:
    """Count reported match wins per team. `matches` is (winner_name, _score); the loser is implicit.

    Returns (team_a_wins, team_b_wins). Wins by a player of unknown team are ignored.
    """
    a_wins = 0
    b_wins = 0
    for winner_name, _ in matches:
        side = teams.get(winner_name)
        if side == TEAM_A:
            a_wins += 1
        elif side == TEAM_B:
            b_wins += 1
    return a_wins, b_wins


def team_winner(a_wins: int, b_wins: int) -> str | None:
    """TEAM_A / TEAM_B for the side with more match wins; None on a tie."""
    if a_wins > b_wins:
        return TEAM_A
    if b_wins > a_wins:
        return TEAM_B
    return None
