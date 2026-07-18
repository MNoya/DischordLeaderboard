from datetime import date, datetime, timezone

import pytest

from bot.models import PodDraftEvent
from bot.services.pod_launch import dedupe_pod_name_sync

BASE = "TLA Jul 17 Late Pod"


def _seed_pod(session, name):
    event = PodDraftEvent(
        event_date=date(2026, 7, 17), event_time=datetime(2026, 7, 17, tzinfo=timezone.utc),
        set_code="TLA", name=name, draftmancer_session=f"sess-{name}",
        discord_thread_id=f"thread-{name}", socket_status="pending", kind="tournament",
    )
    session.add(event)
    session.flush()


@pytest.mark.parametrize(
    "existing, live, expected",
    [
        ([], [], BASE),
        ([BASE], [], f"{BASE} #2"),
        ([BASE, f"{BASE} #2"], [], f"{BASE} #3"),
        ([BASE, f"{BASE} #2", f"{BASE} #3"], [], f"{BASE} #4"),
        ([], [BASE], f"{BASE} #2"),
        ([BASE], [f"{BASE} #2"], f"{BASE} #3"),
        (["TLA Jul 17 Early Pod"], [], BASE),
    ],
)
def test_dedupe_pod_name_numbers_persisted_and_live_collisions(session, existing, live, expected):
    for name in existing:
        _seed_pod(session, name)

    result = dedupe_pod_name_sync(BASE, live_names=live, session=session)

    assert result == expected


def test_dedupe_ignores_table_split_names_when_numbering(session):
    _seed_pod(session, BASE)
    _seed_pod(session, f"{BASE} #2")
    _seed_pod(session, f"{BASE} #2 - Table 2")

    result = dedupe_pod_name_sync(BASE, session=session)

    assert result == f"{BASE} #3"
