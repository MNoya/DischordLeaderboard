"""Shared constructors for the pod-draft engine tests (pod_swiss / pod_bracket)."""
from bot.services.pod_swiss import MatchOutcome, Player


def players(n: int) -> list[Player]:
    return [Player(id=f"p{i}", name=f"p{i}") for i in range(n)]


def match(round_num: int, a: str, b: str, winner: str, score: str = "2-0") -> MatchOutcome:
    return MatchOutcome(round_num=round_num, player_a_id=a, player_b_id=b, winner_id=winner, score=score)


def pairset(pairs) -> set[frozenset[str]]:
    return {frozenset(p) for p in pairs}
