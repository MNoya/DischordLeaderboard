from datetime import date, datetime, timezone

from bot.models import PodDraftEvent, PodDraftMatch
from bot.services import pod_tournament
from bot.services.pod_tournament import SKIPPED_SENTINEL, apply_pairing_swap


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
