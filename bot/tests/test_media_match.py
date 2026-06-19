from datetime import datetime, timezone

from bot.services.media_sync import _Item, _find_match
from bot.services.youtube import YouTubeVideo


def _podcast(title, published_at, duration_seconds):
    return _Item(
        guid="pod",
        kind="episode",
        number=None,
        title=title,
        link="",
        summary="",
        image="",
        published_at=published_at,
        duration_seconds=duration_seconds,
        audio_url=None,
        youtube_id=None,
    )


def _video(title, published_at, duration_seconds):
    return YouTubeVideo(
        id="vid",
        title=title,
        published_at=published_at.isoformat(),
        description="",
        thumbnail="",
        duration_seconds=duration_seconds,
    )


def test_same_date_merge_when_titles_diverge_but_durations_align():
    podcast = _podcast("The Live Listener Q + A Session!", datetime(2023, 5, 27, 0, 36, tzinfo=timezone.utc), 4698)
    video = _video("Listener Q + A! | Limited Level-Ups", datetime(2023, 5, 27, 0, 54, tzinfo=timezone.utc), 4659)

    match = _find_match(podcast, [video], set())

    assert match is video


def test_same_date_video_with_unrelated_duration_is_not_absorbed():
    same_day = datetime(2022, 9, 16, tzinfo=timezone.utc)
    podcast = _podcast("Drafting Red/Green Beatdown with a Guest", same_day.replace(hour=1), 3364)
    draft_vod = _video("The Grindiest Of Grinds! | Twitch Replay", same_day.replace(hour=18), 6139)

    match = _find_match(podcast, [draft_vod], set())

    assert match is None


def test_different_date_is_not_matched_on_duration_alone():
    podcast = _podcast("A Format State of the Format Address", datetime(2023, 5, 27, tzinfo=timezone.utc), 4698)
    video = _video("An Unrelated Draft Guide", datetime(2023, 6, 3, tzinfo=timezone.utc), 4659)

    match = _find_match(podcast, [video], set())

    assert match is None
