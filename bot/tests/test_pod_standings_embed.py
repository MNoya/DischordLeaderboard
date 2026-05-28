from bot.services.pod_swiss import Standing
from bot.services.pod_tournament import build_champion_embed


def _standing(rank: int, name: str, wins: int, losses: int) -> Standing:
    return Standing(
        rank=rank, player_id=f"p{rank}", player_name=name,
        wins=wins, losses=losses, omw_pct=0.5, gw_pct=0.5, ogw_pct=0.5,
    )


def _standings() -> list[Standing]:
    return [
        _standing(1, "Arcyl", 3, 0),
        _standing(2, "Elfandor", 2, 1),
        _standing(3, "Bramblewick", 2, 1),
    ]


def test_medals_hidden_while_matches_pending():
    embed = build_champion_embed(_standings(), pending_count=1, include_submit_cta=False)
    assert "Live Standings" in embed.description
    for medal in ("🥇", "🥈", "🥉"):
        assert medal not in embed.description


def test_medals_shown_once_standings_final():
    embed = build_champion_embed(_standings(), pending_count=0, include_submit_cta=False)
    assert "Final Standings" in embed.description
    assert "1. 🥇 Arcyl" in embed.description
    assert "2. 🥈 Elfandor" in embed.description
    assert "3. 🥉 Bramblewick" in embed.description
