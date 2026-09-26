#!/usr/bin/env python3
"""Load the library, labels and benchmark rankings into a SQLite database.

The database is derived from songs.json and the ground-truth file, never the
other way round, so it can be deleted and rebuilt at any time. Schema and
views: ``sql/schema.sql``. What it is for: ``scripts/sql_crosscheck.py``.

Usage
-----
    python3 scripts/build_db.py                          # bundled sample
    python3 scripts/build_db.py --songs data/songs.json \\
        --ground-truth data/ground_truth.json --out data/kpoprec.db

Run seed, random draws and depth default to what ``make bench`` uses, so the
stored rankings are the ones the committed benchmark was computed from.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kpoprec import config, db  # noqa: E402
from kpoprec.io import load_songs  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the SQLite database")
    ap.add_argument("--songs", type=Path, default=config.SONGS_SAMPLE_JSON)
    ap.add_argument("--ground-truth", type=Path,
                    default=config.DATA_DIR / "ground_truth.sample.json")
    ap.add_argument("--out", type=Path, default=config.DATA_DIR / "kpoprec.sample.db")
    ap.add_argument("--seed", type=int, default=0, help="the benchmark's run seed")
    ap.add_argument("--random-repeats", type=int, default=20)
    ap.add_argument("--depth", type=int, default=50)
    args = ap.parse_args()

    if not args.ground_truth.exists():
        sys.exit(f"[FATAL] no ground truth at {args.ground_truth}")
    songs = load_songs(args.songs)
    gt = json.loads(args.ground_truth.read_text(encoding="utf-8"))

    # Build beside the target and swap in, so an interrupted build never
    # leaves a half-loaded database where a complete one used to be.
    tmp = args.out.with_suffix(args.out.suffix + ".tmp")
    tmp.unlink(missing_ok=True)
    t0 = time.time()
    conn = db.connect(tmp)
    db.build(
        conn, songs, gt,
        run_seed=args.seed, repeats=args.random_repeats, depth=args.depth,
        meta={"songs": args.songs.name, "ground_truth": args.ground_truth.name},
    )
    n_rank = conn.execute("SELECT COUNT(*) FROM rankings").fetchone()[0]
    conn.close()
    tmp.replace(args.out)

    print(f"[load] {len(songs)} tracks, {len(gt)} ground-truth seeds, "
          f"{n_rank:,} ranking rows ({time.time() - t0:.1f}s)")
    print(f"[done] -> {args.out}")


if __name__ == "__main__":
    main()
