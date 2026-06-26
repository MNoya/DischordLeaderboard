from datetime import datetime, timezone

from sqlalchemy import select

from bot.models import Episode
from bot.services.media_sync import _Item, _insert_new


def _item(guid, title, published_at, *, kind="episode", category="Metagame"):
    return _Item(
        guid=guid,
        kind=kind,
        number=None,
        title=title,
        link="",
        summary="",
        image="",
        published_at=published_at,
        duration_seconds=1800,
        audio_url=None,
        youtube_id=None,
        category=category,
    )


def _row(guid, title, published_at, category):
    return Episode(
        guid=guid,
        kind="episode",
        title=title,
        link="",
        published_at=published_at,
        duration_seconds=10,
        category=category,
    )


def test_insert_new_adds_only_unseen_guids(session):
    now = datetime(2026, 6, 20, tzinfo=timezone.utc)
    session.add(_row("pod-1", "Already here", now, "Metagame"))
    session.commit()

    result = _insert_new(session, [_item("pod-1", "Already here", now), _item("pod-2", "Brand new drop", now)])

    assert set(session.execute(select(Episode.guid)).scalars()) == {"pod-1", "pod-2"}
    assert result.total == 1


def test_insert_new_leaves_existing_rows_untouched(session):
    now = datetime(2026, 6, 20, tzinfo=timezone.utc)
    session.add(_row("pod-1", "Original title", now, "Coaching"))
    session.commit()

    _insert_new(session, [_item("pod-1", "Title edited by full sync only", now, category="Metagame")])

    row = session.execute(select(Episode).where(Episode.guid == "pod-1")).scalar_one()
    assert row.title == "Original title"
    assert row.category == "Coaching"
