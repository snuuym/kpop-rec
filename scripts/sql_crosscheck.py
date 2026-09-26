#!/usr/bin/env python3
"""Recompute every published number in SQL and compare it with the report.

The reports in ``reports/`` and the numbers in the README were produced by
pandas and numpy. This recomputes each of them from the SQLite database --
the queries in ``sql/checks/``, over the views in ``sql/schema.sql``, with no
pandas or numpy involved -- and compares the two.

Agreement is judged against what was actually printed: a number shown as
72.7% matches if the SQL value rounds to it, i.e. lies within half a unit of
the last digit shown. The benchmark CSVs carry full precision and are held to
1e-9.

A report that cannot be found is skipped and says so; a number that cannot be
found *inside* a report that exists is a failure, because a check that quietly
stops matching anything is no check at all. Any failure exits non-zero.

Usage
-----
    python3 scripts/sql_crosscheck.py                    # the sample
    python3 scripts/sql_crosscheck.py --db data/kpoprec.db --reports reports \\
        --readme README.md
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kpoprec import config, db  # noqa: E402
from kpoprec.recommend import POLICIES, QUINTILE_LABELS  # noqa: E402

EXACT = 1e-9
NOT_FOUND = "(not in report)"


@dataclass
class Row:
    label: str
    published: str
    sql: str
    ok: bool | None  # None: nothing published to compare against


def _decimals(s: str) -> int:
    return len(s.split(".")[1]) if "." in s else 0


def printed(label: str, published: str | None, sql: float, scale: float = 1.0,
            source: bool = True) -> Row:
    """Compare ``sql * scale`` with a number as the report printed it."""
    v = float(sql) * scale
    if not source:
        return Row(label, "—", f"{v:,.3f}".rstrip("0").rstrip("."), None)
    if published is None:
        return Row(label, NOT_FOUND, f"{v:,.3f}", False)
    # A number at the end of a sentence is captured with its full stop.
    published = published.rstrip(".")
    dec = _decimals(published)
    ok = abs(v - float(published.replace(",", ""))) <= 0.5 * 10 ** -dec + 1e-9
    sep = "," if "," in published else ""
    return Row(label, published, f"{v:{sep}.{dec if ok else dec + 2}f}", ok)


def grab(text: str | None, pattern: str, group: int = 1) -> str | None:
    if text is None:
        return None
    m = re.search(pattern, text, re.MULTILINE)
    return m.group(group) if m else None


def one(conn: sqlite3.Connection, name: str) -> sqlite3.Row:
    return db.check(conn, name)[0]


def read(path: Path | None) -> str | None:
    return path.read_text(encoding="utf-8") if path and path.exists() else None


# ── Tag sparsity ────────────────────────────────────────────────────────────

def section(md: str | None, marker: str, expected: bool, name: str, make) -> list[Row]:
    """Rows for a report section that exists only when there is enough data.

    ``expected`` says whether the data is enough. With no report to read, the
    rows are shown unchecked; otherwise a mismatch between "should be there" and
    "is there" is a failure in either direction.
    """
    if md is None:
        return make() if expected else []
    present = marker in md
    if expected and not present:
        return [Row(name, NOT_FOUND, "the data supports it", False)]
    if present and not expected:
        return [Row(name, "published", "too little data in the database", False)]
    return make() if expected else []


def sparsity(conn: sqlite3.Connection, md: str | None) -> list[Row]:
    has = md is not None
    i, s = one(conn, "integrity"), one(conn, "tag_signal")
    vocab = db.check(conn, "tag_vocabulary")
    bias, reg = db.check(conn, "selection_bias"), db.check(conn, "novelty_vs_obscurity")
    b, r = (bias[0] if bias else None), reg[0]
    fb = {x["bucket"]: x for x in db.check(conn, "fallback_coverage")}
    q = db.check(conn, "coverage_by_quintile")

    def p(label, pattern, sql, scale=1.0, group=1):
        return printed(label, grab(md, pattern, group), sql, scale, has)

    rows = [
        p("Verified untagged (backfill asked, nobody tagged)",
          r"Verified: nobody has tagged it \| (\d+)", i["verified_untagged"]),
        p("Unverified empty tag lists", r"Unverified empty `all_tags` \| (\d+)", i["unverified"]),
        p("Tagged with root tags only", r"only with root tags \| (\d+)", i["root_only"]),
        p("Has an effective tag", r"Has effective tags \| (\d+)", i["has_effective"]),
        p("Corpus size", r"Corpus size: \*\*(\d+)\*\*", s["n_tracks"]),
        p("Mean raw tags per track", r"Raw tags average ([\d.]+)", s["mean_raw"]),
        p("Mean effective tags per track", r"effective tags average only ([\d.]+)", s["mean_eff"]),
        p("Median effective tags", r"\(median (\d+)\)", s["median_eff"]),
        p("Tracks with no effective tag", r"\*\*(\d+) tracks \([\d.]+%\) have no effective", s["zero_eff"]),
        p("... as a share (%)", r"\*\*\d+ tracks \(([\d.]+)%\) have no effective", s["zero_eff_share"], 100),
        p("Tracks with 2 or fewer (%)", r"\d+ tracks \(([\d.]+)%\) have 2 or fewer", s["thin_share"], 100),
        p("Carrying a sub-genre label (%)", r"sub-genre label: \d+ \(([\d.]+)%\)", s["classified_share"], 100),
        p("Unique tags", r"Unique tags: \*\*(\d+)\*\*", vocab[0]["n_unique"] if vocab else 0),
        p("Tags on exactly one track", r"exactly one track: \*\*(\d+)\*\*", vocab[0]["n_singleton"] if vocab else 0),
    ]
    # The analysis skips these two sections when a sample is too small (fewer
    # than 30 tracks in either tagging group; fewer than 100 for the
    # regression). Mirror that from the data, in both directions: a section the
    # data supports but the report lacks is stale, and one the report has but
    # the data cannot support has no business being there.
    rows += section(md, "### Selection-bias check",
                    b is not None and b["first_pass_n"] >= 30 and b["backfill_n"] >= 30,
                    "selection-bias check", lambda: [
        p("First pass: tracks", r"Tagged in the first pass \| (\d+)", b["first_pass_n"]),
        p("First pass: median listeners", r"Tagged in the first pass \| \d+ \| ([\d,]+)", b["first_pass_median"]),
        p("Backfill: tracks", r"Filled in by backfill \| (\d+)", b["backfill_n"]),
        p("Backfill: median listeners", r"Filled in by backfill \| \d+ \| ([\d,]+)", b["backfill_median"]),
        p("First pass / backfill popularity (x)", r"about \*\*([\d.]+)x\*\* as popular", b["ratio"]),
    ])
    rows += section(md, "Model R^2 = ", r["n_tracks"] >= 100, "novelty-vs-obscurity regression", lambda: [
        p("Regression sample", r"Sample: (\d+) tracks with both fields", r["n_tracks"]),
        p("Year: univariate r", r"Release year \| ([+-][\d.]+)", r["r_year"]),
        p("Year: partial beta", r"Release year \| [+-][\d.]+ \| \*\*([+-][\d.]+)", r["beta_year"]),
        p("log10(listeners): univariate r", r"log10\(listeners\) \| ([+-][\d.]+)", r["r_pop"]),
        p("log10(listeners): partial beta", r"log10\(listeners\) \| [+-][\d.]+ \| \*\*([+-][\d.]+)", r["beta_pop"]),
        p("Model R^2", r"Model R\^2 = ([\d.]+)", r["r2"]),
    ])
    for bucket in ("no tags", "has tags"):
        x = fb[bucket]
        pat = rf"\| {bucket} \| (\d+) \| (\d+) \| (\d+) \| ([\d.]+)% \|"
        rows += [
            p(f"{bucket}: no audio features", pat, x["no_feature"], group=1),
            p(f"{bucket}: has audio features", pat, x["has_feature"], group=2),
            p(f"{bucket}: feature coverage (%)", pat, x["feature_coverage"], 100, group=4),
        ]
    rows += [
        p("Unreachable by any content signal", r"Unreachable tracks: (\d+)", fb["no tags"]["no_feature"]),
        p("... as a share (%)", r"Unreachable tracks: \d+ \(([\d.]+)%\)",
          fb["no tags"]["no_feature"] / fb["no tags"]["n_tracks"], 100),
        p("Overall audio-feature coverage (%)", r"Overall audio-feature coverage: ([\d.]+)%",
          fb["no tags"]["overall_feature_coverage"], 100),
    ]
    for x in q:
        label = QUINTILE_LABELS[x["quintile"]]
        pat = rf"\| {label} \| (\d+)% \| (\d+)% \|"
        rows += [
            p(f"{label}: tag coverage (%)", pat, x["tag_coverage"], 100, group=1),
            p(f"{label}: audio-feature coverage (%)", pat, x["feature_coverage"], 100, group=2),
        ]
    rows += [
        p("Tag coverage spread (pp)", r"varies by \*\*(\d+) percentage points", q[0]["tag_spread"], 100),
        p("Feature coverage spread (pp)", r"varies by only \*\*(\d+) points", q[0]["feature_spread"], 100),
    ]
    return rows + sparsity_by_source(conn, md)


def vocabulary(conn: sqlite3.Connection, path: Path) -> list[Row]:
    """The whole CSV, row for row: both sides rank by frequency, then by name."""
    sql = [(r["tag"], r["doc_freq"]) for r in db.check(conn, "tag_vocabulary")]
    label = "Every tag's document frequency, in rank order"
    if not path.exists():
        return [Row(label, "—", f"{len(sql)} tags", None)]
    pub = list(pd.read_csv(path, keep_default_na=False, dtype={"tag": str})
               .itertuples(index=False, name=None))
    differ = sum(a != b for a, b in zip(pub, sql)) + abs(len(pub) - len(sql))
    return [Row(label, f"{len(pub)} tags", f"{len(sql)} tags, {differ} differ", differ == 0)]


# ── By source ───────────────────────────────────────────────────────────────

def cells(text: str | None, first: str) -> list[str] | None:
    """The cells after the first, of the table row that starts with ``first``."""
    if text is None:
        return None
    m = re.search(rf"^\| {re.escape(first)} \|(.*)\|\s*$", text, re.MULTILINE)
    return [c.strip() for c in m.group(1).split("|")] if m else None


def cell(label: str, row: list[str] | None, i: int, sql: float | None, scale: float = 1.0,
         has: bool = True) -> Row:
    """One cell of a published row against SQL. ``n/a`` is published where a
    group has no tracks, and SQL has no value there either."""
    if not has:
        return Row(label, "—", "" if sql is None else f"{sql * scale:,.3f}".rstrip("0").rstrip("."), None)
    if row is None or i >= len(row):
        return Row(label, NOT_FOUND, "" if sql is None else f"{sql * scale:.3f}", False)
    text = row[i].strip("*").rstrip("%")
    if text == "n/a" or sql is None:
        return Row(label, row[i], "n/a" if sql is None else f"{sql * scale:.3f}", text == "n/a" and sql is None)
    return printed(label, text, sql, scale)


def _missing_section(name: str, md: str | None, heading: str, sources: int) -> list[Row] | None:
    """Rows when the by-source section cannot be checked, or ``None`` to go on.

    A database with several sources and a report without the section means the
    report is stale, which is a failure -- not a check that quietly finds
    nothing to do.
    """
    if sources < 2:
        return []
    if md is None:
        return [Row(f"{name}: by-source section", "—", f"{sources} sources", None)]
    if heading not in md:
        return [Row(f"{name}: by-source section", NOT_FOUND, f"{sources} sources in the database", False)]
    return None


def sparsity_by_source(conn: sqlite3.Connection, md: str | None) -> list[Row]:
    summary = {r["source"]: r for r in db.check(conn, "source_summary")}
    early = _missing_section("tag sparsity", md, "## Q4 - Do the two ways of sampling agree?", len(summary))
    if early is not None:
        return early
    sources = sorted(summary)
    has = md is not None
    rows: list[Row] = []

    # Rows of the three tables share first cells (`lastfm_tag`, `Q1 coldest`),
    # so each is looked for only inside its own part of the section.
    part = md[md.index("## Q4 - Do the two ways of sampling agree?"):] if has else ""
    split = ["The central table again, by source", "The novelty-vs-obscurity regression, pooled"]
    summary_txt, rest = (part.split(split[0], 1) + [""])[:2]
    quintile_txt, regression_txt = (rest.split(split[1], 1) + [""])[:2]

    for src in sources:
        x, c = summary[src], cells(summary_txt, src) if has else None
        rows += [
            cell(f"{src}: tracks", c, 0, x["tracks"], has=has),
            cell(f"{src}: no effective tag (%)", c, 1, x["no_tag"], 100, has),
            cell(f"{src}: audio-feature coverage (%)", c, 2, x["audio_coverage"], 100, has),
            cell(f"{src}: listener count known (%)", c, 3, x["listeners_known"], 100, has),
            cell(f"{src}: median listeners", c, 4, x["median_listeners"], 1, has),
            cell(f"{src}: year resolved (%)", c, 5, x["year_resolved"], 100, has),
            cell(f"{src}: median year", c, 6, x["median_year"], 1, has),
        ]

    by_q = {(r["quintile"], r["source"]): r for r in db.check(conn, "source_coverage_by_quintile")}
    for qi, label in enumerate(QUINTILE_LABELS):
        c = cells(quintile_txt, label) if has else None
        for j, src in enumerate(sources):
            x = by_q.get((qi, src))
            rows += [
                cell(f"{label}, {src}: tracks", c, 3 * j, x["tracks"] if x else 0, has=has),
                cell(f"{label}, {src}: tag coverage (%)", c, 3 * j + 1,
                     x["tag_coverage"] if x else None, 100, has),
                cell(f"{label}, {src}: audio coverage (%)", c, 3 * j + 2,
                     x["audio_coverage"] if x else None, 100, has),
            ]

    for r in db.check(conn, "novelty_vs_obscurity_by_source"):
        c = cells(regression_txt, r["sample"]) if has else None
        rows += [
            cell(f"regression, {r['sample']}: tracks", c, 0, r["n_tracks"], has=has),
            cell(f"regression, {r['sample']}: year (partial)", c, 1, r["beta_year"], 1, has),
            cell(f"regression, {r['sample']}: log10(listeners) (partial)", c, 2, r["beta_pop"], 1, has),
            cell(f"regression, {r['sample']}: R^2", c, 3, r["r2"], 1, has),
        ]
    return rows


def benchmark_by_source(conn: sqlite3.Connection, md: str | None) -> list[Row]:
    sql = {(r["policy"], r["source"]): r for r in db.check(conn, "benchmark_by_source")}
    sources = sorted({s for _, s in sql})
    early = _missing_section("eval_summary", md, "## By source of the seed", len(sources))
    if early is not None:
        return early
    section = md[md.index("## By source of the seed"):]
    n_seeds = {(src): v["n_seeds"] for (pol, src), v in sql.items() if pol == POLICIES[0]}
    rows: list[Row] = []
    # Both tables carry the same header, `source (n=...)`; the first is enough.
    for src, n in re.findall(r"(\S+) \(n=(\d+)\)", section)[:len(sources)]:
        rows.append(printed(f"{src}: seeds", n, n_seeds.get(src, 0)))
    for policy in POLICIES:
        lines = re.findall(rf"^\| `{policy}` \|(.*)\|\s*$", section, re.MULTILINE)
        for kind, line in zip(("NDCG@10", "can rank (%)"), lines):
            parts = [x.strip() for x in line.split("|")]
            for j, src in enumerate(sources):
                v = sql[(policy, src)]
                sql_v, scale = (v["ndcg"], 1) if kind == "NDCG@10" else (v["served"], 100)
                rows.append(cell(f"`{policy}`, {src}: {kind}", parts, j, sql_v, scale))
    return rows


# ── Ground truth ────────────────────────────────────────────────────────────

def ground_truth(conn: sqlite3.Connection, md: str | None) -> list[Row]:
    has = md is not None
    d = {r["labels"]: r for r in db.check(conn, "gt_density")}
    sa, pb = one(conn, "gt_same_artist"), one(conn, "gt_popularity_bias")

    def p(label, pattern, sql, scale=1.0, group=1):
        return printed(label, grab(md, pattern, group), sql, scale, has)

    a, n = d["all"], d["nsa"]
    rows = [
        p("Seeds in the label file", r"Seeds: \*\*(\d+)\*\*", a["n_seeds"]),
        p("Seeds with a positive", r"With at least one positive: \*\*(\d+)\*\*", a["with_positive"]),
        p("... as a share (%)", r"one positive: \*\*\d+\*\* \(([\d.]+)%\)", a["with_positive_share"], 100),
        p("Positives per seed: mean", r"Positives per seed: mean \*\*([\d.]+)\*\*", a["mean_positives"]),
        p("Positives per seed: median", r"/ median \*\*(\d+)\*\*", a["median_positives"]),
        p("Positives per seed: p75", r"/ p75 (\d+)", a["p75_positives"]),
        p("Random Precision@10 floor (%)", r"Precision@10 is ~([\d.]+)%", a["random_precision"], 100),
        p("Same-artist share of positives (%)", r"own artist: \*\*([\d.]+)%\*\*", sa["share"], 100),
        p("Same-artist positives", r"own artist: \*\*[\d.]+%\*\* \((\d+)/", sa["same_artist"]),
        p("All positives", r"own artist: \*\*[\d.]+%\*\* \(\d+/(\d+)\)", sa["positives"]),
        p("Median per-seed same-artist share (%)", r"Median per-seed share: \*\*([\d.]+)%", sa["median_seed_share"], 100),
        p("Median listeners, library", r"Whole library \| ([\d,]+)", pb["library_median"]),
        p("Median listeners, positives", r"Positive samples \| ([\d,]+)", pb["positives_median"]),
        p("Positives / library popularity (x)", r"about \*\*([\d.]+)x\*\* as popular", pb["ratio"]),
    ]
    for x in db.check(conn, "gt_label_coverage"):
        q = x["quintile"] + 1
        pat = rf"\| Q{q} \| (\d+) \| (\d+)% \| ([\d.]+) \|"
        rows += [
            p(f"Q{q}: tracks", pat, x["n_tracks"], group=1),
            p(f"Q{q}: share with a positive (%)", pat, x["with_positives"], 100, group=2),
            p(f"Q{q}: mean positives", pat, x["mean_positives"], group=3),
        ]
    rows += [
        p("No same-artist labels: seeds with a positive", r"With at least one positive: (\d+)/", n["with_positive"]),
        p("No same-artist labels: mean positives", r"Positives per seed: mean ([\d.]+) /", n["mean_positives"]),
        p("No same-artist labels: median positives", r"Positives per seed: mean [\d.]+ / median (\d+)", n["median_positives"]),
    ]
    return rows


# ── Benchmark ───────────────────────────────────────────────────────────────

def _bulk(label: str, path: Path, pub_keyed: pd.DataFrame | None, sql: pd.DataFrame,
          keys: list[str], decimals: int | None = None) -> Row:
    """Every value of a CSV against the same cells computed in SQL.

    A CSV written at full precision is held to ``EXACT``. One written rounded
    is compared after rounding the SQL side the same way, and must then agree
    exactly.
    """
    if pub_keyed is None:
        return Row(label, "—", f"{sql.shape[0]} rows", None)
    m = pub_keyed.merge(sql, on=keys, how="outer", suffixes=("_pub", "_sql"), indicator=True)
    if (m["_merge"] != "both").any():
        return Row(label, f"{len(pub_keyed)} rows", "rows do not line up", False)
    cols = [c for c in pub_keyed.columns if c not in keys]
    if decimals is not None:
        m[[f"{c}_sql" for c in cols]] = m[[f"{c}_sql" for c in cols]].round(decimals)
    # A value one side has and the other lacks is a mismatch, not a skipped cell.
    if any((m[f"{c}_pub"].isna() != m[f"{c}_sql"].isna()).any() for c in cols):
        return Row(label, f"{len(pub_keyed)} rows", "missing values differ", False)
    diff = max(float((m[f"{c}_pub"] - m[f"{c}_sql"]).abs().max()) for c in cols)
    n = len(m) * len(cols)
    shown = f"max \\|Δ\\| = {diff:.1e}" if decimals is None else f"{decimals} places, max \\|Δ\\| = {diff:g}"
    return Row(label, f"{n} values", shown, diff <= (EXACT if decimals is None else 0))


def benchmark_csvs(conn: sqlite3.Connection, reports: Path) -> list[Row]:
    by_k_path, by_q_path = reports / "eval_by_k.csv", reports / "eval_by_quintile.csv"
    by_k = pd.DataFrame([dict(r) for r in db.check(conn, "benchmark_by_k")])
    pub_k = pd.read_csv(by_k_path) if by_k_path.exists() else None

    by_q = pd.DataFrame([dict(r) for r in db.check(conn, "benchmark_by_quintile")])
    by_q["quintile"] = [QUINTILE_LABELS[q] for q in by_q["quintile"]]
    by_q = by_q.rename(columns={m: f"{m}@10" for m in ("recall", "precision", "hit_rate", "ndcg")})
    pub_q = pd.read_csv(by_q_path) if by_q_path.exists() else None
    return [
        _bulk("`eval_by_k.csv`: every policy, every k, every metric",
              by_k_path, pub_k, by_k, ["k", "policy"]),
        _bulk("`eval_by_quintile.csv`: every policy, every quintile",
              by_q_path, pub_q, by_q, ["policy", "quintile"], decimals=4),
    ]


def benchmark_md(conn: sqlite3.Connection, md: str | None) -> list[Row]:
    has = md is not None
    proto = one(conn, "benchmark_protocol")
    blind = {r["policy"]: r for r in db.check(conn, "artist_blind")}
    by_k = {(r["k"], r["policy"]): r for r in db.check(conn, "benchmark_by_k")}
    cov = {r["quintile"]: r for r in db.check(conn, "gt_label_coverage")}

    def p(label, pattern, sql, scale=1.0, group=1):
        return printed(label, grab(md, pattern, group), sql, scale, has)

    rows = [
        p("Seeds evaluated", r"Seeds evaluated: \*\*(\d+)\*\*", proto["n_seeds"]),
        p("Candidate pool", r"the whole library, (\d+) tracks", proto["n_library"]),
        p("Positives per seed: median", r"Positives per seed: median \*\*(\d+)\*\*", proto["median_positives"]),
        p("Random Precision@10 floor", r"Precision@10 floor: \*\*([\d.]+)\*\*", by_k[(10, "random")]["precision_all"]),
        p("Same-artist share of labels (%)", r"only ([\d.]+)% of the labels", one(conn, "gt_same_artist")["share"], 100),
    ]
    for policy in POLICIES:
        x = blind[policy]
        pat = rf"\| `{policy}` \| ([\d.]+)% \| ([\d.]+) \| ([\d.]+) \|"
        rows += [
            p(f"`{policy}`: same-artist share of top-10 (%)", pat, x["same_artist_share"], 100, group=1),
            p(f"`{policy}`: NDCG@10 artist-blind", pat, x["ndcg_blind"], group=3),
        ]
    rows += [
        p("`tags`: same-artist share, in the prose (%)", r"\*\*(\d+)%\*\* of its", blind["tags"]["same_artist_share"], 100),
        p("Q1 seeds with a label (%)", r"reaches (\d+)% of Q1", cov[0]["with_positives"], 100),
        p("Q2 seeds with a label (%)", r"of Q1 and (\d+)% of Q2", cov[1]["with_positives"], 100),
    ]
    return rows + benchmark_by_source(conn, md)


# ── README ──────────────────────────────────────────────────────────────────

def readme_samples(conn: sqlite3.Connection, md: str) -> list[Row]:
    """What the README says about the two samples, and the numbers it quotes in
    the limitations and the summary table -- each against its own SQL value."""
    def p(label, pattern, sql, scale=1.0, group=1):
        return printed(label, grab(md, pattern, group), sql, scale)

    summary = {r["source"]: r for r in db.check(conn, "source_summary")}
    lf, pl = summary["lastfm_tag"], summary["spotify_playlist"]
    n_all = lf["tracks"] + pl["tracks"]
    sig, integ = one(conn, "tag_signal"), one(conn, "integrity")
    reg = {r["sample"]: r for r in db.check(conn, "novelty_vs_obscurity_by_source")}
    by_q = {(r["quintile"], r["source"]): r for r in db.check(conn, "source_coverage_by_quintile")}
    yc, fy = one(conn, "year_coverage"), {r["released"]: r for r in db.check(conn, "feature_coverage_by_release_year")}
    bs = {(r["policy"], r["source"]): r for r in db.check(conn, "benchmark_by_source")}
    by_k = {(x["k"], x["policy"]): x for x in db.check(conn, "benchmark_by_k")}
    by_q_all = {(x["policy"], x["quintile"]): x for x in db.check(conn, "benchmark_by_quintile")}
    cov = db.check(conn, "gt_label_coverage")
    floor = one(conn, "random_floor_spread")
    blind = {x["policy"]: x for x in db.check(conn, "artist_blind")}
    fb = {x["bucket"]: x for x in db.check(conn, "fallback_coverage")}
    r_all = reg["all"]

    two = md[md.index("## Two samples, one library"):md.index("## Judging the cold end")]

    rows = [
        p("Library size", r"\*\*Data\.\*\* ([\d,]+) K-pop tracks", n_all),
        p("Last.fm tracks", r"— ([\d,]+) pulled from Last\.fm's", lf["tracks"]),
        p("Playlist tracks", r"and\s+([\d,]+) from the owner's own Spotify", pl["tracks"]),
        p("Pseudo-relevance labels", r"plus\s+([\d,]+)\s+pseudo-relevance labels", one(conn, "gt_same_artist")["positives"]),
        p("Untagged, queried individually", r"\(([\d,]+) of the\s+[\d,]+ were queried", integ["verified_untagged"]),
        p("Untagged, in all", r"\([\d,]+ of the\s+([\d,]+) were queried", sig["zero_eff"]),
    ]

    # the two-samples table
    for label, key, scale in (("Tracks", "tracks", 1), ("Median release year", "median_year", 1),
                              ("Median listeners", "median_listeners", 1),
                              ("No effective tag", "no_tag", 100), ("Audio features", "audio_coverage", 100)):
        c = cells(two, label)
        rows += [cell(f"{label}, Last.fm", c, 0, lf[key], scale), cell(f"{label}, playlists", c, 1, pl[key], scale)]

    for qi, label in enumerate(("Q1 (coldest)", "Q2", "Q3", "Q4", "Q5 (hottest)")):
        c = cells(two, label)
        a, b = by_q[(qi, "lastfm_tag")], by_q[(qi, "spotify_playlist")]
        rows += [
            cell(f"{label}: tag coverage, Last.fm (%)", c, 0, a["tag_coverage"], 100),
            cell(f"{label}: tag coverage, playlists (%)", c, 1, b["tag_coverage"], 100),
            cell(f"{label}: audio coverage, Last.fm (%)", c, 2, a["audio_coverage"], 100),
            cell(f"{label}: audio coverage, playlists (%)", c, 3, b["audio_coverage"], 100),
        ]

    for label, key in (("Last.fm tag pages", "lastfm_tag"), ("Owner's playlists", "spotify_playlist"), ("Pooled", "all")):
        c, r_ = cells(two, label), reg[key]
        rows += [
            cell(f"regression, {label}: tracks", c, 0, r_["n_tracks"]),
            cell(f"regression, {label}: year (partial)", c, 1, r_["beta_year"]),
            cell(f"regression, {label}: log10(listeners) (partial)", c, 2, r_["beta_pop"]),
        ]

    rows += [
        p("Features, released 2024 or earlier (%)", r"features for (\d+)% of the [\d,]+\s+tracks released in 2024", fy["<=2024"]["feature_coverage"], 100),
        p("... tracks", r"features for \d+% of the ([\d,]+)\s+tracks released in 2024", fy["<=2024"]["tracks"]),
        p("Features, released 2025 (%)", r"or earlier, (\d+)% of the \d+ released in 2025", fy["2025"]["feature_coverage"], 100),
        p("... tracks", r"or earlier, \d+% of the (\d+) released in 2025", fy["2025"]["tracks"]),
        p("Features, released 2026 (%)", r"2025 and (\d+)% of\s+the \d+ released in 2026", fy["2026"]["feature_coverage"], 100),
        p("... tracks", r"2025 and \d+% of\s+the (\d+) released in 2026", fy["2026"]["tracks"]),
        p("Unreachable, Last.fm (%)", r"can reach is ([\d.]+)% in\s+the Last\.fm sample", lf["unreachable"], 100),
        p("Unreachable, playlists (%)", r"sample, ([\d.]+)% in the playlists, and", pl["unreachable"], 100),
        p("Unreachable, pooled (%)", r"and ([\d.]+)% pooled", fb["no tags"]["no_feature"] / n_all, 100),
    ]

    # benchmark by source
    header = re.search(r"Last\.fm seeds \(n=(\d+)\) \| Playlist seeds \(n=(\d+)\)", two)
    rows += [
        printed("Seeds, Last.fm", header.group(1) if header else None, bs[("random", "lastfm_tag")]["n_seeds"]),
        printed("Seeds, playlists", header.group(2) if header else None, bs[("random", "spotify_playlist")]["n_seeds"]),
    ]
    for policy in POLICIES:
        c = cells(two, f"`{policy}`")
        rows += [cell(f"`{policy}`, Last.fm seeds: NDCG@10", c, 0, bs[(policy, "lastfm_tag")]["ndcg"]),
                 cell(f"`{policy}`, playlist seeds: NDCG@10", c, 1, bs[(policy, "spotify_playlist")]["ndcg"])]
    rows += [
        p("Last.fm seeds, tags", r"On Last\.fm seeds tag overlap does beat popularity at K=10, ([\d.]+) against", bs[("tags", "lastfm_tag")]["ndcg"]),
        p("Last.fm seeds, popularity", r"On Last\.fm seeds tag overlap does beat popularity at K=10, [\d.]+ against ([\d.]+)", bs[("popularity", "lastfm_tag")]["ndcg"]),
        p("Playlist seeds, tags", r"On playlist seeds it does not, ([\d.]+) against", bs[("tags", "spotify_playlist")]["ndcg"]),
        p("Playlist seeds, popularity", r"On playlist seeds it does not, [\d.]+ against ([\d.]+),", bs[("popularity", "spotify_playlist")]["ndcg"]),
        p("Tags can rank, playlist seeds (%)", r"tags can rank (\d+)% of the\s+playlist seeds", bs[("tags", "spotify_playlist")]["served"], 100),
        p("Tags can rank, Last.fm seeds (%)", r"playlist seeds and (\d+)% of the Last\.fm ones", bs[("tags", "lastfm_tag")]["served"], 100),
        p("Acoustic can rank, playlist seeds (%)", r"acoustic (\d+)% against", bs[("acoustic", "spotify_playlist")]["served"], 100),
        p("Acoustic can rank, Last.fm seeds (%)", r"acoustic \d+% against (\d+)%", bs[("acoustic", "lastfm_tag")]["served"], 100),
    ]

    # the headline sentences
    rows += [
        p("Tags vs popularity, every seed: tags", r"that advantage is spent: ([\d.]+) against", by_k[(10, "tags")]["ndcg_all"]),
        p("Tags vs popularity, every seed: popularity", r"that advantage is spent: [\d.]+ against ([\d.]+),", by_k[(10, "popularity")]["ndcg_all"]),
        p("Tags where a tag exists", r"— ([\d.]+), nearly four times the popularity", by_k[(10, "tags")]["ndcg_served"]),
        p("K=5: tags", r"baseline, ([\d.]+) against [\d.]+\. It loses", by_k[(5, "tags")]["ndcg_all"]),
        p("K=5: popularity", r"baseline, [\d.]+ against ([\d.]+)\. It loses", by_k[(5, "popularity")]["ndcg_all"]),
        p("Popularity keeps (%)", r"keeps (\d+)% of its\s+univariate", r_all["beta_pop"] / one(conn, "novelty_vs_obscurity")["r_pop"], 100),
        p("Year loses (%)", r"Year loses (\d+)% of its own", 1 - r_all["beta_year"] / one(conn, "novelty_vs_obscurity")["r_year"], 100),
        p("`tags` gains without its artist", r"`tags` gains ([\d.]+) when", blind["tags"]["ndcg_blind"] - blind["tags"]["ndcg_shipped"]),
    ]

    # queue length
    h = lambda k: by_k[(k, "hybrid")]  # noqa: E731
    r_ = lambda k: by_k[(k, "random")]  # noqa: E731
    rows += [
        p("Precision multiple at 5", r"Per-slot precision runs ([\d.]+)x random at 5", h(5)["precision_all"] / r_(5)["precision_all"]),
        p("Precision multiple at 50", r"only ([\d.]+)x by 50", h(50)["precision_all"] / r_(50)["precision_all"]),
        p("Hit rate at 5 (%)", r"climbs from (\d+)% to \d+%", h(5)["hit_rate_all"], 100),
        p("Hit rate at 50 (%)", r"climbs from \d+% to (\d+)%", h(50)["hit_rate_all"], 100),
        p("Random hit rate at 50 (%)", r"no better than random's (\d+)%", r_(50)["hit_rate_all"], 100),
        p("Hit rate at 20 (%)", r"keeps a (\d+)% hit rate", h(20)["hit_rate_all"], 100),
        p("Precision multiple at 20", r"hit rate at ([\d.]+)x random", h(20)["precision_all"] / r_(20)["precision_all"]),
    ]

    # the cold end
    pop_q1 = by_q_all[("popularity", 0)]["ndcg"]
    rows += [
        p("Evaluable Q1 seeds", r"one draw of Q1's (\d+) evaluable seeds", floor["q1_seeds"]),
        p("Lowest of 20 draws", r"evaluable seeds ranges from ([\d.]+)\s+to", floor["lowest_draw"]),
        p("Highest of 20 draws", r"evaluable seeds ranges from [\d.]+\s+to ([\d.]+)", floor["highest_draw"]),
        p("Popularity in Q1", r"Popularity's ([\d.]+) is under", pop_q1),
        Row("Popularity's Q1 score is under every one of the draws", "under all 20",
            f"{pop_q1:.4f} < {floor['lowest_draw']:.4f}", pop_q1 < floor["lowest_draw"]),
        p("Acoustic Q1", r"wide margin in Q1 \(([\d.]+) and [\d.]+ against [\d.]+\)", by_q_all[("acoustic", 0)]["ndcg"]),
        p("Hybrid Q1", r"wide margin in Q1 \([\d.]+ and ([\d.]+) against [\d.]+\)", by_q_all[("hybrid", 0)]["ndcg"]),
        p("Random floor Q1", r"wide margin in Q1 \([\d.]+ and [\d.]+ against ([\d.]+)\)", by_q_all[("random", 0)]["ndcg"]),
        p("Acoustic can rank, lowest (%)", r"They can rank (\d+)[–-]\d+% of seeds \(acoustic\)", min(by_q_all[("acoustic", q)]["served"] for q in range(5)), 100),
        p("Acoustic can rank, highest (%)", r"They can rank \d+[–-](\d+)% of seeds \(acoustic\)", max(by_q_all[("acoustic", q)]["served"] for q in range(5)), 100),
        p("Hybrid can rank, lowest (%)", r"and (\d+)[–-]\d+%\s+\(hybrid\)", min(by_q_all[("hybrid", q)]["served"] for q in range(5)), 100),
        p("Hybrid can rank, highest (%)", r"and \d+[–-](\d+)%\s+\(hybrid\)", max(by_q_all[("hybrid", q)]["served"] for q in range(5)), 100),
    ]

    # limitations and the summary table
    rows += [
        p("Q1 seeds with a label, cold-end section (%)", r"reach (\d+)% of the coldest\s+quintile", cov[0]["with_positives"], 100),
        p("Candidate pool of the sample benchmark", r"than the committed ones because the candidate pool is 200 tracks rather than\s+([\d,]+)", n_all),
        p("Q1 seeds with a label, limitation (%)", r"Only (\d+)% of Q1 seeds", cov[0]["with_positives"], 100),
        p("... the most popular share of itself (%)", r"most popular (\d+)% of itself", cov[0]["with_positives"], 100),
        p("Year coverage (%)", r"regression covers (\d+)% of the corpus", yc["resolved_share"], 100),
        p("Year coverage, missing (%)", r"the\s+missing (\d+)% is not random", 1 - yc["resolved_share"], 100),
        p("Years resolved", r"resolves a release year for ([\d,]+)\s+of [\d,]+ tracks", yc["resolved"]),
        p("Coldest quintile years resolved (%)", r"popularity-dependent: (\d+)% in the\s+coldest", yc["q1_resolved"], 100),
        p("Hottest quintile years resolved (%)", r"against (\d+)% in the hottest", yc["q5_resolved"], 100),
        Row("Unresolved tracks have under a third of the median listeners", "under 1/3",
            f"{yc['median_unresolved'] / yc['median_resolved']:.2f}", yc["median_unresolved"] / yc["median_resolved"] < 1 / 3),
        p("Playlist share released 2023 or later (%)", r"\((\d+)% of it is from 2023 or later\)", pl["recent_share"], 100),
        p("Feature coverage, 2025 (%), limitation", r"2025-26 releases\s+is (\d+)% and", fy["2025"]["feature_coverage"], 100),
        p("Feature coverage, 2026 (%), limitation", r"2025-26 releases\s+is \d+% and (\d+)% as of", fy["2026"]["feature_coverage"], 100),
        p("Zero-tag share, summary table (%)", r"\| ([\d.]+)% of tracks have zero effective tags", sig["zero_eff_share"], 100),
        p("Tag spread, summary table (pp)", r"popularity-dependent \((\d+)pp spread\)", one(conn, "coverage_by_quintile")["tag_spread"], 100),
        p("Feature coverage through 2024, summary (%)", r"— (\d+)% for releases through 2024", fy["<=2024"]["feature_coverage"], 100),
        p("Feature coverage 2026, summary (%)", r"through 2024, (\d+)% for 2026", fy["2026"]["feature_coverage"], 100),
        p("Unreachable, summary, Last.fm (%)", r"Measured — ([\d.]+)% of the Last\.fm sample", lf["unreachable"], 100),
        p("Unreachable, summary, playlists (%)", r"of the Last\.fm sample, ([\d.]+)% of the playlists", pl["unreachable"], 100),
        p("Tags vs baseline (x)", r"Measured — [\d.]+, ([\d.]+)x the baseline",
          by_k[(10, "tags")]["ndcg_served"] / by_k[(10, "popularity")]["ndcg_all"]),
    ]
    return rows


def readme(conn: sqlite3.Connection, md: str) -> list[Row]:
    s, r = one(conn, "tag_signal"), one(conn, "novelty_vs_obscurity")
    q = db.check(conn, "coverage_by_quintile")
    years = db.check(conn, "zero_tags_by_year")
    cov = db.check(conn, "gt_label_coverage")
    blind = {x["policy"]: x for x in db.check(conn, "artist_blind")}
    by_k = {(x["k"], x["policy"]): x for x in db.check(conn, "benchmark_by_k")}
    by_q = {(x["policy"], x["quintile"]): x for x in db.check(conn, "benchmark_by_quintile")}
    fb = {x["bucket"]: x for x in db.check(conn, "fallback_coverage")}

    def p(label, pattern, sql, scale=1.0, group=1):
        return printed(label, grab(md, pattern, group), sql, scale)

    rows = [
        p("Corpus with no usable tag (%)", r"\*\*([\d.]+)% of the corpus has no\s+usable tag", s["zero_eff_share"], 100),
        p("Unreachable by any content signal (%)", r"\| ([\d.]+)% of tracks are unreachable",
          fb["no tags"]["no_feature"] / fb["no tags"]["n_tracks"], 100),
    ]
    for x in q:
        n = x["quintile"] + 1
        pat = rf"^\| Q{n}[^|]*\| \**(\d+)%\** \| (\d+)% \|"
        rows += [
            p(f"Q{n}: tag coverage (%)", pat, x["tag_coverage"], 100, group=1),
            p(f"Q{n}: acoustic coverage (%)", pat, x["feature_coverage"], 100, group=2),
        ]
    rows += [
        p("Tag coverage swing (pp)", r"Tag coverage swings \*\*(\d+) percentage points", q[0]["tag_spread"], 100),
        p("Acoustic coverage swing (pp)", r"acoustic\s+coverage swings \*\*(\d+)\*\*", q[0]["feature_spread"], 100),
        p("Regression sample", r"over the ([\d,]+) tracks carrying both", r["n_tracks"]),
        p("Year: univariate", r"\| Release year \| ([+-][\d.]+)", r["r_year"]),
        p("Year: partial", r"\| Release year \| [+-][\d.]+ \| \*\*([+-][\d.]+)", r["beta_year"]),
        p("log10(listeners): univariate", r"\| log10\(listeners\) \| ([+-][\d.]+)", r["r_pop"]),
        p("log10(listeners): partial", r"\| log10\(listeners\) \| [+-][\d.]+ \| \*\*([+-][\d.]+)", r["beta_pop"]),
        p("Zero-tag share, releases before 2010 (%)", r"from (\d+)% for pre-2010", years[0]["zero_share"], 100),
        p("Zero-tag share, 2023 and later (%)", r"to\s+(\d+)% for 2023-and-later", years[-1]["zero_share"], 100),
        p("First pass / backfill popularity (x)", r"\*\*([\d.]+)× more popular\*\*",
          one(conn, "selection_bias")["ratio"]),
        p("Labels / corpus popularity (x)", r"labels are ([\d.]+)× more popular",
          one(conn, "gt_popularity_bias")["ratio"]),
    ]
    for policy in POLICIES:
        h = by_k[(10, policy)]
        pat = rf"^\| `{policy}`[^|]*\| (\d+)% \| \**([\d.]+)\** \| \**([\d.]+)\** \|"
        rows += [
            p(f"`{policy}`: can rank (%)", pat, h["coverage"], 100, group=1),
            p(f"`{policy}`: NDCG@10 where it can", pat, h["ndcg_served"], group=2),
            p(f"`{policy}`: NDCG@10 over every seed", pat, h["ndcg_all"], group=3),
        ]
        pat = rf"^\| `{policy}` \|" + r" \**([\d.]+)\** \|" * 4 + r"\s*$"
        for g, k in enumerate((5, 10, 20, 50), 1):
            rows.append(p(f"`{policy}`: NDCG@{k}", pat, by_k[(k, policy)]["ndcg_all"], group=g))
        pat = rf"^\| `{policy}` \| \**(\d+\.\d)%\** \| ([\d.]+) \| ([\d.]+) \|"
        rows += [
            p(f"`{policy}`: same-artist share of top-10 (%)", pat, blind[policy]["same_artist_share"], 100, group=1),
            p(f"`{policy}`: NDCG@10 artist-blind", pat, blind[policy]["ndcg_blind"], group=3),
        ]
        pat = rf"^\| `{policy}` \|" + r" \**([\d.]+)\** \|" * 5
        for qi in range(5):
            rows.append(p(f"`{policy}`: NDCG@10 in {QUINTILE_LABELS[qi]}", pat,
                          by_q[(policy, qi)]["ndcg"], group=qi + 1))
    labels = r"label\s+coverage runs" + r" (\d+)% /" * 4 + r" (\d+)%"
    for x in cov:
        rows.append(p(f"{QUINTILE_LABELS[x['quintile']]}: seeds with a label (%)", labels,
                      x["with_positives"], 100, group=x["quintile"] + 1))
    return rows + readme_samples(conn, md)


# ── Report ──────────────────────────────────────────────────────────────────

def table(rows: list[Row]) -> list[str]:
    mark = {True: "✓", False: "**✗**", None: "—"}
    out = ["| Number | Published | SQL | |", "|---|---:|---:|:---:|"]
    out += [f"| {r.label} | {r.published} | {r.sql} | {mark[r.ok]} |" for r in rows]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Cross-check published numbers in SQL")
    ap.add_argument("--db", type=Path, default=config.DATA_DIR / "kpoprec.sample.db")
    ap.add_argument("--reports", type=Path, default=config.REPORTS_DIR / "sample")
    ap.add_argument("--readme", type=Path, default=None,
                    help="also check the README; its numbers are the full corpus's")
    ap.add_argument("--out", type=Path, default=None,
                    help="default: <reports>/sql_crosscheck.md")
    args = ap.parse_args()

    if not args.db.exists():
        sys.exit(f"[FATAL] no database at {args.db} -- build it with `make db`")
    conn = db.connect(args.db)
    meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())

    rep = args.reports
    try:
        conn.execute("SELECT 1 FROM track_source LIMIT 1")
    except sqlite3.OperationalError:
        sys.exit(f"[FATAL] {args.db.name} was built from an older schema -- rebuild it with "
                 "`make db` (or `make db-full`)")
    sections = [
        ("tag_sparsity_summary.md", sparsity(conn, read(rep / "tag_sparsity_summary.md"))),
        ("tag_vocabulary.csv", vocabulary(conn, rep / "tag_vocabulary.csv")),
        ("gt_diagnostics.md", ground_truth(conn, read(rep / "gt_diagnostics.md"))),
        ("eval_by_k.csv and eval_by_quintile.csv", benchmark_csvs(conn, rep)),
        ("eval_summary.md", benchmark_md(conn, read(rep / "eval_summary.md"))),
    ]
    if args.readme:
        sections.append((args.readme.name, readme(conn, read(args.readme) or "")))

    rows = [r for _, rs in sections for r in rs]
    checked = [r for r in rows if r.ok is not None]
    failed = [r for r in checked if not r.ok]
    skipped = [name for name, rs in sections if all(r.ok is None for r in rs)]

    md = [
        "# SQL cross-check\n",
        f"> Every number below was recomputed from `{args.db.name}` "
        f"(built from `{meta.get('songs', '?')}` and `{meta.get('ground_truth', '?')}`)",
        "> by the queries in `sql/checks/`, with no pandas or numpy involved, and",
        "> compared with the report that published it. A printed number matches",
        "> when the SQL value rounds to it; the benchmark CSVs are held to 1e-9.\n",
        f"**{len(checked)} numbers checked: "
        + ("all match.**" if not failed else f"{len(failed)} do not match.**"),
    ]
    if skipped:
        md.append(f"\nNot published in this run, so shown but not checked: "
                  f"{', '.join(f'`{s}`' for s in skipped)}.")
    for name, rs in sections:
        md += ["", f"## {name}", "", *table(rs)]

    out = args.out or rep / "sql_crosscheck.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"[check] {len(checked)} numbers checked, {len(failed)} mismatched")
    for r in failed:
        print(f"  ✗ {r.label}: published {r.published}, SQL {r.sql}")
    print(f"[done] -> {out}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
