"""Read-only YouTube Data API client for the channel's uploads and curated playlists.

The channel's playlists are the human-maintained taxonomy: per-set playlists give an
episode its format, "… Set Review" / "Draft …" / "Evergreen" playlists give its category.
``fetch_videos`` returns every upload plus any video Alex featured in a curated playlist
(including the occasional guest/other-channel video), each annotated with the playlists it
belongs to, so the media sync can derive both without guessing from clickbait titles.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import requests

log = logging.getLogger(__name__)

YOUTUBE_API = "https://www.googleapis.com/youtube/v3"
_SKIP_TITLES = {"Private video", "Deleted video"}


@dataclass
class YouTubeVideo:
    id: str
    title: str
    published_at: str
    description: str
    thumbnail: str
    duration_seconds: int
    playlists: list[str] = field(default_factory=list)


class YouTubeClient:
    def __init__(self, api_key: str, channel_handle: str, session: requests.Session | None = None, timeout_s: int = 20):
        self.api_key = api_key
        self.channel_handle = channel_handle
        self.session = session or requests.Session()
        self.timeout_s = timeout_s

    def fetch_videos(self) -> list[YouTubeVideo]:
        channel_id, uploads_playlist = self._resolve_channel()
        upload_ids = self._playlist_video_ids(uploads_playlist)

        membership: dict[str, set[str]] = {}
        for playlist_id, title in self._channel_playlists(channel_id):
            for video_id in self._playlist_video_ids(playlist_id):
                membership.setdefault(video_id, set()).add(title)

        all_ids = list(dict.fromkeys([*upload_ids, *membership]))
        details = self._video_details(all_ids)

        videos: list[YouTubeVideo] = []
        for video_id in all_ids:
            detail = details.get(video_id)
            if detail is None:
                continue
            videos.append(
                YouTubeVideo(
                    id=video_id,
                    title=detail["title"],
                    published_at=detail["published_at"],
                    description=detail["description"],
                    thumbnail=detail["thumbnail"],
                    duration_seconds=detail["duration_seconds"],
                    playlists=sorted(membership.get(video_id, set())),
                )
            )
        return videos

    def _get(self, path: str, params: dict) -> dict:
        params = {**params, "key": self.api_key}
        resp = self.session.get(f"{YOUTUBE_API}/{path}", params=params, timeout=self.timeout_s)
        resp.raise_for_status()
        return resp.json()

    def _resolve_channel(self) -> tuple[str, str]:
        body = self._get("channels", {"part": "contentDetails", "forHandle": self.channel_handle})
        items = body.get("items") or []
        if not items:
            raise RuntimeError(f"YouTube channel not found for handle {self.channel_handle}")
        channel = items[0]
        uploads = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        if not uploads:
            raise RuntimeError("Could not resolve uploads playlist")
        return channel["id"], uploads

    def _channel_playlists(self, channel_id: str) -> list[tuple[str, str]]:
        playlists: list[tuple[str, str]] = []
        page = ""
        while True:
            params = {"part": "snippet", "channelId": channel_id, "maxResults": 50}
            if page:
                params["pageToken"] = page
            body = self._get("playlists", params)
            for item in body.get("items", []):
                playlists.append((item["id"], item.get("snippet", {}).get("title", "")))
            page = body.get("nextPageToken", "")
            if not page:
                return playlists

    def _playlist_video_ids(self, playlist_id: str) -> list[str]:
        ids: list[str] = []
        page = ""
        while True:
            params = {"part": "snippet", "playlistId": playlist_id, "maxResults": 50}
            if page:
                params["pageToken"] = page
            body = self._get("playlistItems", params)
            for entry in body.get("items", []):
                video_id = entry.get("snippet", {}).get("resourceId", {}).get("videoId")
                if video_id:
                    ids.append(video_id)
            page = body.get("nextPageToken", "")
            if not page:
                return ids

    # videos.list carries the authoritative publish date (playlistItems reports the date a video
    # was *added* to a playlist, which is wrong for featured back-catalogue videos), plus the
    # duration, in one call.
    def _video_details(self, video_ids: list[str]) -> dict[str, dict]:
        details: dict[str, dict] = {}
        for start in range(0, len(video_ids), 50):
            chunk = video_ids[start : start + 50]
            body = self._get("videos", {"part": "snippet,contentDetails", "id": ",".join(chunk)})
            for item in body.get("items", []):
                snippet = item.get("snippet", {})
                title = snippet.get("title", "")
                if title in _SKIP_TITLES:
                    continue
                thumbs = snippet.get("thumbnails", {})
                best = thumbs.get("maxres") or thumbs.get("standard") or thumbs.get("high") or thumbs.get("default")
                details[item["id"]] = {
                    "title": title,
                    "published_at": snippet.get("publishedAt", ""),
                    "description": snippet.get("description", ""),
                    "thumbnail": (best or {}).get("url", ""),
                    "duration_seconds": _parse_iso_duration(item.get("contentDetails", {}).get("duration", "")),
                }
        return details


def _parse_iso_duration(iso: str) -> int:
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not match:
        return 0
    hours, minutes, seconds = match.groups()
    return int(hours or 0) * 3600 + int(minutes or 0) * 60 + int(seconds or 0)
