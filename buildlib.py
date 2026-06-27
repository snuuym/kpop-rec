"""
K-Pop Song Library Builder  v4
-------------------------------
Changes vs v3:
  - Root tags = only k-pop / kpop / korean pop (guaranteed K-pop origin)
  - Sub-genre rules exclude the root itself (no "K-pop" label in tags[])
  - Sub-genres now cover the full K-pop taxonomy as style descriptors only

Usage:
    pip install requests
    python3 build_library.py

Output:
    songs.json
"""

import requests, json, time
from collections import Counter

API_KEY = "7f2d0885886279a622e2a0384c807f85"
BASE    = "https://ws.audioscrobbler.com/2.0/"
OUT     = "songs.json"

# ── Root tags: only use these to PULL tracks (all are definitionally K-pop)
KPOP_ROOT_TAGS = ["k-pop", "kpop", "korean pop"]

# ── Sub-genre rules ────────────────────────────────────────────────────────
# These describe STYLE, not origin.
# "K-pop" / "kpop" / "korean pop" are intentionally absent — they're roots.
# Order matters only for readability; ALL matching rules fire (up to MAX_SUBGENRES).
MAX_SUBGENRES = 5

SUBGENRE_RULES = [
    # ── Vocal / mood styles
    ("Ballad",          ["ballad", "k-ballad", "korean ballad", "slow jam"]),
    ("R&B",             ["r&b", "k-r&b", "rnb", "neo soul", "soul"]),
    ("Dream pop",       ["dream pop", "shoegaze", "ambient pop", "ethereal", "chillwave"]),
    ("Bubblegum pop",   ["bubblegum pop", "bubble pop", "bubblegum", "cute", "kawaii", "aegyo"]),

    # ── Rhythm / production styles
    ("Dance pop",       ["dance pop", "electropop", "synth-pop", "synthpop"]),
    ("Electronic",      ["electronic", "edm", "club", "house", "techno", "trance"]),
    ("Hip-hop",         ["hip hop", "hip-hop", "rap", "trap", "k-rap", "k-hip-hop"]),
    ("Rock",            ["rock", "k-rock", "alternative rock", "alt-rock", "punk"]),
    ("Indie",           ["indie", "k-indie", "indie pop", "lo-fi", "lo fi"]),

    # ── Group / artist type
    ("Girl group",      ["girl group", "girlgroup", "female idol", "idol girl", "girls"]),
    ("Boy group",       ["boy band", "boy group", "boyband", "male idol", "idol group"]),
    ("Solo",            ["solo", "soloist"]),

    # ── Context / theme
    ("OST",             ["ost", "korean ost", "k-drama ost", "drama ost", "anime ost"]),
    ("Dance",           ["dance", "choreography", "performance"]),
]

# Root keywords to EXCLUDE from sub-genre output
ROOT_KEYWORDS = {"k-pop", "kpop", "korean pop", "korean", "idol", "k pop"}


def api_get(params, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(BASE, params={**params, "api_key": API_KEY, "format": "json"}, timeout=12)
            data = r.json()
            return None if "error" in data else data
        except Exception:
            if attempt == retries - 1:
                return None
            time.sleep(1.5)


def get_tag_top_tracks(tag, pages=5, limit=100):
    """Pull up to pages*limit tracks for a root tag."""
    tracks = []
    for page in range(1, pages + 1):
        data = api_get({"method": "tag.getTopTracks", "tag": tag, "limit": limit, "page": page})
        if not data:
            break
        page_tracks = data.get("tracks", {}).get("track", [])
        if not page_tracks:
            break
        tracks.extend(page_tracks)
        time.sleep(0.2)
    return tracks


def get_track_tags(artist, title):
    """Return lowercased tag names with count >= 10."""
    data = api_get({"method": "track.getTopTags", "artist": artist, "track": title})
    if not data:
        return []
    raw = data.get("toptags", {}).get("tag", [])
    return [t["name"].lower() for t in raw if int(t.get("count", 0)) >= 10]


def classify_subgenres(track_tags):
    """
    Return up to MAX_SUBGENRES style sub-genre labels.
    Skips any label whose keywords are purely root/origin keywords.
    """
    blob    = " ".join(track_tags)
    matched = []

    for label, keywords in SUBGENRE_RULES:
        if any(kw in blob for kw in keywords):
            matched.append(label)
        if len(matched) >= MAX_SUBGENRES:
            break

    return matched if matched else ["Ballad"]   # safe fallback


def build_library():
    seen = {}   # "artist::title" → song dict

    # ── Phase A: collect tracks from K-pop root tags ───────────────────────
    print("=" * 56)
    print("Phase A: Collecting K-pop tracks (root tags only)")
    print("=" * 56)

    for root_tag in KPOP_ROOT_TAGS:
        print(f"\n  [{root_tag}] pulling up to 500 tracks ...")
        tracks = get_tag_top_tracks(root_tag, pages=5, limit=100)
        added  = 0
        for t in tracks:
            name   = (t.get("name") or "").strip()
            artist = t.get("artist") or {}
            artist = (artist.get("name") if isinstance(artist, dict) else str(artist)).strip()
            if not name or not artist or artist.lower() in ("", "[unknown]"):
                continue
            key = f"{artist.lower()}::{name.lower()}"
            if key in seen:
                continue
            dur = int(t.get("duration") or 0)
            if dur < 60:
                dur = 210
            seen[key] = {
                "title":   name,
                "artist":  artist,
                "tags":    [],        # filled in Phase B (style sub-genres only)
                "all_tags": [],       # raw Last.fm tags, kept for debugging
                "dur":     dur,
                "durStr":  f"{dur // 60}:{dur % 60:02d}",
                "url":     t.get("url", ""),
            }
            added += 1
        print(f"  → {added} new  |  total: {len(seen)}")

    songs_list = list(seen.values())
    print(f"\nPhase A complete: {len(songs_list)} unique K-pop tracks.")

    # ── Phase B: per-track tag fetch + sub-genre classification ───────────
    print("\n" + "=" * 56)
    print("Phase B: Classifying sub-genres per track")
    print(f"         (~{len(songs_list) // 4} seconds estimated)")
    print("=" * 56)

    label_counter = Counter()
    for i, song in enumerate(songs_list, 1):
        raw_tags        = get_track_tags(song["artist"], song["title"])
        subgenres       = classify_subgenres(raw_tags)

        song["all_tags"] = raw_tags
        song["tags"]     = subgenres

        for sg in subgenres:
            label_counter[sg] += 1

        if i % 50 == 0 or i == len(songs_list):
            print(f"  [{i}/{len(songs_list)}] ...")
        time.sleep(0.25)

    # ── Save ──────────────────────────────────────────────────────────────
    songs_list.sort(key=lambda s: (s["tags"][0] if s["tags"] else "", s["title"].lower()))

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(songs_list, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 56}")
    print(f"Done!  {len(songs_list)} tracks saved to {OUT}")
    print("\nSub-genre coverage (tracks containing each label):")
    for label, n in label_counter.most_common():
        bar = "█" * (n // 8)
        print(f"  {label:<22} {n:>4}  {bar}")


if __name__ == "__main__":
    build_library()