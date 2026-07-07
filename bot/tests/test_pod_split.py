from datetime import date, datetime, timezone

from bot.models import MagicSet, PodDraftEvent
from bot.services.pod_drafts import (
    next_table_index,
    record_split_event,
    split_base_name,
)


def _seed_source(session, *, name="MSH Pod Draft #8", set_code="MSH", pairing="swiss", seating="leaderboard"):
    magic_set = MagicSet(code=set_code, name=f"{set_code} long name", start_date=date(2026, 6, 23))
    session.add(magic_set)
    session.flush()
    source = PodDraftEvent(
        event_date=date(2026, 7, 8),
        event_time=datetime(2026, 7, 8, 23, 0, tzinfo=timezone.utc),
        set_id=magic_set.id,
        set_code=set_code,
        format_label="MSH Draft",
        name=name,
        draftmancer_session="LLU-MSH-D8",
        discord_thread_id="thread-1",
        socket_status="reminded",
        kind="tournament",
        pairing_mode=pairing,
        seating_mode=seating,
    )
    session.add(source)
    session.flush()
    return source


def test_split_base_name_strips_trailing_table():
    assert split_base_name("MSH Pod Draft #8 Table 2") == "MSH Pod Draft #8"
    assert split_base_name("MSH Pod Draft #8") == "MSH Pod Draft #8"
    assert split_base_name("SOS Pod Draft #6 - Jun 3") == "SOS Pod Draft #6 - Jun 3"


def test_next_table_index_starts_at_two(session):
    _seed_source(session)

    assert next_table_index(session, "MSH Pod Draft #8") == 2


def test_record_split_event_clones_source_into_table_two(session):
    source = _seed_source(session, pairing="swiss", seating="leaderboard")

    table_two = record_split_event(session, source_event_id=source.id)

    assert table_two.name == "MSH Pod Draft #8 Table 2"
    assert table_two.kind == "tournament"
    assert table_two.sesh_message_id is None
    assert table_two.set_code == source.set_code
    assert table_two.set_id == source.set_id
    assert table_two.format_label == source.format_label
    assert table_two.event_date == source.event_date
    assert table_two.pairing_mode == "swiss"
    assert table_two.seating_mode == "leaderboard"
    assert table_two.draftmancer_session == "LLU-MSH-D8-T2"


def test_second_split_advances_to_table_three(session):
    source = _seed_source(session)
    source.discord_thread_id = "thread-1"

    record_split_event(session, source_event_id=source.id)
    table_three = record_split_event(session, source_event_id=source.id)

    assert table_three.name == "MSH Pod Draft #8 Table 3"
    assert table_three.draftmancer_session == "LLU-MSH-D8-T3"


def test_split_from_a_table_bases_on_the_original_pod(session):
    source = _seed_source(session)
    table_two = record_split_event(session, source_event_id=source.id)

    table_three = record_split_event(session, source_event_id=table_two.id)

    assert table_three.name == "MSH Pod Draft #8 Table 3"
