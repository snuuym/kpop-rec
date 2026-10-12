#!/usr/bin/env python3
"""Stage 2b — attach album-level tags, because track-level ones stopped arriving.

Why this stage exists
---------------------
``track.getTopTags`` is the project's only tag source and it has been
returning empty lists for most tracks since at least 2025, while the same tags
remain visible on Last.fm's own pages. Last.fm has not fixed it. Measured over
64 tracks the library recorded as untagged, **the page showed tags for every
one of them**, and effective tags for three quarters -- so the corpus-wide
"77.4% carry no usable tag" was measuring the endpoint, not the catalogue.

Worse for the project's central claim, the endpoint's failure rate is itself
popularity-dependent. Splitting the observed coverage into a catalogue term
and an API-reliability term puts the estimated success rate at 0.3% in the
coldest quintile against 83% in the hottest. The "tag coverage collapses in
the long tail" curve is largely that gradient.

``album.getTopTags`` is a different endpoint and still answers: 78% of a
stratified sample, 74% with a tag that survives the discriminative filter, and
**no collapse across quintiles** (54% / 79% / 88% / 79% / 71%).

What this stage does NOT do
---------------------------
It does not write into ``all_tags``. Track-level tags stay exactly as the API
gave them, empty where it gave nothing, because that record is the evidence
for the finding above. Album tags land in their own field at their own
granularity, and every downstream report says which level a number came from.

That granularity is a real loss and is not papered over: every track on a
record inherits one tag set, so album tags cannot tell two songs on the same
album apart. A recommender leaning on them will treat an album as a block.

Usage
-----
    export LASTFM_API_KEY=xxx
    python3 scripts/backfill_album_tags.py
    python3 scripts/backfill_album_tags.py --songs data/songs.json
    python3 scripts/backfill_album_tags.py --dry-run

Resumable: progress is cached in ``data/album_tags_cache.json``.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kpoprec import config  # noqa: E402
from kpoprec.io import (  # noqa: E402
    load_songs,
    read_json,
    write_json,
    write_json_with_backup,
)
from kpoprec.lastfm import NOT_FOUND, RATE_LIMITED, LastFM  # noqa: E402
from kpoprec.normalize import key_of, song_key  # noqa: E402

CHECKPOINT_EVERY = 100


def main() -> None:
    ap = argparse.ArgumentParser(description="Attach album-level tags")
    ap.add_argument("--songs", type=Path, default=config.SONGS_JSON)
    ap.add_argument("--cache", type=Path, default=config.ALBUM_TAGS_CACHE)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    songs = load_songs(args.songs)
    cache = read_json(args.cache, default=None) or {"album": {}, "tags": {}}
    cache.setdefault("album", {})   # song key   -> album title or None
    cache.setdefault("tags", {})    # artist::album -> list of tags

    need_album = [s for s in songs if song_key(s) not in cache["album"]]
    print(f"[scan] {len(songs)} tracks, {len(need_album)} need an album lookup")
    if args.dry_run:
        known = {a for a in cache["album"].values() if a}
        print(f"[dry-run] ~{len(need_album) * config.LASTFM_DELAY / 60:.1f} min for albums, "
              f"then one call per album not already cached ({len(known)} known so far)")
        return

    client = LastFM(config.lastfm_key())

    # ── Which album is each track on ────────────────────────────────────────
    for i, s in enumerate(need_album, 1):
        res = client.track_album(s["artist"], s["title"])
        if res is RATE_LIMITED:
            write_json(args.cache, cache)
            print("  ! rate limit — progress saved, re-run later")
            break
        cache["album"][song_key(s)] = res       # may legitimately be None
        if i % CHECKPOINT_EVERY == 0:
            write_json(args.cache, cache)
            print(f"  [album {i}/{len(need_album)}]")
        client.sleep()
    write_json(args.cache, cache)

    # ── Tags per album, fetched once per album rather than once per track ───
    wanted: dict[str, tuple[str, str]] = {}
    for s in songs:
        album = cache["album"].get(song_key(s))
        if album:
            wanted.setdefault(key_of(s["artist"], album), (s["artist"], album))
    todo = [k for k in wanted if k not in cache["tags"]]
    print(f"\n[albums] {len(wanted)} distinct albums, {len(todo)} to fetch "
          f"(~{len(todo) * config.LASTFM_DELAY / 60:.1f} min)")

    for i, k in enumerate(todo, 1):
        artist, album = wanted[k]
        res = client.album_top_tags(artist, album)
        if res is RATE_LIMITED:
            write_json(args.cache, cache)
            print("  ! rate limit — progress saved, re-run later")
            break
        if res is None:
            continue                            # transport error: retry next run
        cache["tags"][k] = [] if res is NOT_FOUND else res[0]
        if i % CHECKPOINT_EVERY == 0:
            write_json(args.cache, cache)
            print(f"  [tags {i}/{len(todo)}]")
        client.sleep()
    write_json(args.cache, cache)

    # ── Merge, in their own fields ──────────────────────────────────────────
    stat: Counter = Counter()
    for s in songs:
        album = cache["album"].get(song_key(s))
        if not album:
            s.pop("album", None)
            s.pop("album_tags", None)
            stat["no album"] += 1
            continue
        s["album"] = album
        tags = cache["tags"].get(key_of(s["artist"], album))
        if tags:
            s["album_tags"] = tags[:20]
            stat["album tagged"] += 1
        else:
            s.pop("album_tags", None)
            stat["album untagged" if tags is not None else "album not fetched"] += 1

    write_json_with_backup(args.songs, songs)

    n = len(songs)
    print(f"\n{'=' * 60}")
    for label, c in stat.most_common():
        print(f"  {label:<20} {c:>5}  ({c / n * 100:.1f}%)")
    print(f"\nBackup written to {args.songs}.bak")
    print("\nNote: `all_tags` is untouched. Album tags are a coarser, separate")
    print("layer -- every track on a record shares them. Reports say which level")
    print("each number came from; they are not merged into the track-level count.")


if __name__ == "__main__":
    main()
