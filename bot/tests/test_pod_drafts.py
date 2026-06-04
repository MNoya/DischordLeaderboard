from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from bot.config import settings
from bot.models import MagicSet, Player, PodDraftEvent, PodDraftParticipant
from bot.services.pod_drafts import (
    FinalStanding,
    ParsedSeshEvent,
    active_event_for_discord_user_in_dm,
    capture_deck_screenshot,
    finalize_champion,
    get_participant_deck_state,
    list_champions,
    participant_dm_info,
    pod_summary_by_set_for_player,
    record_event,
    record_match,
    set_participant_deck_colors,
    set_participant_review_choice,
    update_event_time_if_changed,
    upsert_participant,
)


def _seed_set(session, code="SOS"):
    s = MagicSet(code=code, name=f"{code} long name", start_date=date(2026, 4, 1))
    session.add(s)
    session.flush()
    return s


def _seed_player(session, discord_id="111", username="alice", display_name="Alice"):
    p = Player(
        slug=f"{username}-{discord_id}",
        discord_id=discord_id,
        discord_username=username,
        display_name=display_name,
        seventeenlands_token="t" * 32,
        active=True,
    )
    session.add(p)
    session.flush()
    return p


def _parsed_event(set_code="SOS", event_date=date(2026, 5, 13), attendees=("Alice", "Bob", "Carl"), event_number=None):
    return ParsedSeshEvent(
        event_date=event_date,
        event_time=datetime(event_date.year, event_date.month, event_date.day, 0, 0, tzinfo=timezone.utc),
        set_code=set_code,
        event_number=event_number,
        name=f"{set_code} Pod Draft — {event_date:%b %d}",
        attendees=list(attendees),
        sesh_message_id=f"msg-{event_date.isoformat()}-{event_number}",
        discord_thread_id=f"thread-{event_date.isoformat()}-{event_number}",
    )


def test_record_event_persists_and_links_known_attendees(session, monkeypatch):
    monkeypatch.setattr(settings, "pod_draft_session_prefix", "LLU")
    _seed_set(session, "SOS")
    _seed_player(session, discord_id="111", username="alice", display_name="Alice")

    event = record_event(session, _parsed_event(attendees=("Alice", "Stranger")))

    assert event.socket_status == "pending"
    assert event.draftmancer_session == "LLU-SOS-May-13"
    assert event.draftmancer_url == "https://draftmancer.com/?session=LLU-SOS-May-13"
    assert event.set_id is not None

    participants = session.execute(
        select(PodDraftParticipant).where(PodDraftParticipant.event_id == event.id)
    ).scalars().all()
    by_name = {p.display_name: p for p in participants}
    assert by_name["Alice"].player_id is not None
    assert by_name["Stranger"].player_id is None


def test_record_event_same_day_collision_appends_letter_suffix(session, monkeypatch):
    monkeypatch.setattr(settings, "pod_draft_session_prefix", "LLU")
    _seed_set(session)
    e1 = record_event(session, _parsed_event(attendees=()))
    e2 = record_event(session, _parsed_event(attendees=()))
    e3 = record_event(session, _parsed_event(attendees=()))
    assert e1.draftmancer_session == "LLU-SOS-May-13"
    assert e2.draftmancer_session == "LLU-SOS-May-13-A"
    assert e3.draftmancer_session == "LLU-SOS-May-13-B"


def test_record_event_with_event_number_uses_n_in_session(session, monkeypatch):
    monkeypatch.setattr(settings, "pod_draft_session_prefix", "LLU")
    _seed_set(session)
    e1 = record_event(session, _parsed_event(attendees=(), event_number=10))
    e2 = record_event(session, _parsed_event(attendees=(), event_number=10))
    assert e1.draftmancer_session == "LLU-SOS-10"
    assert e2.draftmancer_session == "LLU-SOS-10-A"


def test_record_event_custom_format_uses_slug_and_drops_prefix(session, monkeypatch):
    monkeypatch.setattr(settings, "pod_draft_session_prefix", "LLU")
    event = record_event(session, _parsed_event(set_code="PEASANT", attendees=(), event_number=4))
    assert event.draftmancer_session == "Peasant-26-D4"
    assert event.draftmancer_url == "https://draftmancer.com/?session=Peasant-26-D4"
    assert event.format_label == "Peasant Cube"


def test_record_event_custom_format_falls_back_to_month_day(session, monkeypatch):
    monkeypatch.setattr(settings, "pod_draft_session_prefix", "LLU")
    event = record_event(session, _parsed_event(set_code="PEASANT", attendees=()))
    assert event.draftmancer_session == "Peasant-26-May-13"


def test_record_event_custom_format_collision_appends_letter_suffix(session, monkeypatch):
    monkeypatch.setattr(settings, "pod_draft_session_prefix", "LLU")
    e1 = record_event(session, _parsed_event(set_code="PEASANT", attendees=(), event_number=4))
    e2 = record_event(session, _parsed_event(set_code="PEASANT", attendees=(), event_number=4))
    assert e1.draftmancer_session == "Peasant-26-D4"
    assert e2.draftmancer_session == "Peasant-26-D4-A"


def test_record_event_with_no_matching_set_leaves_set_id_null(session):
    event = record_event(session, _parsed_event(set_code="CUBE"))
    assert event.set_id is None
    assert event.set_code == "CUBE"


def test_update_event_time_if_changed_no_match_returns_none(session):
    result = update_event_time_if_changed(
        session,
        sesh_message_id="nope",
        new_event_time=datetime(2026, 5, 14, 0, 0, tzinfo=timezone.utc),
        new_event_date=date(2026, 5, 14),
    )
    assert result is None


def test_update_event_time_if_changed_skips_completed_event(session):
    _seed_set(session)
    event = record_event(session, _parsed_event(attendees=()))
    event.socket_status = "complete"
    session.flush()

    result = update_event_time_if_changed(
        session,
        sesh_message_id=event.sesh_message_id,
        new_event_time=datetime(2026, 5, 14, 0, 0, tzinfo=timezone.utc),
        new_event_date=date(2026, 5, 14),
    )
    assert result is None


def test_update_event_time_if_changed_no_op_when_time_matches(session):
    _seed_set(session)
    event = record_event(session, _parsed_event(attendees=()))

    returned, needs_reschedule, was_active = update_event_time_if_changed(
        session,
        sesh_message_id=event.sesh_message_id,
        new_event_time=event.event_time,
        new_event_date=event.event_date,
    )
    assert returned.id == event.id
    assert needs_reschedule is False
    assert was_active is False


def test_update_event_time_if_changed_writes_new_time(session):
    _seed_set(session)
    event = record_event(session, _parsed_event(attendees=()))
    new_time = datetime(2026, 5, 14, 18, 30, tzinfo=timezone.utc)

    returned, needs_reschedule, was_active = update_event_time_if_changed(
        session,
        sesh_message_id=event.sesh_message_id,
        new_event_time=new_time,
        new_event_date=date(2026, 5, 14),
    )
    assert needs_reschedule is True
    assert was_active is False
    assert returned.event_time == new_time
    assert returned.event_date == date(2026, 5, 14)

    reread = session.execute(
        select(PodDraftEvent).where(PodDraftEvent.id == event.id)
    ).scalar_one()
    assert reread.event_time == new_time
    assert reread.event_date == date(2026, 5, 14)


def test_update_event_time_if_changed_no_op_when_active_and_time_matches(session):
    _seed_set(session)
    event = record_event(session, _parsed_event(attendees=()))
    event.socket_status = "connected"
    session.flush()

    returned, needs_reschedule, was_active = update_event_time_if_changed(
        session,
        sesh_message_id=event.sesh_message_id,
        new_event_time=event.event_time,
        new_event_date=event.event_date,
    )
    assert returned.id == event.id
    assert needs_reschedule is False
    assert was_active is True
    assert returned.socket_status == "connected"


def test_update_event_time_if_changed_resets_status_when_active(session):
    _seed_set(session)
    event = record_event(session, _parsed_event(attendees=()))
    event.socket_status = "connected"
    session.flush()
    new_time = datetime(2026, 5, 14, 18, 30, tzinfo=timezone.utc)

    returned, needs_reschedule, was_active = update_event_time_if_changed(
        session,
        sesh_message_id=event.sesh_message_id,
        new_event_time=new_time,
        new_event_date=date(2026, 5, 14),
    )
    assert needs_reschedule is True
    assert was_active is True
    assert returned.socket_status == "pending"
    assert returned.event_time == new_time


def test_upsert_participant_matches_existing_by_display_name(session):
    _seed_set(session)
    event = record_event(session, _parsed_event(attendees=("Alice",)))

    p = upsert_participant(session, event.id, display_name="alice", draftmancer_name="Alice#1234")

    rows = session.execute(
        select(PodDraftParticipant).where(PodDraftParticipant.event_id == event.id)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].id == p.id
    assert rows[0].draftmancer_name == "Alice#1234"


def test_upsert_participant_matches_existing_by_draftmancer_name(session):
    _seed_set(session)
    event = record_event(session, _parsed_event(attendees=("Alice",)))
    upsert_participant(session, event.id, display_name="Alice", draftmancer_name="A#1")

    again = upsert_participant(session, event.id, display_name="Different", draftmancer_name="a#1")

    rows = session.execute(
        select(PodDraftParticipant).where(PodDraftParticipant.event_id == event.id)
    ).scalars().all()
    assert len(rows) == 1
    assert again.id == rows[0].id


def test_upsert_participant_creates_new_row_when_no_match(session):
    _seed_set(session)
    event = record_event(session, _parsed_event(attendees=("Alice",)))
    upsert_participant(session, event.id, display_name="Brand New", draftmancer_name="New#9999")

    rows = session.execute(
        select(PodDraftParticipant).where(PodDraftParticipant.event_id == event.id)
    ).scalars().all()
    assert len(rows) == 2


def test_upsert_participant_backfills_player_id(session):
    _seed_set(session)
    event = record_event(session, _parsed_event(attendees=("Stranger",)))
    _seed_player(session, discord_id="222", username="stranger", display_name="Stranger")

    upsert_participant(session, event.id, display_name="Stranger")

    row = session.execute(
        select(PodDraftParticipant).where(PodDraftParticipant.event_id == event.id)
    ).scalar_one()
    assert row.player_id is not None


def test_record_match_is_idempotent(session):
    _seed_set(session)
    event = record_event(session, _parsed_event())

    first = record_match(session, event.id, 1, "Alice", "Bob", winner_name="Alice", score="2-1")
    again = record_match(session, event.id, 1, "Alice", "Bob", winner_name="Alice", score="2-0")

    assert first.id == again.id
    assert again.score == "2-0"


def test_finalize_champion_writes_standings_and_marks_complete(session):
    _seed_set(session)
    event = record_event(session, _parsed_event(attendees=("Alice", "Bob", "Carl")))

    standings = [
        FinalStanding(draftmancer_name="Alice", placement=1, record="3-0", eliminated_round=None),
        FinalStanding(draftmancer_name="Bob",   placement=2, record="2-1", eliminated_round=3),
        FinalStanding(draftmancer_name="Carl",  placement=3, record="1-2", eliminated_round=3),
    ]
    updated = finalize_champion(session, event.id, standings)

    assert updated.socket_status == "complete"
    rows = session.execute(
        select(PodDraftParticipant).where(PodDraftParticipant.event_id == event.id)
    ).scalars().all()
    by_name = {p.display_name: p for p in rows}
    assert by_name["Alice"].placement == 1
    assert by_name["Alice"].record == "3-0"
    assert by_name["Alice"].eliminated_round is None
    assert by_name["Bob"].placement == 2
    assert by_name["Bob"].eliminated_round == 3


def test_finalize_champion_stamps_finalized_at_and_preserves_it_on_rerun(session):
    _seed_set(session)
    event = record_event(session, _parsed_event(attendees=("Alice", "Bob")))
    standings = [
        FinalStanding(draftmancer_name="Alice", placement=1, record="3-0", eliminated_round=None),
        FinalStanding(draftmancer_name="Bob",   placement=2, record="2-1", eliminated_round=3),
    ]
    first = finalize_champion(session, event.id, standings)
    assert first.finalized_at is not None
    stamped = first.finalized_at

    again = finalize_champion(session, event.id, standings)
    assert again.finalized_at == stamped


def _seed_linked_event(session, *, discord_id, thread_id, event_time, name="Pod Draft"):
    parsed = ParsedSeshEvent(
        event_date=event_time.date(),
        event_time=event_time,
        set_code="SOS", event_number=None,
        name=name,
        attendees=["Alice"],
        sesh_message_id=f"msg-{thread_id}",
        discord_thread_id=thread_id,
    )
    return record_event(session, parsed)


def test_active_event_resolver_returns_finalized_pod(session):
    """Regression: a player submitting deck colors after finalization must still resolve to the pod."""
    _seed_set(session)
    _seed_player(session, discord_id="42", username="alice", display_name="Alice")
    now = datetime.now(timezone.utc)
    event = _seed_linked_event(session, discord_id="42", thread_id="thread-fin", event_time=now)
    finalize_champion(session, event.id, [
        FinalStanding(draftmancer_name="Alice", placement=1, record="3-0", eliminated_round=None),
    ])
    assert event.socket_status == "complete"

    resolved = active_event_for_discord_user_in_dm(session, "42")
    assert resolved == (event.id, "thread-fin")


def test_active_event_resolver_excludes_pods_outside_window(session):
    _seed_set(session)
    _seed_player(session, discord_id="42", username="alice", display_name="Alice")
    old = datetime.now(timezone.utc) - timedelta(hours=25)
    _seed_linked_event(session, discord_id="42", thread_id="thread-old", event_time=old)

    assert active_event_for_discord_user_in_dm(session, "42") is None


def test_active_event_resolver_returns_newest_within_window(session):
    _seed_set(session)
    _seed_player(session, discord_id="42", username="alice", display_name="Alice")
    now = datetime.now(timezone.utc)
    _seed_linked_event(session, discord_id="42", thread_id="thread-older", event_time=now - timedelta(hours=6))
    newer = _seed_linked_event(session, discord_id="42", thread_id="thread-newer", event_time=now - timedelta(hours=1))

    resolved = active_event_for_discord_user_in_dm(session, "42")
    assert resolved == (newer.id, "thread-newer")


def test_list_champions_returns_filtered_and_ordered_by_date(session):
    _seed_set(session, "SOS")
    _seed_set(session, "ECL")
    for set_code, ed in [("SOS", date(2026, 5, 6)), ("SOS", date(2026, 5, 13)), ("ECL", date(2026, 4, 1))]:
        event = record_event(session, _parsed_event(set_code=set_code, event_date=ed, attendees=()))
        standing = FinalStanding(
            draftmancer_name=f"Champ-{set_code}-{ed.isoformat()}", placement=1, record="3-0",
            eliminated_round=None,
        )
        finalize_champion(session, event.id, [standing])

    all_rows = list_champions(session)
    assert [r["event_date"] for r in all_rows] == [date(2026, 4, 1), date(2026, 5, 6), date(2026, 5, 13)]

    sos_only = list_champions(session, set_code="sos")
    assert {r["set_code"] for r in sos_only} == {"SOS"}
    assert len(sos_only) == 2


def test_pod_summary_by_set_aggregates_per_set(session):
    _seed_set(session, "SOS")
    _seed_set(session, "ECL")
    player = _seed_player(session, discord_id="777", username="champ", display_name="Champ")

    e1 = record_event(session, _parsed_event(set_code="SOS", event_date=date(2026, 5, 6), attendees=("Champ",)))
    finalize_champion(session, e1.id, [
        FinalStanding("Champ", placement=1, record="3-0", eliminated_round=None),
    ])
    e2 = record_event(session, _parsed_event(set_code="ECL", event_date=date(2026, 4, 1), attendees=("Champ",)))
    finalize_champion(session, e2.id, [
        FinalStanding("Champ", placement=2, record="2-1", eliminated_round=3),
    ])

    summary = pod_summary_by_set_for_player(session, player.id)
    assert summary["SOS"] == (1, 3, 0, 1, 0)   # events, wins, losses, trophies, wins_2_1
    assert summary["ECL"] == (1, 2, 1, 0, 1)


def test_pod_summary_trophy_from_pod_win_without_3_0(session):
    _seed_set(session, "SOS")
    player = _seed_player(session, discord_id="778", username="smallpod", display_name="SmallPod")

    event = record_event(session, _parsed_event(set_code="SOS", event_date=date(2026, 5, 6), attendees=("SmallPod",)))
    finalize_champion(session, event.id, [
        FinalStanding("SmallPod", placement=1, record="2-1", eliminated_round=None),
    ])

    summary = pod_summary_by_set_for_player(session, player.id)
    assert summary["SOS"].trophies == 1   # 2-1 that won the pod counts as a trophy
    assert summary["SOS"].wins_2_1 == 0   # not also a 2-1 finish


def test_pod_summary_empty_for_unknown_player(session):
    assert pod_summary_by_set_for_player(session, "ghost") == {}


def test_stats_embed_pod_line_scoped_to_requested_set(session):
    from bot.services.player_stats import process_stats, render_embed

    _seed_set(session, "SOS")
    _seed_set(session, "ECL")
    _seed_player(session, discord_id="777", username="champ", display_name="Champ")
    e = record_event(session, _parsed_event(set_code="SOS", event_date=date(2026, 5, 6), attendees=("Champ",)))
    finalize_champion(session, e.id, [FinalStanding("Champ", placement=1, record="3-0", eliminated_round=None)])
    session.commit()

    sos = render_embed(process_stats(session, player_name=None, viewer_discord_id="777", set_code="SOS"))
    assert "**Pod**" in (sos.description or "")

    ecl = render_embed(process_stats(session, player_name=None, viewer_discord_id="777", set_code="ECL"))
    assert "Pod" not in (ecl.description or "")


def _seed_pod_for_deck_color_tests(session, thread_id: str = "thread-42") -> tuple[str, str]:
    _seed_set(session, "SOS")
    player = _seed_player(session, discord_id="42", username="alice", display_name="Alice")
    parsed = ParsedSeshEvent(
        event_date=date(2026, 5, 13),
        event_time=datetime(2026, 5, 13, 0, 0, tzinfo=timezone.utc),
        set_code="SOS", event_number=None,
        name="Pod Draft #1",
        attendees=["Alice", "Bob"],
        sesh_message_id="msg-deck-color",
        discord_thread_id=thread_id,
    )
    event = record_event(session, parsed)
    return event.id, player.discord_id


def test_set_participant_deck_colors_saves(session):
    _seed_pod_for_deck_color_tests(session)
    ok = set_participant_deck_colors(session, "thread-42", "42", "WU")
    assert ok is True
    in_pod, color, _ = get_participant_deck_state(session, "thread-42", "42")
    assert in_pod is True
    assert color == "WU"


def test_set_participant_deck_colors_rejects_non_participant(session):
    _seed_pod_for_deck_color_tests(session)
    # discord_id "99" is not on the participant list
    assert set_participant_deck_colors(session, "thread-42", "99", "WB") is False


def test_get_participant_deck_state_signals_not_in_pod(session):
    _seed_pod_for_deck_color_tests(session)
    in_pod, color, wants_review = get_participant_deck_state(session, "thread-42", "99")
    assert in_pod is False
    assert color is None
    assert wants_review is None


def test_participant_dm_info_returns_linked_player_data(session):
    event_id, _ = _seed_pod_for_deck_color_tests(session)
    # Simulate Alice joining Draftmancer under a specific handle (the session-specific name)
    participant = session.execute(
        select(PodDraftParticipant)
        .where(PodDraftParticipant.event_id == event_id, PodDraftParticipant.display_name == "Alice")
    ).scalar_one()
    participant.draftmancer_name = "Alice#1234"
    # Also set a different Player.arena_name to confirm the DM info uses the Draftmancer handle,
    # not the player's primary alias
    player = session.execute(select(Player).where(Player.discord_id == "42")).scalar_one()
    player.arena_name = "AliceMain#9999"
    session.flush()

    info = participant_dm_info(session, event_id)
    assert "alice" in info
    alice = info["alice"]
    assert alice.discord_id == "42"
    assert alice.display_name == "Alice"
    assert alice.arena_name == "Alice#1234"


def test_set_participant_deck_colors_overwrites_on_resubmit(session):
    _seed_pod_for_deck_color_tests(session)
    set_participant_deck_colors(session, "thread-42", "42", "WU")
    set_participant_deck_colors(session, "thread-42", "42", "URg")
    _, color, _ = get_participant_deck_state(session, "thread-42", "42")
    assert color == "URg"


def test_get_participant_deck_state_defaults_review_to_none(session):
    _seed_pod_for_deck_color_tests(session)
    in_pod, _, wants_review = get_participant_deck_state(session, "thread-42", "42")
    assert in_pod is True
    assert wants_review is None


def test_set_participant_review_choice_saves(session):
    _seed_pod_for_deck_color_tests(session)
    assert set_participant_review_choice(session, "thread-42", "42", True) is True
    _, _, wants_review = get_participant_deck_state(session, "thread-42", "42")
    assert wants_review is True


def test_set_participant_review_choice_toggles(session):
    _seed_pod_for_deck_color_tests(session)
    set_participant_review_choice(session, "thread-42", "42", True)
    set_participant_review_choice(session, "thread-42", "42", False)
    _, _, wants_review = get_participant_deck_state(session, "thread-42", "42")
    assert wants_review is False


def test_set_participant_review_choice_independent_of_colors(session):
    _seed_pod_for_deck_color_tests(session)
    set_participant_deck_colors(session, "thread-42", "42", "WU")
    set_participant_review_choice(session, "thread-42", "42", True)
    _, color, wants_review = get_participant_deck_state(session, "thread-42", "42")
    assert color == "WU"
    assert wants_review is True


def test_set_participant_review_choice_rejects_non_participant(session):
    _seed_pod_for_deck_color_tests(session)
    assert set_participant_review_choice(session, "thread-42", "99", True) is False


def test_apply_mainboards_writes_when_decklist_present_and_skips_others(session):
    from bot.services.pod_draft_manager import _apply_mainboards

    _seed_set(session)
    event = record_event(session, _parsed_event(attendees=("Alice", "Bob", "Carl", "Dee")))
    upsert_participant(session, event.id, display_name="Alice", draftmancer_name="Alice#1")
    upsert_participant(session, event.id, display_name="Bob",   draftmancer_name="Bob#2")
    upsert_participant(session, event.id, display_name="Carl",  draftmancer_name="Carl#3")
    upsert_participant(session, event.id, display_name="Dee",   draftmancer_name=None)
    session.flush()

    log_payload = {
        "users": {
            "u1": {"userName": "Alice#1", "decklist": {"main": ["c-a1", "c-a2", "c-a3"]}},
            "u2": {"userName": "Bob#2"},
            "u3": {"userName": "Carl#3", "decklist": {"main": ["c-c1"]}, "isBot": True},
            "u4": {"userName": "Dee",    "decklist": {"main": ["c-d1", "c-d2"]}},
            "u5": {"userName": "DisChordBot", "decklist": {"main": ["junk"]}},
            "u6": {"userName": "Bot #1",      "decklist": {"main": ["junk"]}},
        },
    }
    _apply_mainboards(session, event.id, log_payload)
    session.flush()

    by_name = {
        r.display_name: r
        for r in session.execute(
            select(PodDraftParticipant).where(PodDraftParticipant.event_id == event.id)
        ).scalars().all()
    }
    assert by_name["Alice"].mainboard_card_ids == ["c-a1", "c-a2", "c-a3"]
    assert by_name["Bob"].mainboard_card_ids is None
    assert by_name["Carl"].mainboard_card_ids is None
    assert by_name["Dee"].mainboard_card_ids == ["c-d1", "c-d2"]


@pytest.mark.parametrize(
    "current_round, championship_posted, existing_url, existing_caption, new_caption, captured",
    [
        (None, False, None, None, None, False),
        (3, False, None, None, None, True),
        (3, False, "https://cdn.test/old.png", None, None, True),
        (3, False, "https://cdn.test/old.png", "3-0 trophy", None, False),
        (3, False, "https://cdn.test/old.png", "3-0 trophy", "went 2-1 actually", True),
        (3, True, "https://cdn.test/old.png", None, None, False),
        (3, True, "https://cdn.test/old.png", None, "3-0", True),
        (3, True, None, None, None, True),
    ],
    ids=[
        "too-early", "first-capture", "last-wins", "record-locks-slot", "record-replaces-record",
        "post-championship-ignored", "post-championship-record-overrides", "post-championship-fills-missing",
    ],
)
def test_capture_deck_screenshot_gating(
    session, current_round, championship_posted, existing_url, existing_caption, new_caption, captured,
):
    player = _seed_player(session, discord_id="901", username="cap", display_name="Cap")
    event = PodDraftEvent(
        event_date=date(2026, 6, 3), event_time=datetime(2026, 6, 3, tzinfo=timezone.utc),
        set_code="SOS", name="SOS Pod Capture", draftmancer_session="cap-sess",
        draftmancer_url="https://draftmancer.com/?session=cap-sess",
        discord_thread_id="cap-thread", sesh_message_id="cap-msg", socket_status="complete",
        current_round=current_round,
        championship_posted_at=datetime(2026, 6, 3, 23, tzinfo=timezone.utc) if championship_posted else None,
    )
    session.add(event)
    session.flush()
    session.add(PodDraftParticipant(
        event_id=event.id, player_id=player.id, display_name="Cap",
        deck_screenshot_url=existing_url, deck_screenshot_caption=existing_caption,
    ))
    session.flush()

    result = capture_deck_screenshot(session, "cap-thread", "901", "https://cdn.test/new.png", new_caption)

    stored = session.execute(
        select(PodDraftParticipant).where(PodDraftParticipant.event_id == event.id)
    ).scalar_one()
    if captured:
        assert result == event.id
        assert stored.deck_screenshot_url == "https://cdn.test/new.png"
        assert stored.deck_screenshot_caption == new_caption
    else:
        assert result is None
        assert stored.deck_screenshot_url == existing_url
