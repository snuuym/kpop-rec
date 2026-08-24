#!/usr/bin/env python3
"""Stage 2 — backfill tracks that Phase B of the library build never reached.

Why this exists
---------------
Phase B walks the library in insertion order, and Phase A inserts in Last.fm
popularity order. When Phase B was interrupted, the tracks that *did* get
tagged were therefore the most popular ones — a textbook selection bias.

That matters because the headline claim of this project is "most of the corpus
has no usable tags". Measured on the interrupted data, that claim would be
unfalsifiable: an empty ``all_tags`` could mean either "nobody tagged this
track" (a real finding) or "we never asked" (a collection gap).

This script asks. Every track with an empty ``all_tags`` is queried
individually, and the outcome is recorded as ``tagged`` / ``no_tags`` /
``notfound``. Tracks touched here are stamped ``tag_source: "backfill"`` so
``analyze_tag_sparsity.py`` can quantify the bias between the two passes rather
than assume it away.

Usage
-----
    export LASTFM_API_KEY=xxx
    python3 scripts/backfill_tags.py
    python3 scripts/backfill_tags.py --dry-run        # count the work first
    python3 scripts/backfill_tags.py --min-count 20   # stricter classification

Resumable: progress is cached in ``data/tags_cache.json``.
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
from kpoprec.normalize import song_key  # noqa: E402
from kpoprec.taxonomy import classify_subgenres  # noqa: E402

CHECKPOINT_EVERY = 100


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill missing Last.fm tags")
    ap.add_argument("--songs", type=Path, default=config.SONGS_JSON)
    ap.add_argument("--cache", type=Path, default=config.TAGS_CACHE)
    ap.add_argument(
        "--min-count", type=int, default=10,
        help="only tags with at least this many votes drive sub-genre "
             "classification (default 10)",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    songs = load_songs(args.songs)
    missing = [s for s in songs if not s.get("all_tags")]
    print(f"[scan] {len(songs)} tracks, {len(missing)} missing all_tags")

    if args.dry_run:
        print(f"[dry-run] ~{len(missing) * config.LASTFM_DELAY / 60:.1f} minutes of API calls")
        return
    if not missing:
        print("[done] nothing to backfill")
        return

    client = LastFM(config.lastfm_key())
    cache: dict = read_json(args.cache, default={}) or {}
    todo = [s for s in missing if song_key(s) not in cache]
    print(
        f"[fetch] {len(todo)} to process, {len(missing) - len(todo)} already cached "
        f"(~{len(todo) * config.LASTFM_DELAY / 60:.1f} min)"
    )

    hits = 0
    for i, s in enumerate(todo, 1):
        res = client.track_top_tags(s["artist"], s["title"], args.min_count)

        if res is RATE_LIMITED:
            write_json(args.cache, cache)
            print("  ! Last.fm rate limit — progress saved, re-run later")
            break
        if res is NOT_FOUND:
            cache[song_key(s)] = {"all": [], "conf": [], "status": "notfound"}
        elif res is None:
            continue  # transport error: do not cache, retry next run
        else:
            all_tags, confident = res
            cache[song_key(s)] = {
                "all": all_tags,
                "conf": confident,
                "status": "tagged" if all_tags else "no_tags",
            }
            if all_tags:
                hits += 1

        if i % CHECKPOINT_EVERY == 0:
            write_json(args.cache, cache)
            print(f"  [{i}/{len(todo)}] tagged so far: {hits}")
        client.sleep()

    write_json(args.cache, cache)

    # ── Merge back into the library ─────────────────────────────────────────
    filled: Counter = Counter()
    for s in songs:
        if s.get("all_tags"):
            continue
        entry = cache.get(song_key(s))
        if not entry:
            continue
        s["all_tags"] = entry["all"]
        s["tags"] = classify_subgenres(entry["conf"]) if entry["conf"] else ["K-pop"]
        s["tag_source"] = "backfill"  # marks this record for the bias check
        filled[entry.get("status", "unknown")] += 1

    write_json_with_backup(args.songs, songs)

    still_empty = sum(1 for s in songs if not s.get("all_tags"))
    n = len(songs)
    print(f"\n{'=' * 60}")
    print(
        f"Backfill result: tagged {filled['tagged']} | "
        f"queried but untagged by anyone {filled['no_tags']} | "
        f"not found {filled['notfound']}"
    )
    print(f"all_tags coverage: {n - still_empty}/{n} ({(n - still_empty) / n * 100:.1f}%)")
    print(f"Backup written to {args.songs}.bak")
    print("\nNext:")
    print("  1. python3 scripts/enrich_metadata.py --skip-year")
    print("  2. python3 scripts/analyze_tag_sparsity.py   # now unbiased")


if __name__ == "__main__":
    main()
