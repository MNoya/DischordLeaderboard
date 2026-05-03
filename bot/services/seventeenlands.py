"""Client and aggregation helpers for 17lands draft data.

Fetches use the data endpoint:
    GET https://www.17lands.com/user/data/{token}?start_date=YYYY-MM-DD
which returns ``{"drafts": [...]}``. The ``/user_history/{token}`` URL
mentioned in the spec is the human-facing page — not used here.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterable

import requests

from bot.scoring import supported_formats

logger = logging.getLogger(__name__)

# Derived from the scoring buckets so adding a bucket auto-expands what gets fetched
SUPPORTED_FORMATS: tuple[str, ...] = supported_formats()

DEFAULT_BASE_URL = "https://www.17lands.com"
_TOKEN_RE = re.compile(r"[a-f0-9]{32}")


def extract_token(value: str) -> str:
    """Accept either a raw 32-hex token or a 17lands URL containing one.

    Returns the lowercase token. Raises ValueError if no token can be parsed.
    """
    if not value or not isinstance(value, str):
        raise ValueError("token is empty")
    candidate = value.strip().lower()
    match = _TOKEN_RE.search(candidate)
    if not match:
        raise ValueError(f"could not extract a 17lands token from: {value!r}")
    return match.group(0)


class MinIntervalLimiter:
    """Block ``wait()`` until at least ``min_interval_s`` has passed since the prior call.

    Time and sleep are injected so tests can drive the limiter deterministically.
    """

    def __init__(
        self,
        min_interval_s: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.min_interval_s = min_interval_s
        self._sleep = sleep
        self._clock = clock
        self._last_at: float | None = None

    def wait(self) -> None:
        now = self._clock()
        if self._last_at is not None and self.min_interval_s > 0:
            remaining = self.min_interval_s - (now - self._last_at)
            if remaining > 0:
                self._sleep(remaining)
                now = self._clock()
        self._last_at = now


class SeventeenLandsClient:
    """Thin client over the 17lands data endpoint.

    Optional file cache: when ``cache_dir`` is set, ``fetch_drafts`` will read
    cached JSON from ``<cache_dir>/<token>__<start_date>.json`` if present, and
    write each fresh response there. Bypasses both rate limiter and HTTP on
    cache hit. Useful for dev iteration where the upstream data hasn't moved.
    """

    def __init__(
        self,
        limiter: MinIntervalLimiter | None = None,
        session: requests.Session | None = None,
        timeout_s: float = 30.0,
        base_url: str = DEFAULT_BASE_URL,
        cache_dir: Path | str | None = None,
    ) -> None:
        self.limiter = limiter or MinIntervalLimiter()
        self.session = session or requests.Session()
        self.timeout_s = timeout_s
        self.base_url = base_url.rstrip("/")
        self.cache_dir = Path(cache_dir) if cache_dir else None

    def _data_url(self, token: str) -> str:
        return f"{self.base_url}/user/data/{token}"

    def _cache_path(self, token: str, start_date: date | None) -> Path | None:
        if self.cache_dir is None:
            return None
        suffix = start_date.isoformat() if start_date else "all"
        return self.cache_dir / f"{token}__{suffix}.json"

    def fetch_drafts(self, token: str, start_date: date | None = None) -> list[dict]:
        """Return the list of draft events for a token.

        Raises ``requests.HTTPError`` on non-2xx and ``ValueError`` on a
        malformed response body.
        """
        cache_path = self._cache_path(token, start_date)
        if cache_path is not None and cache_path.exists():
            with cache_path.open("r", encoding="utf-8") as f:
                cached = json.load(f)
            return cached.get("drafts", []) or []

        params: dict[str, str] = {}
        if start_date is not None:
            params["start_date"] = start_date.isoformat()

        self.limiter.wait()
        resp = self.session.get(self._data_url(token), params=params, timeout=self.timeout_s)
        resp.raise_for_status()
        try:
            body = resp.json()
        except ValueError as e:
            raise ValueError(f"17lands response was not valid JSON: {e}") from e
        if not isinstance(body, dict) or "drafts" not in body:
            raise ValueError("17lands response missing 'drafts' key")

        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(body, f)

        return body["drafts"] or []

    def verify_token(self, token: str) -> bool:
        """Return True if 17lands recognizes the token.

        A new user with no events still returns ``{"drafts": []}`` — that
        counts as recognized. Any non-200, network failure, or malformed
        response means the token is treated as invalid.
        """
        self.limiter.wait()
        try:
            resp = self.session.get(self._data_url(token), timeout=self.timeout_s)
        except requests.RequestException:
            logger.warning("17lands verify failed with network error", exc_info=True)
            return False
        if resp.status_code != 200:
            return False
        try:
            body = resp.json()
        except ValueError:
            return False
        return isinstance(body, dict) and "drafts" in body


def aggregate_for_set(drafts: Iterable[dict], set_code: str) -> dict[str, dict]:
    """Aggregate raw drafts into per-format stats for a single set.

    Returns one bucket per ``SUPPORTED_FORMATS`` entry (always present, zeroed
    when no events match). Drafts in unsupported formats are skipped. The set
    match is substring-based so Alchemy variants (e.g. ``Y26ECL``) bucket
    under their parent set code (``ECL``) — mirrors legacy behavior.

    A trophy is any event with a truthy ``event_wins`` field, which 17lands
    sets when an event ended in a winning run (7-0 Premier, 4-0 Trad, etc.).
    """
    result: dict[str, dict] = {
        fmt: {"wins": 0, "losses": 0, "games_played": 0, "trophies": 0}
        for fmt in SUPPORTED_FORMATS
    }

    for d in drafts:
        fmt = d.get("format")
        if fmt not in result:
            continue
        expansion = d.get("expansion") or ""
        if set_code not in expansion:
            continue
        wins = int(d.get("wins") or 0)
        losses = int(d.get("losses") or 0)
        bucket = result[fmt]
        bucket["wins"] += wins
        bucket["losses"] += losses
        bucket["games_played"] += wins + losses
        if d.get("event_wins"):
            bucket["trophies"] += 1

    return result


def _parse_17lands_ts(value: str | None) -> datetime | None:
    """17lands serves timestamps as ``YYYY-MM-DD HH:MM[:SS]`` UTC strings (no tz)."""
    if not value or not isinstance(value, str):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def extract_events_for_set(drafts: Iterable[dict], set_code: str) -> list[dict]:
    """One dict per individual draft event matching ``set_code``.

    Same set-match rule as ``aggregate_for_set`` (substring of ``expansion``).
    Drafts in formats outside SUPPORTED_FORMATS are skipped — mirrors what
    aggregation considers "real" for this leaderboard.

    Output dicts use the same field names as ``DraftEvent`` columns so callers
    can construct rows with ``DraftEvent(**row)`` after attaching ``player_id``
    and ``set_id``.
    """
    out: list[dict] = []
    for d in drafts:
        fmt = d.get("format")
        if fmt not in SUPPORTED_FORMATS:
            continue
        expansion = d.get("expansion") or ""
        if set_code not in expansion:
            continue
        event_id = d.get("id")
        if not event_id:
            # 17lands has always provided id in observed responses; skip defensively
            continue
        out.append({
            "seventeenlands_event_id": event_id,
            "format": fmt,
            "expansion": expansion,
            "wins": int(d.get("wins") or 0),
            "losses": int(d.get("losses") or 0),
            "is_trophy": bool(d.get("event_wins")),
            "colors": d.get("colors") or None,
            "start_rank": d.get("start_rank") or None,
            "end_rank": d.get("end_rank") or None,
            "started_at": _parse_17lands_ts(d.get("first_event_server_time")),
            "finished_at": _parse_17lands_ts(d.get("last_event_server_time")),
        })
    return out
