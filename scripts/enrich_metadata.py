#!/usr/bin/env python3
"""Stage 3 — add popularity and release-year metadata.

Two fields, two sources:

  listeners / playcount   Last.fm ``track.getInfo``
  year                    MusicBrainz recording search

Neither is decoration. ``listeners`` is the popularity axis that the entire
analysis is stratified on — without it there is no way to show that tag
coverage collapses in the long tail. ``year`` exists to test the competing
explanation: maybe untagged tracks are simply *new* rather than *obscure*.
``analyze_tag_sparsity.py`` regresses tag count on both to separate them.

Usage
-----
    export LASTFM_API_KEY=xxx
    python3 scripts/enrich_metadata.py                 # both fields
    python3 scripts/enrich_metadata.py --skip-year     # popularity only (fast)

Rate limits
-----------
Last.fm tolerates ~5 req/s; MusicBrainz enforces a hard 1 req/s and bans on
sustained excess, so the year pass is ~4x slower per track. For ~1,300 tracks
budget roughly 6 minutes for popularity and 25 minutes for year.

Resumable: progress is cached in ``data/enrich_cache.json``.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kpoprec import config  # noqa: E402
from kpoprec.io import load_songs, read_json, write_json, write_json_with_backup  # noqa: E402
from kpoprec.lastfm import RATE_LIMITED, LastFM  # noqa: E402
from kpoprec.normalize import clean_for_search, song_key  # noqa: E402

# MusicBrainz scores each candidate 0-100; below this the match is unreliable.
MB_MIN_SCORE = 85
# Guard against obviously wrong parses (a "year" of 3 or 9999).
MB_YEAR_RANGE = (1980, 2027)


def fetch_year(artist: str, title: str):
    """First known release year for a recording, or ``None``.

    Takes the minimum across all matching releases: a track's first release is
    what "how new is this" should mean, not the latest compilation it appeared
    on.
    """
    query = f'recording:"{clean_for_search(title)}" AND artist:"{clean_for_search(artist)}"'
    try:
        r = requests.get(
            config.MUSICBRAINZ_BASE,
            timeout=15,
            headers={"User-Agent": config.USER_AGENT},
            params={"query": query, "fmt": "json", "limit": 5},
        )
        if r.status_code == 503:
            return RATE_LIMITED

        years: list[str] = []
        for rec in r.json().get("recordings", []):
            if rec.get("score", 0) < MB_MIN_SCORE:
                continue
            if rec.get("first-release-date"):
                years.append(rec["first-release-date"][:4])
            for rel in rec.get("releases", []):
                if rel.get("date"):
                    years.append(rel["date"][:4])

        lo, hi = MB_YEAR_RANGE
        parsed = [int(y) for y in years if y.isdigit() and lo <= int(y) <= hi]
        return min(parsed) if parsed else None
    except Exception:
        return None


def enrich_popularity(client: LastFM, songs: list[dict], cache: dict, cache_path: Path) -> None:
    todo = [s for s in songs if song_key(s) not in cache["lastfm"]]
    print(f"[popularity] {len(todo)} to process, {len(songs) - len(todo)} cached")

    for i, s in enumerate(todo, 1):
        res = client.track_info(s["artist"], s["title"])
        if res is RATE_LIMITED:
            write_json(cache_path, cache)
            print("  ! Last.fm rate limit — progress saved, re-run later")
            break
        cache["lastfm"][song_key(s)] = res or {}
        if i % 100 == 0:
            write_json(cache_path, cache)
            print(f"  [{i}/{len(todo)}]")
        client.sleep()

    write_json(cache_path, cache)


def enrich_year(songs: list[dict], cache: dict, cache_path: Path) -> None:
    todo = [s for s in songs if song_key(s) not in cache["year"]]
    mins = len(todo) * config.MUSICBRAINZ_DELAY / 60
    print(f"\n[year] {len(todo)} to process (~{mins:.0f} min at MusicBrainz's 1 req/s)")

    for i, s in enumerate(todo, 1):
        y = fetch_year(s["artist"], s["title"])
        if y is RATE_LIMITED:
            write_json(cache_path, cache)
            print("  ! MusicBrainz rate limit — progress saved, re-run later")
            break
        cache["year"][song_key(s)] = y
        if i % 50 == 0:
            write_json(cache_path, cache)
            resolved = sum(1 for v in cache["year"].values() if v)
            print(f"  [{i}/{len(todo)}] resolved {resolved}")
        time.sleep(config.MUSICBRAINZ_DELAY)

    write_json(cache_path, cache)


def main() -> None:
    ap = argparse.ArgumentParser(description="Add popularity and year metadata")
    ap.add_argument("--songs", type=Path, default=config.SONGS_JSON)
    ap.add_argument("--cache", type=Path, default=config.ENRICH_CACHE)
    ap.add_argument("--skip-year", action="store_true", help="popularity only (fast)")
    ap.add_argument("--limit", type=int, default=0, help="only the first N tracks (debug)")
    args = ap.parse_args()

    songs = load_songs(args.songs)
    if args.limit:
        songs = songs[: args.limit]

    client = LastFM(config.lastfm_key())
    cache = read_json(args.cache, default=None) or {"lastfm": {}, "year": {}}
    cache.setdefault("lastfm", {})
    cache.setdefault("year", {})

    enrich_popularity(client, songs, cache, args.cache)
    if not args.skip_year:
        enrich_year(songs, cache, args.cache)

    # ── Merge into the full library ─────────────────────────────────────────
    all_songs = load_songs(args.songs)
    n_pop = n_year = 0
    for s in all_songs:
        k = song_key(s)
        info = cache["lastfm"].get(k) or {}
        if info.get("listeners"):
            s["listeners"] = info["listeners"]
            s["playcount"] = info.get("playcount", 0)
            if info.get("mbid"):
                s.setdefault("mbid", info["mbid"])
            n_pop += 1
        year = cache["year"].get(k)
        if year:
            s["year"] = year
            n_year += 1

    write_json_with_backup(args.songs, all_songs)

    n = len(all_songs)
    print(f"\n[done] listeners: {n_pop}/{n} ({n_pop / n * 100:.1f}%)")
    print(f"[done] year:      {n_year}/{n} ({n_year / n * 100:.1f}%)")
    print(f"[done] backup -> {args.songs}.bak")
    print("\nNext: python3 scripts/analyze_tag_sparsity.py")


if __name__ == "__main__":
    main()
