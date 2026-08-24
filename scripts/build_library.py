#!/usr/bin/env python3
"""Stage 1 — build the track library from Last.fm.

Two passes:

  Phase A  pull candidate tracks from the K-pop root tags (origin filter)
  Phase B  fetch per-track tags and assign style sub-genres

Phase A gives breadth; Phase B gives the labels everything downstream scores
on. Note that Phase A inserts tracks in Last.fm popularity order, so if Phase B
is interrupted the tracks that did get tagged are systematically the popular
ones. ``backfill_tags.py`` exists to close that gap, and
``analyze_tag_sparsity.py`` explicitly tests for the resulting selection bias.

Usage
-----
    export LASTFM_API_KEY=xxx
    python3 scripts/build_library.py
    python3 scripts/build_library.py --pages 3 --out data/songs.json

Output
------
    data/songs.json
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kpoprec import config  # noqa: E402
from kpoprec.io import write_json  # noqa: E402
from kpoprec.lastfm import RATE_LIMITED, LastFM  # noqa: E402
from kpoprec.taxonomy import (  # noqa: E402
    CLASSIFY_MIN,
    KPOP_ROOT_TAGS,
    classify_subgenres,
)

# A track shorter than this is almost always bad metadata rather than a real
# short track; substitute the corpus-typical duration instead of trusting it.
MIN_PLAUSIBLE_DURATION = 60
DEFAULT_DURATION = 210


def collect_candidates(client: LastFM, pages: int) -> dict[str, dict]:
    """Phase A — de-duplicated tracks across all root tags."""
    print("=" * 60)
    print("Phase A: collecting candidate tracks from K-pop root tags")
    print("=" * 60)

    seen: dict[str, dict] = {}
    for root_tag in KPOP_ROOT_TAGS:
        print(f"\n  [{root_tag}] pulling up to {pages * 100} tracks ...")
        added = 0
        for t in client.tag_top_tracks(root_tag, pages=pages):
            name = (t.get("name") or "").strip()
            artist = t.get("artist") or {}
            artist = (
                artist.get("name") if isinstance(artist, dict) else str(artist)
            ).strip()
            if not name or not artist or artist.lower() in ("", "[unknown]"):
                continue

            key = f"{artist.lower()}::{name.lower()}"
            if key in seen:
                continue

            dur = int(t.get("duration") or 0)
            if dur < MIN_PLAUSIBLE_DURATION:
                dur = DEFAULT_DURATION

            seen[key] = {
                "title": name,
                "artist": artist,
                "tags": [],       # style sub-genres, filled in Phase B
                "all_tags": [],   # raw Last.fm tags, kept as the audit trail
                "dur": dur,
                "durStr": f"{dur // 60}:{dur % 60:02d}",
                "url": t.get("url", ""),
            }
            added += 1
        print(f"  -> {added} new  |  total: {len(seen)}")

    return seen


def classify_all(client: LastFM, songs: list[dict]) -> Counter:
    """Phase B — per-track tag fetch and sub-genre assignment."""
    print("\n" + "=" * 60)
    print("Phase B: classifying sub-genres per track")
    print(f"         (~{len(songs) * config.LASTFM_DELAY / 60:.0f} minutes)")
    print("=" * 60)

    labels: Counter = Counter()
    for i, song in enumerate(songs, 1):
        res = client.track_top_tags(song["artist"], song["title"], CLASSIFY_MIN)
        if res is RATE_LIMITED:
            print("  ! Last.fm rate limit reached — stopping Phase B early.")
            print("    Re-run `backfill_tags.py` later to fill the remainder.")
            break
        if isinstance(res, tuple):
            all_tags, confident = res
            song["all_tags"] = all_tags[:15]
            song["tags"] = classify_subgenres(confident)
        else:
            song["tags"] = classify_subgenres([])

        labels.update(song["tags"])
        if i % 50 == 0 or i == len(songs):
            print(f"  [{i}/{len(songs)}] ...")
        client.sleep()

    return labels


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the K-pop track library")
    ap.add_argument("--out", type=Path, default=config.SONGS_JSON)
    ap.add_argument(
        "--pages", type=int, default=5,
        help="pages of 100 tracks to pull per root tag (default 5)",
    )
    args = ap.parse_args()

    client = LastFM(config.lastfm_key())

    seen = collect_candidates(client, args.pages)
    songs = list(seen.values())
    print(f"\nPhase A complete: {len(songs)} unique tracks.")

    labels = classify_all(client, songs)

    songs.sort(key=lambda s: (s["tags"][0] if s["tags"] else "", s["title"].lower()))
    write_json(args.out, songs, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Done. {len(songs)} tracks -> {args.out}")
    print("\nSub-genre coverage (tracks carrying each label):")
    for label, n in labels.most_common():
        print(f"  {label:<22} {n:>4}  {'#' * (n // 8)}")


if __name__ == "__main__":
    main()
