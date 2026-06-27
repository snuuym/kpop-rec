"""
K-Pop Audio-Feature Builder
---------------------------
Enriches songs.json with objective audio features for similarity-based
recommendation, replacing the dead Spotify audio-features endpoint
(deprecated 2024-11-27) with the free ReccoBeats API.

Pipeline (all offline, run once):
  1. Spotify Search  : (title, artist)            -> Spotify track ID
  2. ReccoBeats map  : Spotify track ID  (40/req) -> ReccoBeats UUID
  3. ReccoBeats feats: ReccoBeats UUID   (40/req) -> audio features

Spotify search needs a token via the Client Credentials flow, so this
script reads the client SECRET from the environment — it is NEVER written
to songs.json or committed:

    export SPOTIFY_CLIENT_ID=3b83bb835d39465aaa7e2e857981d7ba   # optional, has default
    export SPOTIFY_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    python3 build_features.py

Resumable: intermediate lookups are cached in features_cache.json, so a
re-run only fetches what is missing.
"""

import os, json, time, base64
import requests

CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID", "3b83bb835d39465aaa7e2e857981d7ba")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")

SONGS_FILE  = "songs.json"
CACHE_FILE  = "features_cache.json"   # gitignored; resume support
RECCO_BASE  = "https://api.reccobeats.com/v1"
SPOTIFY_TOKEN_URL  = "https://accounts.spotify.com/api/token"
SPOTIFY_SEARCH_URL = "https://api.spotify.com/v1/search"

SEARCH_DELAY     = 0.35   # gentler pacing to avoid the 429 penalty box
MAX_RETRY_AFTER  = 120    # if Spotify asks us to wait longer, stop Step 1 instead

# Feature fields we keep (Spotify-compatible names from ReccoBeats)
FEATURE_KEYS = [
    "danceability", "energy", "valence", "tempo", "acousticness",
    "instrumentalness", "loudness", "speechiness", "liveness",
]


# ── Cache helpers ───────────────────────────────────────────────────────────
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"spotify_id": {}, "recco_uuid": {}, "features": {}}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


# ── Spotify (Client Credentials) ────────────────────────────────────────────
def spotify_token():
    if not CLIENT_SECRET:
        raise SystemExit(
            "ERROR: SPOTIFY_CLIENT_SECRET not set.\n"
            "Get it from https://developer.spotify.com/dashboard (your app -> Settings),\n"
            "then: export SPOTIFY_CLIENT_SECRET=...  before running."
        )
    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    r = requests.post(
        SPOTIFY_TOKEN_URL,
        headers={"Authorization": f"Basic {auth}"},
        data={"grant_type": "client_credentials"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def spotify_search_id(token, title, artist):
    """Return best-match Spotify track ID, or None."""
    q = f'track:{title} artist:{artist}'
    for attempt in range(4):
        r = requests.get(
            SPOTIFY_SEARCH_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={"q": q, "type": "track", "limit": 1},
            timeout=15,
        )
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", "2"))
            # A long Retry-After means Spotify has thrown us in the penalty box
            # (it can be many hours). Don't block — signal the caller to stop
            # Step 1 and proceed with whatever IDs we already have.
            if wait > MAX_RETRY_AFTER:
                return "__RATELIMIT__"
            time.sleep(wait + 1)
            continue
        if r.status_code == 401:
            return "__EXPIRED__"      # signal caller to refresh token
        if r.status_code != 200:
            return None
        items = r.json().get("tracks", {}).get("items", [])
        return items[0]["id"] if items else None
    return None


# ── ReccoBeats ──────────────────────────────────────────────────────────────
def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def recco_map_ids(spotify_ids):
    """Spotify track IDs -> {spotify_id: reccobeats_uuid} (40 per request)."""
    out = {}
    for batch in chunked(spotify_ids, 40):
        try:
            r = requests.get(f"{RECCO_BASE}/track",
                             params={"ids": ",".join(batch)}, timeout=20)
            for t in r.json().get("content", []):
                sid = (t.get("href") or "").rstrip("/").split("/")[-1]
                if sid:
                    out[sid] = t["id"]
        except Exception:
            pass
        time.sleep(0.2)
    return out


def recco_features(uuids):
    """ReccoBeats UUIDs -> {uuid: {feature: value}} (40 per request)."""
    out = {}
    for batch in chunked(uuids, 40):
        try:
            r = requests.get(f"{RECCO_BASE}/audio-features",
                             params={"ids": ",".join(batch)}, timeout=20)
            for t in r.json().get("content", []):
                out[t["id"]] = {k: t.get(k) for k in FEATURE_KEYS}
        except Exception:
            pass
        time.sleep(0.2)
    return out


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    with open(SONGS_FILE, encoding="utf-8") as f:
        songs = json.load(f)
    cache = load_cache()

    # ── Step 1: resolve Spotify IDs (cached per "artist::title") ────────────
    todo = [s for s in songs
            if f"{s['artist'].lower()}::{s['title'].lower()}" not in cache["spotify_id"]]
    print(f"Step 1/3: Resolving Spotify track IDs "
          f"({len(todo)} remaining, {len(songs) - len(todo)} cached) ...")
    rate_limited = False
    if todo and not CLIENT_SECRET:
        # No secret provided: skip Spotify resolution entirely and just process
        # whatever IDs are already cached through ReccoBeats (Steps 2-3).
        print("  (no SPOTIFY_CLIENT_SECRET set — skipping Step 1, using cached IDs only)")
    elif todo:
        token = spotify_token()
        for i, s in enumerate(todo, 1):
            key = f"{s['artist'].lower()}::{s['title'].lower()}"
            sid = spotify_search_id(token, s["title"], s["artist"])
            if sid == "__EXPIRED__":
                token = spotify_token()
                sid = spotify_search_id(token, s["title"], s["artist"])
            if sid == "__RATELIMIT__":
                save_cache(cache)
                print("  ! Spotify rate-limited (long Retry-After). Stopping Step 1; "
                      "re-run later to resume the rest.")
                rate_limited = True
                break
            cache["spotify_id"][key] = sid     # may be None (no match)
            if i % 50 == 0:
                save_cache(cache)
                print(f"  [{i}/{len(todo)}] resolved so far: "
                      f"{sum(1 for v in cache['spotify_id'].values() if v)}")
            time.sleep(SEARCH_DELAY)
        save_cache(cache)

    # ── Step 2: map Spotify IDs -> ReccoBeats UUIDs ─────────────────────────
    sids = sorted({v for v in cache["spotify_id"].values()
                   if v and v not in cache["recco_uuid"]})
    print(f"\nStep 2/3: Mapping {len(sids)} new Spotify IDs to ReccoBeats ...")
    cache["recco_uuid"].update(recco_map_ids(sids))
    save_cache(cache)

    # ── Step 3: fetch audio features ────────────────────────────────────────
    uuids = sorted({u for u in cache["recco_uuid"].values()
                    if u and u not in cache["features"]})
    print(f"\nStep 3/3: Fetching audio features for {len(uuids)} tracks ...")
    cache["features"].update(recco_features(uuids))
    save_cache(cache)

    # ── Merge into songs.json ───────────────────────────────────────────────
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

    with open(SONGS_FILE, "w", encoding="utf-8") as f:
        json.dump(songs, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {enriched}/{len(songs)} songs enriched with audio features "
          f"({100 * enriched // len(songs)}% coverage).")
    print("Songs without features fall back to tag-based recommendation.")
    if rate_limited:
        remaining = sum(1 for s in songs
                        if f"{s['artist'].lower()}::{s['title'].lower()}" not in cache["spotify_id"])
        print(f"\nNOTE: Spotify rate-limited Step 1 — {remaining} songs still unresolved.")
        print("Re-run this script later (the penalty resets in a few hours) to fill them in.")


if __name__ == "__main__":
    main()
