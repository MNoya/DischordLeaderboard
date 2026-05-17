from datetime import date, datetime, timezone

from sqlalchemy import select

from bot.config import settings
from bot.models import MagicSet, Player, PodDraftEvent, PodDraftParticipant
from bot.services.pod_drafts import (
    FinalStanding,
    ParsedSeshEvent,
    finalize_champion,
    get_participant_deck_state,
    list_champions,
    participant_dm_info,
    player_pod_stats,
    record_event,
    record_match,
    set_participant_deck_colors,
    set_participant_review_choice,
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
        format_label=None,
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


def test_record_event_with_no_matching_set_leaves_set_id_null(session):
    event = record_event(session, _parsed_event(set_code="CUBE"))
    assert event.set_id is None
    assert event.set_code == "CUBE"


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
        FinalStanding(draftmancer_name="Alice", placement=1, record="3-0", eliminated_round=None, draft_log_url="u1"),
        FinalStanding(draftmancer_name="Bob",   placement=2, record="2-1", eliminated_round=3,    draft_log_url="u2"),
        FinalStanding(draftmancer_name="Carl",  placement=3, record="1-2", eliminated_round=3,    draft_log_url="u3"),
    ]
    updated = finalize_champion(session, event.id, standings)

    assert updated.socket_status == "complete"
    rows = session.execute(
        select(PodDraftParticipant).where(PodDraftParticipant.event_id == event.id)
    ).scalars().all()
    by_name = {p.display_name: p for p in rows}
    assert by_name["Alice"].placement == 1
    assert by_name["Alice"].draft_log_url == "u1"
    assert by_name["Alice"].eliminated_round is None
    assert by_name["Bob"].placement == 2
    assert by_name["Bob"].eliminated_round == 3


def test_list_champions_returns_filtered_and_ordered_by_date(session):
    _seed_set(session, "SOS")
    _seed_set(session, "ECL")
    for set_code, ed in [("SOS", date(2026, 5, 6)), ("SOS", date(2026, 5, 13)), ("ECL", date(2026, 4, 1))]:
        event = record_event(session, _parsed_event(set_code=set_code, event_date=ed, attendees=()))
        standing = FinalStanding(
            draftmancer_name=f"Champ-{set_code}-{ed.isoformat()}", placement=1, record="3-0",
            eliminated_round=None, draft_log_url=None,
        )
        finalize_champion(session, event.id, [standing])

    all_rows = list_champions(session)
    assert [r["event_date"] for r in all_rows] == [date(2026, 4, 1), date(2026, 5, 6), date(2026, 5, 13)]

    sos_only = list_champions(session, set_code="sos")
    assert {r["set_code"] for r in sos_only} == {"SOS"}
    assert len(sos_only) == 2


def test_player_pod_stats_aggregates_correctly(session):
    _seed_set(session, "SOS")
    _seed_set(session, "ECL")
    player = _seed_player(session, discord_id="777", username="champ", display_name="Champ")

    e1 = record_event(session, _parsed_event(set_code="SOS", event_date=date(2026, 5, 6), attendees=("Champ",)))
    finalize_champion(session, e1.id, [
        FinalStanding("Champ", placement=1, record="3-0", eliminated_round=None, draft_log_url=None),
    ])
    e2 = record_event(session, _parsed_event(set_code="ECL", event_date=date(2026, 4, 1), attendees=("Champ",)))
    finalize_champion(session, e2.id, [
        FinalStanding("Champ", placement=2, record="2-1", eliminated_round=3, draft_log_url=None),
    ])

    stats = player_pod_stats(session, "777")
    assert stats is not None
    assert stats["lifetime_trophies"] == 1
    assert stats["trophies_by_set"] == {"SOS": 1}
    assert stats["events_played"] == 2
    assert stats["wins"] == 5
    assert stats["losses"] == 1


def test_player_pod_stats_returns_none_for_unknown_discord_id(session):
    assert player_pod_stats(session, "ghost") is None


def _seed_pod_for_deck_color_tests(session, thread_id: str = "thread-42") -> tuple[str, str]:
    _seed_set(session, "SOS")
    player = _seed_player(session, discord_id="42", username="alice", display_name="Alice")
    parsed = ParsedSeshEvent(
        event_date=date(2026, 5, 13),
        event_time=datetime(2026, 5, 13, 0, 0, tzinfo=timezone.utc),
        set_code="SOS", event_number=None, format_label=None,
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
    # Set arena_name on the linked player so we cover the populated branch
    player = session.execute(select(Player).where(Player.discord_id == "42")).scalar_one()
    player.arena_name = "Alice#1234"
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
