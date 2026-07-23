from datetime import date, datetime, timezone

from bot.models import Player, PodDraftEvent, PodDraftMatch, PodDraftParticipant
from bot.services import pod_tournament
from bot.services.pod_tournament import (
    CLEAR_SENTINEL,
    RESULT_KEEP,
    SKIPPED_SENTINEL,
    FixPairingView,
    _load_champions_sync,
    apply_pairing_swap,
)


def _session_factory(session):
    class _Ctx:
        def __enter__(self):
            return session

        def __exit__(self, *exc):
            return False

    return lambda: _Ctx()


def _event(session):
    event = PodDraftEvent(
        event_date=date(2026, 7, 14),
        event_time=datetime(2026, 7, 14, tzinfo=timezone.utc),
        set_code="MSH",
        name="Test Pod",
        draftmancer_session="sess",
        discord_thread_id="thread-1",
        socket_status="in_progress",
        pairing_mode="bracket",
    )
    session.add(event)
    session.flush()
    return event


def _match(session, event_id, a, b, *, winner=None, score=None, round_num=1):
    reported = datetime(2026, 7, 14, tzinfo=timezone.utc) if winner is not None else None
    match = PodDraftMatch(
        event_id=event_id, round=round_num, pairing_index=0,
        player_a_name=a, player_b_name=b, winner_name=winner, score=score, reported_at=reported,
    )
    session.add(match)
    session.flush()
    return match


def test_swap_updates_both_players_and_keeps_pending(session, monkeypatch):
    monkeypatch.setattr(pod_tournament, "SessionLocal", _session_factory(session))
    event = _event(session)
    match = _match(session, event.id, "Alice", "Bob")

    result = apply_pairing_swap(match.id, "Carol", "Dan")

    session.refresh(match)
    assert (match.player_a_name, match.player_b_name) == ("Carol", "Dan")
    assert result["cleared"] is False
    assert match.winner_name is None


def test_swap_clears_result_when_winner_leaves_match(session, monkeypatch):
    monkeypatch.setattr(pod_tournament, "SessionLocal", _session_factory(session))
    event = _event(session)
    match = _match(session, event.id, "Alice", "Bob", winner="Alice", score="2-0")

    result = apply_pairing_swap(match.id, "Carol", "Bob")

    session.refresh(match)
    assert result["cleared"] is True
    assert match.winner_name is None
    assert match.score is None
    assert match.reported_at is None


def test_swap_keeps_result_when_winner_still_in_match(session, monkeypatch):
    monkeypatch.setattr(pod_tournament, "SessionLocal", _session_factory(session))
    event = _event(session)
    match = _match(session, event.id, "Alice", "Bob", winner="Bob", score="2-1")

    result = apply_pairing_swap(match.id, "Carol", "Bob")

    session.refresh(match)
    assert result["cleared"] is False
    assert match.winner_name == "Bob"
    assert match.score == "2-1"


def test_swap_preserves_not_played_marker(session, monkeypatch):
    monkeypatch.setattr(pod_tournament, "SessionLocal", _session_factory(session))
    event = _event(session)
    match = _match(session, event.id, "Alice", "Bob", winner=SKIPPED_SENTINEL, score="0-0")

    result = apply_pairing_swap(match.id, "Carol", "Dan")

    session.refresh(match)
    assert result["cleared"] is False
    assert match.winner_name == SKIPPED_SENTINEL


def test_swap_missing_match_returns_none(session, monkeypatch):
    monkeypatch.setattr(pod_tournament, "SessionLocal", _session_factory(session))
    assert apply_pairing_swap("does-not-exist", "Carol", "Dan") is None


def _fix_view(*, selected_a="Alice", selected_b="Bob", winner=None, score=None):
    match = {"match_id": "m1", "a_name": selected_a, "b_name": selected_b,
             "a_display": selected_a, "b_display": selected_b, "winner_name": winner, "score": score}
    view = FixPairingView("evt", 1, None, [match], [(selected_a, selected_a), (selected_b, selected_b)])
    view.selected_match = match
    view.selected_a = selected_a
    view.selected_b = selected_b
    return view


def test_resolve_result_choice_maps_slot_and_score():
    view = _fix_view()

    view.selected_result = "a|2-0"
    assert view._resolve_result_choice() == ("Alice", "2-0")

    view.selected_result = "b|2-1"
    assert view._resolve_result_choice() == ("Bob", "2-1")


def test_resolve_result_choice_sentinels_and_keep():
    view = _fix_view()

    view.selected_result = "clear"
    assert view._resolve_result_choice() == (CLEAR_SENTINEL, "0-0")
    view.selected_result = "skip"
    assert view._resolve_result_choice() == (SKIPPED_SENTINEL, "0-0")
    view.selected_result = RESULT_KEEP
    assert view._resolve_result_choice() is None
    view.selected_result = None
    assert view._resolve_result_choice() is None


def test_current_result_token_reflects_recorded_winner():
    assert _fix_view(winner="Bob", score="2-1")._current_result_token() == "b|2-1"
    assert _fix_view(winner="Alice", score="2-0")._current_result_token() == "a|2-0"
    assert _fix_view(winner=SKIPPED_SENTINEL, score="0-0")._current_result_token() == "skip"
    assert _fix_view()._current_result_token() == RESULT_KEEP


def test_current_result_token_keep_when_winner_no_longer_in_slots():
    view = _fix_view(winner="Alice", score="2-0")
    view.selected_a = "Carol"

    assert view._current_result_token() == RESULT_KEEP


def _champion(session, event_id, *, seat_name, deck_colors, player=None):
    session.add(PodDraftParticipant(
        event_id=event_id, display_name=seat_name, draftmancer_name=seat_name,
        player_id=player.id if player else None, placement=1, deck_colors=deck_colors,
    ))
    session.flush()


def test_load_champions_prefers_linked_discord_name_over_seat_name(session, monkeypatch):
    monkeypatch.setattr(pod_tournament, "SessionLocal", _session_factory(session))
    event = _event(session)
    linked = Player(slug="aitch-1", discord_id="1", discord_username="aitch", display_name="Aitch", active=True)
    session.add(linked)
    session.flush()
    _champion(session, event.id, seat_name="Aitch#85794", deck_colors="WU", player=linked)
    _champion(session, event.id, seat_name="Unlinked#0001", deck_colors="BR", player=None)

    champions = _load_champions_sync(event.id)

    assert ("**Aitch**", "WU") in champions
    assert ("**Unlinked#0001**", "BR") in champions
