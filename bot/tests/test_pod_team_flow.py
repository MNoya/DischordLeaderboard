from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from bot.models import PodDraftEvent, PodDraftParticipant
from bot.services import pod_team
from bot.services.pod_drafts import apply_seat_indexes, normalize_player_name, seed_event_participants
from bot.services.pod_swiss import Standing
from bot.services.pod_tournament import format_deck_color_emojis
from bot.services.pod_team_flow import (
    TEAM_VICTORY_COLORS,
    _apply_teams,
    build_team_final_embed,
    team_final_standings,
    team_scores,
)


def _standing(rank, name, wins, losses):
    return Standing(rank=rank, player_id=name, player_name=name, wins=wins, losses=losses,
                    omw_pct=0.0, gw_pct=0.0, ogw_pct=0.0)


GREEN = ["Ava", "Cara", "Eli"]
BLUE = ["Bram", "Dex", "Fern"]
TEAMS = {**{n: pod_team.TEAM_A for n in GREEN}, **{n: pod_team.TEAM_B for n in BLUE}}
DISPLAYS = {normalize_player_name(n): {"display_name": n} for n in GREEN + BLUE}


def _standings(green_records, blue_records):
    rows = list(zip(GREEN, green_records)) + list(zip(BLUE, blue_records))
    rows.sort(key=lambda r: -r[1][0])
    return [_standing(i + 1, name, w, losses) for i, (name, (w, losses)) in enumerate(rows)]


def test_team_scores_sum_each_sides_match_wins():
    standings = _standings([(3, 0), (2, 1), (2, 1)], [(1, 2), (1, 2), (0, 3)])

    assert team_scores(standings, TEAMS) == (7, 2)


def test_team_final_standings_carry_records_but_no_placement():
    standings = _standings([(3, 0), (2, 1), (2, 1)], [(1, 2), (1, 2), (0, 3)])

    rows = team_final_standings(standings)

    assert [r.record for r in rows] == ["3-0", "2-1", "2-1", "1-2", "1-2", "0-3"]
    assert all(r.placement is None for r in rows)
    assert all(r.eliminated_round is None for r in rows)


def test_final_embed_declares_the_winning_team_with_score():
    standings = _standings([(3, 0), (2, 1), (2, 1)], [(1, 2), (1, 2), (0, 3)])

    embed = build_team_final_embed(
        standings, TEAMS, event_name="Pod", displays=DISPLAYS, pending_count=0,
    )

    assert pod_team.team_label(pod_team.TEAM_A) in embed.title
    assert "7" in embed.description and "2" in embed.description
    assert len(embed.fields) == 2
    assert embed.colour == TEAM_VICTORY_COLORS[pod_team.TEAM_A]


def test_final_embed_draw_names_no_winner():
    standings = _standings([(2, 1), (2, 1), (2, 1)], [(2, 1), (2, 1), (2, 1)])

    embed = build_team_final_embed(
        standings, TEAMS, event_name="Pod", displays=DISPLAYS, pending_count=0,
    )

    assert pod_team.team_label(pod_team.TEAM_A) not in embed.title
    assert pod_team.team_label(pod_team.TEAM_B) not in embed.title
    assert "🏆" not in embed.title


def test_final_embed_live_variant_shows_running_score_without_winner():
    standings = _standings([(1, 0), (1, 0), (0, 0)], [(0, 1), (0, 1), (0, 0)])

    embed = build_team_final_embed(
        standings, TEAMS, event_name="Pod", displays=DISPLAYS, pending_count=5,
    )

    assert "🏆" not in embed.title
    assert "2" in embed.description and "0" in embed.description


def test_final_embed_fields_carry_each_players_record():
    standings = _standings([(3, 0), (2, 1), (2, 1)], [(1, 2), (1, 2), (0, 3)])

    embed = build_team_final_embed(
        standings, TEAMS, event_name="Pod", displays=DISPLAYS, pending_count=0,
    )

    green_field = next(f for f in embed.fields if "Ava" in f.value)
    assert "3-0" in green_field.value
    blue_field = next(f for f in embed.fields if "Fern" in f.value)
    assert "0-3" in blue_field.value
    assert embed.footer.text == "Pod"


def test_final_embed_marks_personal_trophies_on_3_0_rows_only():
    standings = _standings([(3, 0), (2, 1), (2, 1)], [(1, 2), (1, 2), (0, 3)])

    embed = build_team_final_embed(
        standings, TEAMS, event_name="Pod", displays=DISPLAYS, pending_count=0,
    )

    green_field = next(f for f in embed.fields if "Ava" in f.value)
    trophy_lines = [line for line in green_field.value.splitlines() if "🏆" in line]
    assert len(trophy_lines) == 1 and "Ava" in trophy_lines[0]
    blue_field = next(f for f in embed.fields if "Fern" in f.value)
    assert "🏆" not in blue_field.value


def test_final_embed_deck_colors_render_per_player():
    standings = _standings([(3, 0), (2, 1), (2, 1)], [(1, 2), (1, 2), (0, 3)])
    player_colors = {normalize_player_name("Ava"): "WU"}
    glyph = format_deck_color_emojis("WU")

    embed = build_team_final_embed(
        standings, TEAMS, event_name="Pod", displays=DISPLAYS, pending_count=0,
        player_colors=player_colors,
    )

    green_field = next(f for f in embed.fields if "Ava" in f.value)
    ava_line = next(line for line in green_field.value.splitlines() if "Ava" in line)
    cara_line = next(line for line in green_field.value.splitlines() if "Cara" in line)
    assert glyph and glyph in ava_line
    assert glyph not in cara_line


def test_start_assignment_persists_seat_parity_teams(session):
    event_id = str(uuid4())
    now = datetime.now(timezone.utc)
    session.add(PodDraftEvent(
        id=event_id, event_date=now.date(), event_time=now, set_code="SOS",
        name="Team Test Pod", draftmancer_session="TEAM-TEST", discord_thread_id="1",
        sesh_message_id="team-test", socket_status="test", pairing_mode="team",
    ))
    session.flush()
    order = ["Ava#11111", "Bram#22222", "Cara#33333", "Dex#44444"]
    seed_event_participants(session, event_id, order)

    apply_seat_indexes(session, event_id, order)
    _apply_teams(session, event_id, pod_team.assign_teams(order))
    session.commit()

    rows = session.execute(
        select(PodDraftParticipant.draftmancer_name, PodDraftParticipant.seat_index, PodDraftParticipant.team)
        .where(PodDraftParticipant.event_id == event_id)
        .order_by(PodDraftParticipant.seat_index)
    ).all()
    assert [(seat, team) for _, seat, team in rows] == [
        (0, pod_team.TEAM_A), (1, pod_team.TEAM_B), (2, pod_team.TEAM_A), (3, pod_team.TEAM_B),
    ]
    assert [name for name, _, _ in rows] == order
