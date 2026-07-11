import discord

from bot.services import pod_team
from bot.services.pod_drafts import normalize_player_name
from bot.services.pod_swiss import Standing
from bot.services.pod_team_flow import TEAM_VICTORY_COLORS
from bot.services.pod_team_showcase import build_team_championship_view, decided_trophy_standings
from bot.services.pod_tournament import ParticipantDeckData


GREEN = ["Ava", "Cara", "Eli"]
BLUE = ["Bram", "Dex", "Fern"]
TEAMS = {**{n: pod_team.TEAM_A for n in GREEN}, **{n: pod_team.TEAM_B for n in BLUE}}
DISPLAYS = {normalize_player_name(n): {"display_name": n} for n in GREEN + BLUE}


def _standing(rank, name, wins, losses):
    return Standing(rank=rank, player_id=name, player_name=name, wins=wins, losses=losses,
                    omw_pct=0.0, gw_pct=0.0, ogw_pct=0.0)


def _standings(green_records, blue_records):
    rows = list(zip(GREEN, green_records)) + list(zip(BLUE, blue_records))
    rows.sort(key=lambda r: -r[1][0])
    return [_standing(i + 1, name, w, losses) for i, (name, (w, losses)) in enumerate(rows)]


def _rounds(pending_pairs=()):
    matches = [
        {"a_name": a, "b_name": b, "winner_name": None if (a, b) in pending_pairs else a}
        for a in GREEN for b in BLUE
    ]
    return [(1, matches)]


def test_trophy_set_undecided_while_an_undefeated_player_has_a_pending_match():
    standings = _standings([(2, 0), (2, 1), (1, 2)], [(1, 2), (1, 2), (1, 1)])

    result = decided_trophy_standings(standings, _rounds(pending_pairs=(("Ava", "Fern"),)))

    assert result is None


def test_trophy_set_collects_every_locked_3_0_across_both_teams():
    standings = _standings([(3, 0), (2, 1), (1, 2)], [(3, 0), (0, 3), (0, 3)])

    result = decided_trophy_standings(standings, _rounds())

    assert {s.player_name for s in result} == {"Ava", "Bram"}


def test_trophy_set_empty_when_everyone_has_a_loss():
    standings = _standings([(2, 1), (2, 1), (2, 1)], [(1, 2), (1, 2), (1, 2)])

    result = decided_trophy_standings(standings, _rounds())

    assert result == []


def test_undefeated_short_of_three_wins_neither_earns_nor_blocks():
    standings = _standings([(2, 0), (2, 1), (2, 1)], [(1, 2), (1, 2), (0, 2)])

    result = decided_trophy_standings(standings, _rounds())

    assert result == []


def _deck_data(names_with_shots, caption=None):
    return {
        normalize_player_name(n): ParticipantDeckData(
            colors="WU", screenshot_url=url, screenshot_caption=caption,
        )
        for n, url in names_with_shots
    }


def _container_parts(view):
    (container, _) = view.children
    galleries = [c for c in container.children if isinstance(c, discord.ui.MediaGallery)]
    texts = [c.content for c in container.children if isinstance(c, discord.ui.TextDisplay)]
    thumbnail_sections = [
        c for c in container.children
        if isinstance(c, discord.ui.Section) and isinstance(c.accessory, discord.ui.Thumbnail)
    ]
    return container, galleries, texts, thumbnail_sections


def test_championship_view_shows_only_the_winning_teams_gallery():
    standings = _standings([(3, 0), (2, 1), (2, 1)], [(1, 2), (1, 2), (0, 3)])
    deck_data = _deck_data([(n, f"https://cdn.example/{n}.png") for n in GREEN + BLUE])

    view = build_team_championship_view(
        standings, TEAMS, event_name="MSH Pod Draft #4 - July 1", displays=DISPLAYS,
        player_colors={}, deck_data=deck_data,
    )

    container, galleries, texts, thumbnail_sections = _container_parts(view)
    assert container.accent_colour == TEAM_VICTORY_COLORS[pod_team.TEAM_A]
    assert len(galleries) == 1 and len(galleries[0].items) == 3
    assert {m.media.url for m in galleries[0].items} == {f"https://cdn.example/{n}.png" for n in GREEN}
    assert any("Fern" in t for t in texts)
    assert thumbnail_sections == []


def test_championship_view_rows_carry_captions_for_both_teams():
    standings = _standings([(3, 0), (2, 1), (2, 1)], [(1, 2), (1, 2), (0, 3)])
    deck_data = _deck_data(
        [(n, f"https://cdn.example/{n}.png") for n in GREEN + BLUE], caption="pure value",
    )

    view = build_team_championship_view(
        standings, TEAMS, event_name="Pod", displays=DISPLAYS,
        player_colors={}, deck_data=deck_data,
    )

    _, _, texts, _ = _container_parts(view)
    green_block = next(t for t in texts if "Ava" in t)
    blue_block = next(t for t in texts if "Fern" in t)
    assert "pure value" in green_block
    assert "pure value" in blue_block


def test_championship_view_losing_3_0_gets_a_row_thumbnail():
    standings = _standings([(3, 0), (2, 1), (1, 2)], [(3, 0), (0, 3), (0, 3)])
    deck_data = _deck_data([(n, f"https://cdn.example/{n}.png") for n in GREEN + BLUE])

    view = build_team_championship_view(
        standings, TEAMS, event_name="Pod", displays=DISPLAYS,
        player_colors={}, deck_data=deck_data,
    )

    container, galleries, texts, thumbnail_sections = _container_parts(view)
    assert len(galleries) == 1
    assert len(thumbnail_sections) == 1
    (section,) = thumbnail_sections
    block = section.children[0].content
    assert "Bram" in block and "Dex" in block and "Fern" in block
    assert section.accessory.media.url == "https://cdn.example/Bram.png"


def test_championship_view_draw_shows_no_gallery():
    standings = _standings([(2, 1), (2, 1), (2, 1)], [(2, 1), (2, 1), (2, 1)])
    deck_data = _deck_data([(n, f"https://cdn.example/{n}.png") for n in GREEN + BLUE])

    view = build_team_championship_view(
        standings, TEAMS, event_name="Pod", displays=DISPLAYS,
        player_colors={}, deck_data=deck_data,
    )

    container, galleries, _, thumbnail_sections = _container_parts(view)
    assert container.accent_colour == discord.Color.green()
    assert galleries == []
    assert thumbnail_sections == []
