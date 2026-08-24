#!/usr/bin/env python3
"""Feasibility probe — is there enough ground truth to evaluate on at all?

Run this *before* committing to the full ground-truth build. ``getSimilar``
returns similar tracks from all of Last.fm, but only those that also exist in
the local library can serve as positive samples. On a ~1,300-track corpus that
intersection can be nearly empty, which would make any offline metric
meaningless.

The probe samples across popularity quintiles rather than uniformly, because
the failure mode is not uniform: the head is well covered and the tail is not,
and an average over the whole corpus would hide exactly that.

Decision rule:

  mean positives >= 5   track-level ground truth is usable as planned
  mean positives 1-4    too sparse; grow the corpus or fall back to
                        artist-level labels, and keep K small
  mean positives < 1    track-level ground truth is not viable

An artist-level fallback (library tracks by similar artists) is measured
alongside, so there is a fallback number rather than just a verdict.

Usage
-----
    export LASTFM_API_KEY=xxx
    python3 scripts/check_gt_density.py --sample 60
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kpoprec import config  # noqa: E402
from kpoprec.io import load_songs, write_json  # noqa: E402
from kpoprec.lastfm import LastFM  # noqa: E402
from kpoprec.normalize import norm  # noqa: E402

USABLE_THRESHOLD = 5
MARGINAL_THRESHOLD = 1
# Above this share of zero-positive seeds, a quintile cannot be evaluated.
BLIND_SPOT_THRESHOLD = 0.4


def main() -> None:
    ap = argparse.ArgumentParser(description="Probe ground-truth density")
    ap.add_argument("--songs", type=Path, default=config.SONGS_JSON)
    ap.add_argument("--outdir", type=Path, default=config.REPORTS_DIR)
    ap.add_argument("--sample", type=int, default=60, help="total seeds, split across 5 quintiles")
    ap.add_argument("--limit", type=int, default=100, help="similar tracks per seed")
    args = ap.parse_args()

    songs = load_songs(args.songs)
    client = LastFM(config.lastfm_key())

    by_track = {(norm(s["artist"]), norm(s["title"])) for s in songs}
    by_artist: dict[str, list] = {}
    for s in songs:
        by_artist.setdefault(norm(s["artist"]), []).append(s)
    print(f"[index] {len(songs)} tracks / {len(by_artist)} artists")

    pool = [s for s in songs if s.get("listeners")]
    if len(pool) < 50:
        sys.exit(
            "[FATAL] too few tracks carry a `listeners` field to stratify by "
            "popularity.\n        Run scripts/enrich_metadata.py first."
        )
    pool.sort(key=lambda s: s["listeners"])
    quintiles = np.array_split(pool, 5)
    per_q = max(args.sample // 5, 4)

    header = (
        f"{'Quintile':<10}{'med listeners':>15}{'seeds w/ data':>15}"
        f"{'mean positives':>16}{'median':>8}{'zero':>7}{'artist fallback':>17}"
    )
    print(f"\n{header}\n{'-' * len(header)}")

    rows = []
    for qi, q in enumerate(quintiles, 1):
        step = max(len(q) // per_q, 1)
        sample = list(q[::step])[:per_q]
        hits, track_pos, artist_pos = 0, [], []

        for s in sample:
            sims = client.similar_tracks(s["artist"], s["title"], args.limit)
            sims = sims if isinstance(sims, list) else []
            if sims:
                hits += 1
            self_key = (norm(s["artist"]), norm(s["title"]))
            n = sum(
                1 for t in sims
                if (k := (norm(t["artist"]), norm(t["title"]))) in by_track
                and k != self_key
            )
            track_pos.append(n)
            client.sleep()

            similar_artists = client.similar_artists(s["artist"], limit=50)
            m = sum(
                len(by_artist.get(norm(a.get("name", "")), []))
                for a in similar_artists
                if norm(a.get("name", "")) in by_artist
            )
            artist_pos.append(m)
            client.sleep()

        med = int(np.median([x["listeners"] for x in sample]))
        row = dict(
            q=f"Q{qi}",
            listeners=med,
            hit=hits / len(sample),
            mean=float(np.mean(track_pos)),
            median=float(np.median(track_pos)),
            zero=float(np.mean([t == 0 for t in track_pos])),
            amean=float(np.mean(artist_pos)),
        )
        rows.append(row)
        print(
            f"Q{qi:<9}{med:>15,}{f'{hits}/{len(sample)}':>15}"
            f"{row['mean']:>16.1f}{row['median']:>8.0f}"
            f"{row['zero'] * 100:>6.0f}%{row['amean']:>17.1f}"
        )

    overall = float(np.mean([r["mean"] for r in rows]))
    zero_q1 = rows[0]["zero"]
    print("-" * len(header))
    print(f"\nMean in-library positives across the corpus: {overall:.1f}")

    print("\nVerdict")
    if overall >= USABLE_THRESHOLD:
        print("  Track-level ground truth is dense enough. Proceed with the full build.")
    elif overall >= MARGINAL_THRESHOLD:
        print("  Track-level ground truth is sparse. Recommended mitigations:")
        print("    1) Use getSimilar results as a crawl frontier to grow the corpus,")
        print("       which raises both label density and candidate-pool size.")
        print("    2) Keep K small (5 or 10) and report HitRate@K alongside Recall@K.")
        print("    3) Fall back to artist-level labels in the coldest quintiles.")
    else:
        print("  Track-level ground truth is not viable. Grow the corpus first, or")
        print("  switch to artist-level labels plus human relevance judgements.")

    if zero_q1 > BLIND_SPOT_THRESHOLD:
        print(
            f"\n  Caveat: {zero_q1 * 100:.0f}% of Q1 seeds get no in-library positives at all.\n"
            "  Offline evaluation is not trustworthy in the coldest quintile and the\n"
            "  README must say so."
        )

    args.outdir.mkdir(parents=True, exist_ok=True)
    write_json(args.outdir / "gt_density.json", rows, indent=2)
    print(f"\n[done] -> {args.outdir / 'gt_density.json'}")


if __name__ == "__main__":
    main()
