#!/usr/bin/env python3
"""Stage 5 — build a pseudo ground truth, and diagnose what it is worth.

There are no user interaction logs for this project, so offline evaluation
needs relevance labels from somewhere. Last.fm's ``track.getSimilar`` provides
them: for each seed, the similar tracks that also exist in the local library
become positive samples.

What this actually measures
---------------------------
Last.fm similarity is itself collaborative-filtering output. So a model scored
against these labels is not being measured against user preference — it is
being measured on **how closely a content-based method reproduces an industrial
CF system**. That is a legitimate question, but it is a different one, and
stating it plainly is the difference between an honest evaluation and an
inflated one.

Three diagnostics run automatically, because each one can invalidate the
evaluation design:

  1. Same-artist contamination — if most positives share the seed's artist, a
     trivial "recommend the same artist" policy scores well and the benchmark
     degenerates into artist identification.
  2. Popularity bias — CF favours the head. A large skew means the popularity
     baseline is strong and must be reported alongside any content method.
  3. Per-quintile coverage — seeds with zero positives cannot be evaluated at
     all, which marks out the blind spots of the whole benchmark.

Two label sets are written; the no-same-artist variant is the recommended
primary benchmark.

Usage
-----
    export LASTFM_API_KEY=xxx
    python3 scripts/build_ground_truth.py
    python3 scripts/build_ground_truth.py --limit-songs 100   # quick check

Resumable: progress is cached in ``data/gt_cache.json``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kpoprec import config  # noqa: E402
from kpoprec.io import load_songs, read_json, write_json  # noqa: E402
from kpoprec.lastfm import RATE_LIMITED, LastFM  # noqa: E402
from kpoprec.normalize import key_of, norm  # noqa: E402

# Above this share of same-artist positives, the benchmark is measuring artist
# recognition rather than musical similarity.
CONTAMINATION_CRITICAL = 0.30
CONTAMINATION_WARN = 0.15
# A popularity skew beyond this makes the popularity baseline hard to beat.
POPULARITY_SKEW_WARN = 1.5


def diagnose(gt: dict, lib: dict, md: list) -> None:
    n_pos = [len(v) for v in gt.values()]
    covered = [k for k, v in gt.items() if v]
    random_precision = np.mean(n_pos) / len(lib) * 100

    md += [
        "# Ground-truth diagnostics\n",
        "> Last.fm `track.getSimilar` intersected with the local library.\n"
        "> **These labels come from collaborative filtering, not from observed "
        "user preference.**\n",
        "---\n",
        "## Density\n",
        f"- Seeds: **{len(gt)}**",
        f"- With at least one positive: **{len(covered)}** "
        f"({len(covered) / len(gt) * 100:.1f}%)",
        f"- Positives per seed: mean **{np.mean(n_pos):.1f}** / "
        f"median **{np.median(n_pos):.0f}** / p75 {np.percentile(n_pos, 75):.0f}",
        f"- Relative to library size, {random_precision:.1f}% of the corpus is "
        f"labelled relevant for an average seed\n"
        f"  -> **a random recommender's expected Precision@10 is ~{random_precision:.1f}%**. "
        f"Any method must clear this floor before it means anything.\n",
    ]

    # ── 1. Same-artist contamination ────────────────────────────────────────
    same = total = 0
    per_seed = []
    for k, pos in gt.items():
        if not pos:
            continue
        artist = lib[k]["_artist_n"]
        s = sum(1 for p in pos if lib[p]["_artist_n"] == artist)
        same += s
        total += len(pos)
        per_seed.append(s / len(pos))
    share = same / max(total, 1)

    md += [
        "## Diagnostic 1 — same-artist contamination\n",
        f"- Share of positives by the seed's own artist: **{share * 100:.1f}%** "
        f"({same}/{total})",
        f"- Median per-seed share: **{np.median(per_seed) * 100:.1f}%**\n",
    ]
    if share > CONTAMINATION_CRITICAL:
        md += [
            "> **Severe.** A trivial \"recommend more of the same artist\" policy "
            "would score highly, so the benchmark would be measuring artist "
            "recognition rather than musical similarity.\n"
            "> Use `ground_truth_no_same_artist.json` as the primary benchmark "
            "and report same-artist as an explicit baseline arm.\n"
        ]
    elif share > CONTAMINATION_WARN:
        md += ["> Some contamination. Report both label sets side by side.\n"]
    else:
        md += ["> Acceptable — same-artist positives are not driving the labels.\n"]
    print(f"[diag] same-artist share {share * 100:.1f}%")

    # ── 2. Popularity bias ──────────────────────────────────────────────────
    lib_listeners = [v["listeners"] for v in lib.values() if v.get("listeners")]
    pos_listeners = [
        lib[p]["listeners"] for pos in gt.values() for p in pos if lib[p].get("listeners")
    ]
    if lib_listeners and pos_listeners:
        ratio = np.median(pos_listeners) / max(np.median(lib_listeners), 1)
        md += [
            "## Diagnostic 2 — popularity bias\n",
            "| | median listeners |",
            "|---|---:|",
            f"| Whole library | {np.median(lib_listeners):,.0f} |",
            f"| Positive samples | {np.median(pos_listeners):,.0f} |",
            f"\nPositives are about **{ratio:.1f}x** as popular as the corpus median. "
            + (
                "The CF labels lean heavily toward the head, so a popularity "
                "baseline will be strong and must be reported. If a content-based "
                "method cannot beat it, that is the finding.\n"
                if ratio > POPULARITY_SKEW_WARN
                else "The skew is mild.\n"
            ),
        ]
        print(f"[diag] positives/library median listeners = {ratio:.2f}")

    # ── 3. Per-quintile evaluability ────────────────────────────────────────
    with_listeners = [(k, v) for k, v in lib.items() if v.get("listeners")]
    if len(with_listeners) > 100:
        with_listeners.sort(key=lambda kv: kv[1]["listeners"])
        md += [
            "## Diagnostic 3 — evaluation reliability by popularity quintile\n",
            "| Quintile | Seeds | With positives | Mean positives | Reliability |",
            "|---|---:|---:|---:|---|",
        ]
        for i, chunk in enumerate(
            np.array_split([k for k, _ in with_listeners], 5), 1
        ):
            ks = [k for k in chunk if k in gt]
            if not ks:
                continue
            cov = np.mean([bool(gt[k]) for k in ks])
            mean = np.mean([len(gt[k]) for k in ks])
            verdict = (
                "Reliable" if cov > 0.8
                else ("Treat with caution" if cov > 0.5 else "**Not reliable**")
            )
            md += [f"| Q{i} | {len(ks)} | {cov * 100:.0f}% | {mean:.1f} | {verdict} |"]
        md += [
            "\n> Quintiles with low coverage are blind spots of the offline "
            "benchmark and must be labelled as such wherever results are "
            "reported. Closing them requires human relevance judgements, not "
            "more CF labels.\n"
        ]


def main() -> None:
    ap = argparse.ArgumentParser(description="Build pseudo ground truth from Last.fm")
    ap.add_argument("--songs", type=Path, default=config.SONGS_JSON)
    ap.add_argument("--cache", type=Path, default=config.GT_CACHE)
    ap.add_argument("--outdir", type=Path, default=config.REPORTS_DIR)
    ap.add_argument("--limit", type=int, default=100, help="similar tracks per seed")
    ap.add_argument("--limit-songs", type=int, default=0, help="only first N seeds (debug)")
    args = ap.parse_args()

    songs = load_songs(args.songs)
    if args.limit_songs:
        songs = songs[: args.limit_songs]

    lib = {
        key_of(s["artist"], s["title"]): {**s, "_artist_n": norm(s["artist"])}
        for s in songs
    }
    print(f"[index] {len(songs)} tracks -> {len(lib)} unique keys")

    cache: dict = read_json(args.cache, default={}) or {}
    todo = [s for s in songs if key_of(s["artist"], s["title"]) not in cache]
    print(
        f"[fetch] {len(todo)} to process, {len(songs) - len(todo)} cached "
        f"(~{len(todo) * config.LASTFM_DELAY / 60:.1f} min)"
    )

    if todo:
        client = LastFM(config.lastfm_key())
        for i, s in enumerate(todo, 1):
            res = client.similar_tracks(s["artist"], s["title"], args.limit)
            if res is RATE_LIMITED:
                write_json(args.cache, cache)
                print("  ! rate limit — progress saved, re-run later")
                break
            if res is None:
                continue  # transport error: do not cache
            cache[key_of(s["artist"], s["title"])] = res
            if i % 100 == 0:
                write_json(args.cache, cache)
                print(f"  [{i}/{len(todo)}]")
            client.sleep()
        write_json(args.cache, cache)

    # ── Intersect against the library ───────────────────────────────────────
    gt: dict[str, list[str]] = {}
    gt_nsa: dict[str, list[str]] = {}
    for s in songs:
        k = key_of(s["artist"], s["title"])
        positives = []
        for t in cache.get(k, []):
            pk = key_of(t["artist"], t["title"])
            if pk in lib and pk != k:
                positives.append(pk)
        gt[k] = list(dict.fromkeys(positives))
        gt_nsa[k] = [p for p in gt[k] if lib[p]["_artist_n"] != lib[k]["_artist_n"]]

    write_json(config.GROUND_TRUTH_JSON, gt, indent=1)
    write_json(config.GROUND_TRUTH_NSA_JSON, gt_nsa, indent=1)

    md: list[str] = []
    diagnose(gt, lib, md)
    n_cov = sum(1 for v in gt_nsa.values() if v)
    md += [
        "\n---\n## Density after removing same-artist positives\n",
        f"- With at least one positive: {n_cov}/{len(gt_nsa)} "
        f"({n_cov / len(gt_nsa) * 100:.1f}%)",
        f"- Positives per seed: mean {np.mean([len(v) for v in gt_nsa.values()]):.1f} "
        f"/ median {np.median([len(v) for v in gt_nsa.values()]):.0f}\n",
    ]

    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "gt_diagnostics.md").write_text("\n".join(md), encoding="utf-8")

    print(f"\n[done] -> {config.GROUND_TRUTH_JSON}")
    print(f"[done] -> {config.GROUND_TRUTH_NSA_JSON}")
    print(f"[done] -> {args.outdir / 'gt_diagnostics.md'}")


if __name__ == "__main__":
    main()
