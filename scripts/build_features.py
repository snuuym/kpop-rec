#!/usr/bin/env python3
"""Stage 4 — attach acoustic audio features to each track.

This is the signal that does not depend on anyone having tagged the track, and
therefore the one that reaches the long tail. Spotify deprecated its
``audio-features`` endpoint on 2024-11-27, so features come from ReccoBeats,
which is free and keyed by Spotify track ID.

Pipeline (offline, resumable):

  1. Spotify Search   (title, artist)          -> Spotify track ID
  2. ReccoBeats map   Spotify ID   (40/req)    -> ReccoBeats UUID
  3. ReccoBeats feats ReccoBeats UUID (40/req) -> audio features

Step 1 needs a Spotify token via the Client Credentials flow, so the client
secret is read from the environment. It is never written to disk or committed.
Steps 2-3 need no credentials, so a run without a secret still makes progress
against whatever IDs are already cached.

Usage
-----
    export SPOTIFY_CLIENT_ID=...
    export SPOTIFY_CLIENT_SECRET=...
    python3 scripts/build_features.py

Resumable: intermediate lookups are cached in ``data/features_cache.json``.
"""

from __future__ import annotations

import argparse
import base64
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kpoprec import config  # noqa: E402
from kpoprec.io import load_songs, read_json, write_json  # noqa: E402

RATE_LIMITED = "__RATELIMIT__"
TOKEN_EXPIRED = "__EXPIRED__"

# Spotify's Retry-After can be hours long when it throttles hard. Rather than
# block, stop step 1 and let the operator resume later.
MAX_RETRY_AFTER = 120

# Spotify-compatible feature names, as served by ReccoBeats.
FEATURE_KEYS = [
    "danceability", "energy", "valence", "tempo", "acousticness",
    "instrumentalness", "loudness", "speechiness", "liveness",
]

BATCH = 40


def spotify_token(client_id: str, client_secret: str) -> str:
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    r = requests.post(
        config.SPOTIFY_TOKEN_URL,
        headers={"Authorization": f"Basic {auth}"},
        data={"grant_type": "client_credentials"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def spotify_search_id(token: str, title: str, artist: str):
    """Best-match Spotify track ID, ``None``, or a sentinel."""
    q = f"track:{title} artist:{artist}"
    for _ in range(4):
        r = requests.get(
            config.SPOTIFY_SEARCH_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={"q": q, "type": "track", "limit": 1},
            timeout=15,
        )
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", "2"))
            if wait > MAX_RETRY_AFTER:
                return RATE_LIMITED
            time.sleep(wait + 1)
            continue
        if r.status_code == 401:
            return TOKEN_EXPIRED
        if r.status_code != 200:
            return None
        items = r.json().get("tracks", {}).get("items", [])
        return items[0]["id"] if items else None
    return None


def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def recco_map_ids(spotify_ids: list[str]) -> dict[str, str]:
    """Spotify track IDs -> ReccoBeats UUIDs."""
    out: dict[str, str] = {}
    for batch in chunked(spotify_ids, BATCH):
        try:
            r = requests.get(
                f"{config.RECCOBEATS_BASE}/track",
                params={"ids": ",".join(batch)},
                timeout=20,
            )
            for t in r.json().get("content", []):
                sid = (t.get("href") or "").rstrip("/").split("/")[-1]
                if sid:
                    out[sid] = t["id"]
        except Exception:
            pass
        time.sleep(0.2)
    return out


def recco_features(uuids: list[str]) -> dict[str, dict]:
    """ReccoBeats UUIDs -> feature dicts."""
    out: dict[str, dict] = {}
    for batch in chunked(uuids, BATCH):
        try:
            r = requests.get(
                f"{config.RECCOBEATS_BASE}/audio-features",
                params={"ids": ",".join(batch)},
                timeout=20,
            )
            for t in r.json().get("content", []):
                out[t["id"]] = {k: t.get(k) for k in FEATURE_KEYS}
        except Exception:
            pass
        time.sleep(0.2)
    return out


def resolve_spotify_ids(songs, cache, cache_path, client_id, client_secret) -> bool:
    """Step 1. Returns True if the run was cut short by rate limiting."""
    todo = [
        s for s in songs
        if f"{s['artist'].lower()}::{s['title'].lower()}" not in cache["spotify_id"]
    ]
    print(
        f"Step 1/3: resolving Spotify track IDs "
        f"({len(todo)} remaining, {len(songs) - len(todo)} cached) ..."
    )
    if not todo:
        return False
    if not client_secret:
        print("  (no SPOTIFY_CLIENT_SECRET set — skipping step 1, using cached IDs only)")
        return False

    token = spotify_token(client_id, client_secret)
    for i, s in enumerate(todo, 1):
        key = f"{s['artist'].lower()}::{s['title'].lower()}"
        sid = spotify_search_id(token, s["title"], s["artist"])
        if sid == TOKEN_EXPIRED:
            token = spotify_token(client_id, client_secret)
            sid = spotify_search_id(token, s["title"], s["artist"])
        if sid == RATE_LIMITED:
            write_json(cache_path, cache)
            print("  ! Spotify rate-limited with a long Retry-After. Stopping step 1;")
            print("    re-run later to resume.")
            return True
        cache["spotify_id"][key] = sid  # may legitimately be None (no match)
        if i % 50 == 0:
            write_json(cache_path, cache)
            resolved = sum(1 for v in cache["spotify_id"].values() if v)
            print(f"  [{i}/{len(todo)}] resolved so far: {resolved}")
        time.sleep(config.SPOTIFY_SEARCH_DELAY)

    write_json(cache_path, cache)
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Attach audio features to the library")
    ap.add_argument("--songs", type=Path, default=config.SONGS_JSON)
    ap.add_argument("--cache", type=Path, default=config.FEATURES_CACHE)
    args = ap.parse_args()

    songs = load_songs(args.songs)
    cache = read_json(args.cache, default=None) or {
        "spotify_id": {}, "recco_uuid": {}, "features": {}
    }
    for k in ("spotify_id", "recco_uuid", "features"):
        cache.setdefault(k, {})

    client_id, client_secret = config.spotify_credentials()
    if not client_id and client_secret:
        sys.exit("[FATAL] SPOTIFY_CLIENT_SECRET is set but SPOTIFY_CLIENT_ID is not.")

    rate_limited = resolve_spotify_ids(
        songs, cache, args.cache, client_id, client_secret
    )

    # ── Step 2 ──────────────────────────────────────────────────────────────
    sids = sorted(
        {v for v in cache["spotify_id"].values() if v and v not in cache["recco_uuid"]}
    )
    print(f"\nStep 2/3: mapping {len(sids)} new Spotify IDs to ReccoBeats ...")
    cache["recco_uuid"].update(recco_map_ids(sids))
    write_json(args.cache, cache)

    # ── Step 3 ──────────────────────────────────────────────────────────────
    uuids = sorted(
        {u for u in cache["recco_uuid"].values() if u and u not in cache["features"]}
    )
    print(f"\nStep 3/3: fetching audio features for {len(uuids)} tracks ...")
    cache["features"].update(recco_features(uuids))
    write_json(args.cache, cache)

    # ── Merge ───────────────────────────────────────────────────────────────
    enriched = 0
    for s in songs:
        key = f"{s['artist'].lower()}::{s['title'].lower()}"
        sid = cache["spotify_id"].get(key)
        uuid = cache["recco_uuid"].get(sid) if sid else None
        feats = cache["features"].get(uuid) if uuid else None
        if feats and feats.get("danceability") is not None:
            s["spotify_id"] = sid
            s["features"] = feats
            enriched += 1
        else:
            s.pop("features", None)
            s.pop("spotify_id", None)

    write_json(args.songs, songs, indent=2)

    n = len(songs)
    print(f"\nDone. {enriched}/{n} tracks enriched ({100 * enriched // n}% coverage).")
    print("Tracks without features fall back to tag-based recommendation.")
    if rate_limited:
        remaining = sum(
            1 for s in songs
            if f"{s['artist'].lower()}::{s['title'].lower()}" not in cache["spotify_id"]
        )
        print(f"\nNOTE: step 1 stopped early — {remaining} tracks still unresolved.")
        print("Re-run later; Spotify's penalty window resets within a few hours.")


if __name__ == "__main__":
    main()
