#!/usr/bin/env python3
"""Stage 8 - build the pooled annotation task for the cold end.

The benchmark in ``evaluate.py`` cannot say anything trustworthy about the
coldest two quintiles, because Last.fm's similar-track labels cover only 43%
and 64% of them. This script produces the input to the one remedy available:
human judgements, sampled where the labels are missing rather than where they
are plentiful.

Output
------
``--out``       the task. Title and artist only, candidates shuffled, one
                empty ``labels`` object per seed to fill in by hand.
``--key``       provenance: each policy's ranking, the seed's quintile and
                listener count, whether Last.fm labels exist for it. Read when
                scoring, never while judging.
``--sheet``     a markdown worksheet carrying the same information as the task
                and nothing more.

Score the finished labels with ``evaluate_ranking(..., judged=...)``, which
condenses each ranking to positions a human actually ruled on instead of
counting an unjudged candidate as a miss.

Usage
-----
    python3 scripts/build_pool.py                      # bundled sample
    python3 scripts/build_pool.py --songs data/songs.json \\
        --ground-truth data/ground_truth.json --n-seeds 40
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from kpoprec import config  # noqa: E402
from kpoprec.io import load_songs, write_json  # noqa: E402
from kpoprec.pooling import (  # noqa: E402
    build_pool,
    evaluable_seeds,
    select_seeds,
    sheet,
)
from kpoprec.recommend import QUINTILE_LABELS, Library  # noqa: E402


def parse_quintiles(spec: str) -> tuple[int, ...]:
    """``"Q1,Q2"`` or ``"1,2"`` -> ``(0, 1)``."""
    out = []
    for part in spec.split(","):
        part = part.strip().lstrip("Qq")
        if not part.isdigit() or not 1 <= int(part) <= len(QUINTILE_LABELS):
            sys.exit(f"[FATAL] not a quintile: {part!r} (use Q1..Q{len(QUINTILE_LABELS)})")
        out.append(int(part) - 1)
    if not out:
        sys.exit("[FATAL] --quintiles is empty")
    return tuple(dict.fromkeys(out))


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a pooled annotation task")
    ap.add_argument("--songs", type=Path, default=config.SONGS_SAMPLE_JSON)
    ap.add_argument("--ground-truth", type=Path,
                    default=config.DATA_DIR / "ground_truth.sample.json",
                    help="only recorded, never used to filter; absent is fine")
    ap.add_argument("--quintiles", default="Q1,Q2",
                    help="strata to sample from (default: the two the labels cannot reach)")
    ap.add_argument("--n-seeds", type=int, default=40)
    ap.add_argument("--depth", type=int, default=10,
                    help="pool each policy's top-N; also the largest K the result can score")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path,
                    default=config.DATA_DIR / "annotation_pool.sample.json")
    ap.add_argument("--key", type=Path,
                    default=config.DATA_DIR / "annotation_pool_key.sample.json")
    ap.add_argument("--sheet", type=Path,
                    default=config.REPORTS_DIR / "sample" / "annotation_pool.md")
    args = ap.parse_args()

    songs = load_songs(args.songs)
    lib = Library(songs)
    quintiles = parse_quintiles(args.quintiles)

    # "Has a ground-truth entry" is not "can be evaluated": most of a seed's
    # similar tracks are not in this library. Use the benchmark's own test.
    labelled = None
    if args.ground_truth.exists():
        labelled = set(evaluable_seeds(json.loads(args.ground_truth.read_text()), songs))
    print(f"[load] {len(songs)} tracks, "
          f"{len(labelled) if labelled is not None else 'no'} seeds the CF labels can score")

    rng = np.random.default_rng(args.seed)
    # The same fixed permutation the benchmark uses, so a candidate's rank here
    # is the rank it will have when the judgements are scored.
    tiebreak = rng.permutation(lib.n)

    seeds = select_seeds(lib, quintiles, args.n_seeds, rng)
    if len(seeds) < args.n_seeds:
        print(f"[warn] only {len(seeds)} seeds available in "
              f"{', '.join(QUINTILE_LABELS[q] for q in quintiles)}")

    task, key = build_pool(lib, songs, seeds, args.depth, rng, tiebreak,
                          run_seed=args.seed, labelled=labelled)

    write_json(args.out, task, indent=2)
    write_json(args.key, key, indent=2)
    args.sheet.parent.mkdir(parents=True, exist_ok=True)
    args.sheet.write_text("\n".join(sheet(task)) + "\n")

    m = task["meta"]
    served = sum(1 for s in key["seeds"] if set(s["served_by"]) - {"random", "popularity"})
    covered = sum(1 for s in key["seeds"] if s["has_cf_labels"])
    print(f"[pool] {m['n_seeds']} seeds from "
          f"{', '.join(QUINTILE_LABELS[q] for q in quintiles)} at depth {m['depth']}")
    print(f"[pool] {m['n_judgements']} judgements, "
          f"median {int(np.median([len(s['candidates']) for s in task['seeds']]))} per seed")
    print(f"[pool] {served}/{m['n_seeds']} seeds a content policy can rank; "
          f"{covered}/{m['n_seeds']} already have Last.fm labels")
    print(f"\n[done] -> {args.out}   (label this)")
    print(f"[done] -> {args.key}   (do not open while labelling)")
    print(f"[done] -> {args.sheet}")


if __name__ == "__main__":
    main()
