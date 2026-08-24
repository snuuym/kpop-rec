"""Minimal Last.fm client.

Only the four endpoints this project uses, with one behaviour worth calling
out: rate limiting is reported to the caller as the sentinel ``RATE_LIMITED``
rather than raised or slept through. Every pipeline stage caches incrementally,
so the correct response to a 429 is to persist progress and exit — not to block
for an unknown period. A transport error returns ``None`` (retry next run,
don't cache); a "no such track" answer returns an empty result (safe to cache).
"""

from __future__ import annotations

import time
from typing import Any

import requests

from . import config

RATE_LIMITED = "__RATELIMIT__"
NOT_FOUND = "__NOTFOUND__"


class LastFM:
    def __init__(self, api_key: str, delay: float = config.LASTFM_DELAY):
        self.api_key = api_key
        self.delay = delay

    def _get(self, method: str, **params: Any) -> Any:
        """Return the decoded body, ``RATE_LIMITED``, or ``None`` on failure."""
        try:
            r = requests.get(
                config.LASTFM_BASE,
                timeout=12,
                params={
                    "method": method,
                    "api_key": self.api_key,
                    "format": "json",
                    "autocorrect": 1,
                    **params,
                },
            )
            if r.status_code == 429:
                return RATE_LIMITED
            return r.json()
        except Exception:
            return None

    def sleep(self) -> None:
        time.sleep(self.delay)

    # ── Endpoints ───────────────────────────────────────────────────────────

    def tag_top_tracks(self, tag: str, pages: int = 5, limit: int = 100) -> list[dict]:
        """All tracks Last.fm associates with a tag, paged."""
        tracks: list[dict] = []
        for page in range(1, pages + 1):
            data = self._get("tag.getTopTracks", tag=tag, limit=limit, page=page)
            if not isinstance(data, dict) or "error" in data:
                break
            page_tracks = _as_list(data.get("tracks", {}).get("track"))
            if not page_tracks:
                break
            tracks.extend(page_tracks)
            time.sleep(0.2)
        return tracks

    def track_top_tags(self, artist: str, title: str, min_count: int):
        """Return ``(all_tags, confident_tags)``, or a sentinel.

        ``all_tags`` is every tag with at least one vote; ``confident_tags`` is
        the subset with at least ``min_count`` votes, which is what feeds
        sub-genre classification.
        """
        data = self._get("track.getTopTags", artist=artist, track=title)
        if data is RATE_LIMITED:
            return RATE_LIMITED
        if data is None:
            return None
        if "error" in data:
            return NOT_FOUND

        all_tags, confident = [], []
        for t in _as_list(data.get("toptags", {}).get("tag")):
            name = str(t.get("name", "")).lower().strip()
            if not name:
                continue
            all_tags.append(name)
            if int(t.get("count") or 0) >= min_count:
                confident.append(name)
        return all_tags, confident

    def track_info(self, artist: str, title: str):
        """Popularity metadata: listeners, playcount, MusicBrainz id."""
        data = self._get("track.getInfo", artist=artist, track=title)
        if data is RATE_LIMITED:
            return RATE_LIMITED
        if data is None or "error" in data:
            return None
        t = data.get("track", {})
        return {
            "listeners": int(t.get("listeners") or 0),
            "playcount": int(t.get("playcount") or 0),
            "mbid": t.get("mbid") or None,
        }

    def similar_tracks(self, artist: str, title: str, limit: int = 100):
        """Last.fm's similar-track list — the basis of the pseudo ground truth.

        These similarities are themselves collaborative-filtering output, not
        user preferences. See ``reports/gt_diagnostics.md``.
        """
        data = self._get(
            "track.getSimilar", artist=artist, track=title, limit=limit
        )
        if data is RATE_LIMITED:
            return RATE_LIMITED
        if data is None:
            return None
        if "error" in data:
            return []
        return [
            {
                "artist": (t.get("artist") or {}).get("name", ""),
                "title": t.get("name", ""),
                "match": float(t.get("match") or 0),
            }
            for t in _as_list(data.get("similartracks", {}).get("track"))
        ]

    def similar_artists(self, artist: str, limit: int = 50) -> list[dict]:
        data = self._get("artist.getSimilar", artist=artist, limit=limit)
        if not isinstance(data, dict):
            return []
        return _as_list(data.get("similarartists", {}).get("artist"))


def _as_list(x: Any) -> list:
    """Last.fm returns a bare object instead of a 1-element list. Normalize."""
    if isinstance(x, dict):
        return [x]
    return x or []
