"""Load the library, its labels and the benchmark's rankings into SQLite.

The database is derived, never authoritative: songs.json remains what every
pipeline stage reads and writes, and ``make db`` rebuilds this from it. What
the database adds is a second, independent way to compute the project's
numbers. ``sql/schema.sql`` defines each derived quantity once as a view, and
``scripts/sql_crosscheck.py`` compares what those views produce against the
reports the pandas pipeline published.

Two things are deliberately *not* moved into SQL, and the split is the point:

* **String normalization.** ``normalize.norm`` and ``normalize_tag`` apply
  Unicode folding and regexes SQLite has no equivalent for (its ``lower()``
  folds ASCII only). The loader stores their output next to the raw text.
* **Ranking.** Scores come from ``recommend.score`` exactly as the benchmark
  calls it. Whether a seed is evaluable, whether a policy can serve it, and
  every metric computed from the ranking are left to SQL.
"""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Iterable
from pathlib import Path

import numpy as np

from kpoprec.config import ROOT
from kpoprec.normalize import norm, normalize_tag, song_key
from kpoprec.pooling import evaluable_seeds
from kpoprec.recommend import (
    FEATURE_KEYS,
    POLICIES,
    Library,
    draw_rng,
    run_tiebreak,
    score,
    top_k,
)
from kpoprec.taxonomy import NON_DISCRIMINATIVE_TAGS

SQL_DIR = ROOT / "sql"
SCHEMA = SQL_DIR / "schema.sql"
DERIVE = SQL_DIR / "derive.sql"
CHECKS_DIR = SQL_DIR / "checks"

# Every field a song record may carry. Anything else is schema drift and must
# stop the load: a field that is silently dropped here would make the
# database quietly disagree with the JSON it claims to mirror.
SONG_FIELDS = {
    "title", "artist", "tags", "all_tags", "dur", "durStr", "url",
    "spotify_id", "features", "listeners", "playcount", "mbid", "year",
    "tag_source",
}
_SCALARS = ("url", "spotify_id", "mbid", "year", "listeners", "playcount", "tag_source")


def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open a connection with foreign keys enforced and math functions present.

    SQLite ships ``log2``/``log10``/``sqrt`` only when compiled with its math
    extension, which most Python builds are but not every Linux distribution's.
    Where they are missing, Python's own are registered under the same names so
    the SQL reads identically everywhere.
    """
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    for name, fn in (("log2", math.log2), ("log10", math.log10), ("sqrt", math.sqrt)):
        try:
            conn.execute(f"SELECT {name}(4)")
        except sqlite3.OperationalError:
            conn.create_function(name, 1, fn, deterministic=True)
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))


# ── Library ─────────────────────────────────────────────────────────────────

def load_library(conn: sqlite3.Connection, songs: list[dict]) -> None:
    """Insert every song, its tags, genres and features. ``track_id`` = index."""
    for i, s in enumerate(songs):
        extra = set(s) - SONG_FIELDS
        if extra:
            raise ValueError(
                f"song {i} ({s.get('artist')} - {s.get('title')}) has fields the "
                f"schema does not know: {sorted(extra)}. Add them to "
                f"sql/schema.sql and db.SONG_FIELDS rather than dropping them."
            )

    # The benchmark's same-artist test is name.strip().lower(); the schema's
    # identity is norm(name). They must agree on who is the same artist, or the
    # artist-blind numbers would be computed over a different grouping.
    by_norm: dict[str, set[str]] = {}
    for s in songs:
        by_norm.setdefault(norm(s["artist"]), set()).add(s["artist"].strip().lower())
    split = {k: v for k, v in by_norm.items() if len(v) > 1}
    if split:
        raise ValueError(f"artist identity differs between norm() and lower(): {split}")

    artist_ids: dict[str, int] = {}
    for s in songs:
        artist_ids.setdefault(norm(s["artist"]), len(artist_ids))
    conn.executemany(
        "INSERT INTO artists (artist_id, name_norm) VALUES (?, ?)",
        [(aid, name) for name, aid in artist_ids.items()],
    )

    conn.executemany(
        "INSERT INTO tracks (track_id, song_key, title, artist, artist_id, dur, "
        + ", ".join(_SCALARS) + ") VALUES (?, ?, ?, ?, ?, ?, "
        + ", ".join("?" * len(_SCALARS)) + ")",
        [
            (i, song_key(s), s["title"], s["artist"], artist_ids[norm(s["artist"])],
             s["dur"], *(s.get(c) for c in _SCALARS))
            for i, s in enumerate(songs)
        ],
    )
    conn.executemany(
        "INSERT INTO track_tags (track_id, ord, tag, tag_norm) VALUES (?, ?, ?, ?)",
        [
            (i, j, t, normalize_tag(t))
            for i, s in enumerate(songs)
            for j, t in enumerate(s.get("all_tags") or [])
        ],
    )
    conn.executemany(
        "INSERT INTO track_genres (track_id, ord, genre) VALUES (?, ?, ?)",
        [(i, j, g) for i, s in enumerate(songs) for j, g in enumerate(s.get("tags") or [])],
    )
    conn.executemany(
        "INSERT INTO non_discriminative_tags (tag) VALUES (?)",
        [(t,) for t in sorted(NON_DISCRIMINATIVE_TAGS)],
    )
    conn.executemany(
        "INSERT INTO audio_features (track_id, " + ", ".join(FEATURE_KEYS)
        + ") VALUES (?, " + ", ".join("?" * len(FEATURE_KEYS)) + ")",
        [
            (i, *(s["features"].get(k) for k in FEATURE_KEYS))
            for i, s in enumerate(songs)
            if s.get("features")
        ],
    )


def export_songs(conn: sqlite3.Connection) -> list[dict]:
    """Rebuild songs.json from the tables -- the proof the load lost nothing.

    Optional fields are emitted only when present, as the pipeline writes them,
    and ``durStr`` is re-derived from ``dur`` the way build_library does.
    """
    tags: dict[int, list[str]] = {}
    for r in conn.execute("SELECT track_id, tag FROM track_tags ORDER BY track_id, ord"):
        tags.setdefault(r["track_id"], []).append(r["tag"])
    genres: dict[int, list[str]] = {}
    for r in conn.execute("SELECT track_id, genre FROM track_genres ORDER BY track_id, ord"):
        genres.setdefault(r["track_id"], []).append(r["genre"])
    feats = {
        r["track_id"]: {k: r[k] for k in FEATURE_KEYS}
        for r in conn.execute("SELECT * FROM audio_features")
    }

    songs = []
    for r in conn.execute("SELECT * FROM tracks ORDER BY track_id"):
        i, dur = r["track_id"], r["dur"]
        s = {
            "title": r["title"],
            "artist": r["artist"],
            "tags": genres.get(i, []),
            "all_tags": tags.get(i, []),
            "dur": dur,
            "durStr": f"{dur // 60}:{dur % 60:02d}",
        }
        for c in _SCALARS:
            if r[c] is not None:
                s[c] = r[c]
        if i in feats:
            s["features"] = feats[i]
        songs.append(s)
    return songs


# ── Labels ──────────────────────────────────────────────────────────────────

def load_ground_truth(conn: sqlite3.Connection, gt: dict[str, list[str]]) -> None:
    """Store the labels as keys. Resolving them to tracks is the views' job."""
    conn.executemany("INSERT INTO gt_seeds (seed_key) VALUES (?)", [(k,) for k in gt])
    conn.executemany(
        "INSERT INTO ground_truth (seed_key, ord, positive_key) VALUES (?, ?, ?)",
        [(k, j, p) for k, pos in gt.items() for j, p in enumerate(pos)],
    )


# ── Rankings ────────────────────────────────────────────────────────────────

def rank_rows(
    songs: list[dict],
    gt: dict[str, list[str]],
    run_seed: int,
    repeats: int,
    depth: int,
) -> Iterable[tuple[str, int, int, int, int]]:
    """``(policy, seed, draw, rank, track)`` for every evaluable seed.

    The same calls evaluate.py makes -- one tie-break permutation per run, one
    generator per random draw -- so the rankings are the ones the published
    numbers were computed from. Every policy is ranked on every seed, servable
    or not; the ``served`` view decides which rankings count.

    Each list runs ``depth`` deep, and further where needed until it holds
    ``depth`` tracks outside the seed's own artist. Without that, the
    artist-blind variant could not be scored: the tag policy fills the top 50
    of a BTS seed almost entirely with BTS, and filtering them out leaves
    fewer than ten.
    """
    lib = Library(songs)
    tiebreak = run_tiebreak(run_seed, lib.n)
    for i in sorted(evaluable_seeds(gt, songs)):
        same = lib.same_artist(i)
        for policy in POLICIES:
            for d in range(repeats if policy == "random" else 1):
                scores = score(policy, lib, i, draw_rng(run_seed, d, i))
                ranked = top_k(scores, lib.n, tiebreak)
                outside = np.cumsum(~same[ranked])
                n = max(depth, int(np.searchsorted(outside, depth)) + 1)
                for r, j in enumerate(ranked[:n], 1):
                    yield policy, i, d, r, int(j)


def build(
    conn: sqlite3.Connection,
    songs: list[dict],
    gt: dict[str, list[str]],
    run_seed: int = 0,
    repeats: int = 20,
    depth: int = 50,
    ks: tuple[int, ...] = (5, 10, 20, 50),
    meta: dict[str, str] | None = None,
) -> None:
    """Create the schema and load everything. Defaults match ``make bench``."""
    if max(ks) > depth:
        raise ValueError(f"cannot score k={max(ks)} from rankings {depth} deep")
    create_schema(conn)
    load_library(conn, songs)
    load_ground_truth(conn, gt)
    conn.executemany("INSERT INTO policies (policy) VALUES (?)", [(p,) for p in POLICIES])
    conn.executemany("INSERT INTO ks (k) VALUES (?)", [(k,) for k in ks])
    conn.executemany(
        "INSERT INTO meta (key, value) VALUES (?, ?)",
        [(k, str(v)) for k, v in {
            "run_seed": run_seed, "random_repeats": repeats, "depth": depth,
            **(meta or {}),
        }.items()],
    )
    conn.executemany(
        "INSERT INTO rankings (policy, seed_id, draw, rank, track_id) VALUES (?, ?, ?, ?, ?)",
        rank_rows(songs, gt, run_seed, repeats, depth),
    )
    conn.executescript(DERIVE.read_text(encoding="utf-8"))
    conn.commit()


# ── Queries ─────────────────────────────────────────────────────────────────

def check(conn: sqlite3.Connection, name: str) -> list[sqlite3.Row]:
    """Run ``sql/checks/<name>.sql`` and return its rows."""
    return conn.execute((CHECKS_DIR / f"{name}.sql").read_text(encoding="utf-8")).fetchall()
