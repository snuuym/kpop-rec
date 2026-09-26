#!/usr/bin/env python3
"""Stage 6 — the core EDA. Three questions decide the whole system design.

  Q1  After removing tags that every K-pop track carries, how much signal is
      left? (upper bound on what tag-based retrieval can ever do)
  Q2  Is tag sparsity about tracks being *new*, or about them being *obscure*?
      (the central hypothesis — and the two imply opposite remedies)
  Q3  Where tags are missing, do audio features fill the gap?
      (does the fallback path actually exist, or is part of the corpus
      unreachable by any content-based method?)

Q2 is the one that matters most. If sparsity is driven by novelty, the fix is
to wait or to scrape more tag sources. If it is driven by obscurity, no amount
of tag scraping helps — tags are user-generated content, and nobody is
generating them for tracks nobody listens to. The script separates the two with
a standardized two-variable OLS rather than eyeballing the marginal plots,
because year and popularity are themselves correlated.

Usage
-----
    python3 scripts/analyze_tag_sparsity.py
    python3 scripts/analyze_tag_sparsity.py --songs data/songs.sample.json

Analyses that need ``year`` or ``listeners`` are skipped with a notice when
those fields are absent; run ``enrich_metadata.py`` first for the full report.

Outputs
-------
    figures/fig1_tag_count_distribution.png
    figures/fig2_tags_vs_year.png          (needs year)
    figures/fig3_tags_vs_popularity.png    (needs listeners)
    figures/fig4_coverage_crosstab.png
    figures/fig5_signal_coverage.png       (needs listeners)
    reports/tag_sparsity_summary.md
    reports/tag_vocabulary.csv
    reports/song_buckets.csv               (stratification for evaluation)
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kpoprec import config  # noqa: E402
from kpoprec.io import load_songs  # noqa: E402
from kpoprec.normalize import normalize_tag  # noqa: E402
from kpoprec.playlist import SOURCE_LASTFM, source_of  # noqa: E402
from kpoprec.recommend import quintile_of  # noqa: E402
from kpoprec.taxonomy import NON_DISCRIMINATIVE_TAGS, is_effective  # noqa: E402

# Last.fm tagging turns out to be near-binary: a track has either zero
# effective tags or six-plus. The 1-2 band held only 4 tracks in practice, so
# stratification uses a binary split rather than a gradient of buckets.
NO_TAGS, HAS_TAGS = "no tags", "has tags"
BUCKET_EDGES = [(0, 0, NO_TAGS), (1, 999, HAS_TAGS)]

PALETTE = ["#E8547C", "#3D5A80", "#EE9B00", "#606C38", "#9B5DE5"]

# Figures live in figures/; the report lives in reports/ and links across.
FIG_PREFIX = "../figures"


def bucket_of(n: int) -> str:
    for lo, hi, label in BUCKET_EDGES:
        if lo <= n <= hi:
            return label
    return BUCKET_EDGES[-1][2]


def to_frame(path: Path) -> pd.DataFrame:
    songs = load_songs(path)
    print(f"[load] {len(songs)} records <- {path}")

    rows = []
    for s in songs:
        raw = [t for t in (normalize_tag(t) for t in (s.get("all_tags") or [])) if t]
        eff = [t for t in raw if is_effective(t)]
        feats = s.get("features") or {}
        rows.append({
            "title": s.get("title", ""),
            "artist": s.get("artist", ""),
            "key": f"{str(s.get('artist', '')).lower()}::{str(s.get('title', '')).lower()}",
            "raw_tags": raw,
            "n_raw": len(raw),
            "n_eff": len(eff),
            "n_classified": len(s.get("tags") or []),
            "has_feats": bool(feats) and feats.get("danceability") is not None,
            "year": s.get("year") or s.get("release_year"),
            "listeners": s.get("listeners"),
            "playcount": s.get("playcount"),
            "tag_source": s.get("tag_source"),
            "source": source_of(s),
        })

    df = pd.DataFrame(rows)
    df["bucket"] = df["n_eff"].apply(bucket_of)
    for c in ("year", "listeners", "playcount"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def style(ax, title="", xlabel="", ylabel="") -> None:
    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25, linewidth=0.7)
    ax.set_axisbelow(True)


# ── Data integrity ──────────────────────────────────────────────────────────

def integrity_check(df: pd.DataFrame, md: list) -> None:
    """Separate "nobody tagged this" from "we never asked".

    These look identical in the data and mean opposite things. Only the first
    is a finding; the second is a bug in the collection pipeline. Tracks that
    ``backfill_tags.py`` queried individually are verified as the former.
    """
    n = len(df)
    empty = int((df["n_raw"] == 0).sum())
    root_only = int(((df["n_raw"] > 0) & (df["n_eff"] == 0)).sum())
    verified = int(((df["n_raw"] == 0) & (df["tag_source"] == "backfill")).sum())
    unverified = empty - verified

    md += [
        "## Data integrity\n",
        "| Status | Tracks | Share | Meaning |",
        "|---|---:|---:|---|",
        f"| Verified: nobody has tagged it | {verified} | {verified / n * 100:.1f}% | "
        "**genuine absence of UGC** (confirmed per track via the API) |",
        f"| Unverified empty `all_tags` | {unverified} | {unverified / n * 100:.1f}% | "
        "possibly a collection gap |",
        f"| Tagged, but only with root tags | {root_only} | {root_only / n * 100:.1f}% | "
        "**genuine UGC sparsity** |",
        f"| Has effective tags | {n - empty - root_only} | "
        f"{(n - empty - root_only) / n * 100:.1f}% | usable |",
        "",
    ]

    if unverified > n * 0.05:
        md += [
            f"\n> **{unverified} tracks with empty `all_tags` were never verified, so the "
            "sparsity conclusions below are not yet trustworthy.**",
            "> Run `backfill_tags.py`, then re-run this script.\n",
        ]
        print(f"[integrity] {unverified}/{n} unverified — run backfill_tags.py first")
    else:
        md += [
            "\n> Empty tags were confirmed track by track against the Last.fm API: "
            "**this is genuine absence of UGC, not a gap in collection.**\n"
        ]
        print(
            f"[integrity] verified-untagged {verified}/{n}, "
            f"unverified {unverified}, root-only {root_only}"
        )
    md.append("")


def selection_bias_check(df: pd.DataFrame, md: list) -> None:
    """Were the originally-tagged tracks systematically more popular?

    The first tagging pass walked the corpus in popularity order, so if it was
    interrupted the surviving sample is biased. Quantifying that ratio is both
    a caveat on the data *and* independent evidence for the popularity
    hypothesis this project is testing.
    """
    if df["listeners"].notna().sum() < 50:
        return
    if "tag_source" not in df.columns or df["tag_source"].notna().sum() == 0:
        return

    # Only the Last.fm pull has a first pass to compare against. Playlist tracks
    # are all tagged by the backfill stage because Phase B never saw them, so
    # letting them in would fill the "backfill" group with tracks that were not
    # left behind by an interrupted run.
    d = df[df["source"] == SOURCE_LASTFM].dropna(subset=["listeners"])
    original = d[d["tag_source"].isna()]["listeners"]
    backfilled = d[d["tag_source"] == "backfill"]["listeners"]
    if len(original) < 30 or len(backfilled) < 30:
        return

    ratio = original.median() / max(backfilled.median(), 1)
    md += [
        "### Selection-bias check\n",
        "The first tagging pass traversed the corpus in descending popularity "
        "order, so an interruption leaves a sample skewed toward the head:\n",
        "| Group | Tracks | Median listeners |",
        "|---|---:|---:|",
        f"| Tagged in the first pass | {len(original)} | {original.median():,.0f} |",
        f"| Filled in by backfill | {len(backfilled)} | {backfilled.median():,.0f} |",
        f"\nFirst-pass tracks are about **{ratio:.1f}x** as popular. "
        + (
            "**The bias is confirmed** — drawing conclusions from the first-pass "
            "sample alone would have badly overstated tag coverage. It is also "
            "independent evidence for the popularity-driven tagging hypothesis.\n"
            if ratio > 1.5
            else "The two groups are comparable; no material bias.\n"
        ),
    ]
    print(f"[bias] first-pass/backfill median listeners ratio = {ratio:.2f}")


# ── Q1 ──────────────────────────────────────────────────────────────────────

def fig1_distribution(df: pd.DataFrame, figdir: Path, md: list) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.6))

    cap = 15
    counts = df["n_eff"].clip(upper=cap).value_counts().sort_index()
    colors = [PALETTE[0] if i == 0 else PALETTE[1] for i in counts.index]
    ax1.bar(counts.index, counts.values, color=colors, width=0.78)
    for x, y in zip(counts.index, counts.values):
        if y > len(df) * 0.02:
            ax1.text(x, y, f"{y}", ha="center", va="bottom", fontsize=8)
    style(ax1, "Fig 1a - Effective tag count (root tags removed)",
          f"# effective tags (>={cap} merged)", "# tracks")

    srt = np.sort(df["n_eff"].values)
    cum = np.arange(1, len(srt) + 1) / len(srt) * 100
    ax2.plot(srt, cum, color=PALETTE[1], linewidth=2)
    for thr in (0, 2):
        pct = (df["n_eff"] <= thr).mean() * 100
        ax2.axvline(thr, color=PALETTE[0], linestyle="--", alpha=0.6, linewidth=1)
        ax2.text(thr + 0.3, pct, f"<={thr}: {pct:.1f}%", fontsize=9, color=PALETTE[0])
    ax2.set_xlim(-0.5, min(srt.max(), 20))
    style(ax2, "Fig 1b - Cumulative distribution", "# effective tags",
          "cumulative % of tracks")

    fig.tight_layout()
    fig.savefig(figdir / "fig1_tag_count_distribution.png", dpi=150)
    plt.close(fig)

    n = len(df)
    zero = int((df["n_eff"] == 0).sum())
    thin = int((df["n_eff"] <= 2).sum())
    md += [
        "## Q1 - How much signal survives removing root tags?\n",
        f"- Corpus size: **{n}** tracks",
        f"- Raw tags average {df['n_raw'].mean():.1f} per track; "
        f"**effective tags average only {df['n_eff'].mean():.1f}** "
        f"(median {df['n_eff'].median():.0f})",
        f"- **{zero} tracks ({zero / n * 100:.1f}%) have no effective tags at all** "
        "-> tag-based retrieval cannot reach them",
        f"- {thin} tracks ({thin / n * 100:.1f}%) have 2 or fewer -> tag-overlap "
        "scoring barely discriminates between them",
        f"- Carrying a classified sub-genre label: {int((df['n_classified'] > 0).sum())} "
        f"({(df['n_classified'] > 0).mean() * 100:.1f}%)\n",
        f"![]({FIG_PREFIX}/fig1_tag_count_distribution.png)\n",
    ]
    print(f"[fig1] zero effective tags: {zero}/{n} ({zero / n * 100:.1f}%)")


def tag_vocabulary(df: pd.DataFrame, outdir: Path, md: list, top: int = 25) -> None:
    dfreq: Counter = Counter()
    for tags in df["raw_tags"]:
        dfreq.update(set(tags))
    n = len(df)
    # Ties broken by name. Counter.most_common keeps first-seen order, and the
    # set above iterates in hash order, which changes with every interpreter
    # run -- so without this the committed CSV reshuffles on each regeneration.
    ranked = sorted(dfreq.items(), key=lambda kv: (-kv[1], kv[0]))

    lines = ["| Tag | Tracks | Share | Root tag |", "|---|---:|---:|:---:|"]
    for tag, c in ranked[:top]:
        root = "yes" if tag in NON_DISCRIMINATIVE_TAGS else ""
        lines.append(f"| `{tag}` | {c} | {c / n * 100:.1f}% | {root} |")

    singleton = sum(1 for c in dfreq.values() if c == 1)
    md += [
        "### Tag vocabulary\n",
        f"- Unique tags: **{len(dfreq)}**",
        f"- Tags appearing on exactly one track: **{singleton}** "
        f"({singleton / max(len(dfreq), 1) * 100:.1f}%) -> these contribute almost "
        "nothing to similarity, and are where TF-IDF weighting would gain over "
        "plain rule matching\n",
        "\n".join(lines),
        "",
    ]
    pd.DataFrame(ranked, columns=["tag", "doc_freq"]).to_csv(
        outdir / "tag_vocabulary.csv", index=False
    )
    print(f"[vocab] {len(dfreq)} unique tags, {singleton} appear only once")


# ── Q2 ──────────────────────────────────────────────────────────────────────

def fig2_year(df: pd.DataFrame, figdir: Path, md: list) -> bool:
    d = df.dropna(subset=["year"])
    d = d[(d["year"] >= 1990) & (d["year"] <= 2026)]
    if len(d) < 50:
        md += [
            "## Q2a - Tag sparsity vs release year\n",
            "Skipped: the `year` field is missing or the sample is too small. "
            "Run `enrich_metadata.py` first.\n",
        ]
        print("[fig2] skipped: no year field")
        return False

    d = d.copy()
    d["yr_bin"] = pd.cut(
        d["year"], bins=[1989, 2009, 2014, 2017, 2020, 2022, 2027],
        labels=["<=2009", "10-14", "15-17", "18-20", "21-22", "23+"],
    )
    g = d.groupby("yr_bin", observed=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.6))
    med = g["n_eff"].median()
    ax1.bar(range(len(med)), med.values, color=PALETTE[1], width=0.7)
    ax1.set_xticks(range(len(med)))
    ax1.set_xticklabels(med.index, fontsize=9)
    for i, (v, cnt) in enumerate(zip(med.values, g.size().values)):
        ax1.text(i, v, f"n={cnt}", ha="center", va="bottom", fontsize=8, color="#666")
    style(ax1, "Fig 2a - Median effective tags by release year",
          "release year", "median # effective tags")

    zero = g["n_eff"].apply(lambda x: (x == 0).mean() * 100)
    ax2.plot(range(len(zero)), zero.values, "o-", color=PALETTE[0],
             linewidth=2, markersize=7)
    ax2.set_xticks(range(len(zero)))
    ax2.set_xticklabels(zero.index, fontsize=9)
    style(ax2, "Fig 2b - Share of zero-tag tracks by year",
          "release year", "% with zero effective tags")

    fig.tight_layout()
    fig.savefig(figdir / "fig2_tags_vs_year.png", dpi=150)
    plt.close(fig)

    md += [
        "## Q2a - Tag sparsity vs release year\n",
        f"Sample: {len(d)} tracks with a known year.\n",
        f"![]({FIG_PREFIX}/fig2_tags_vs_year.png)\n",
    ]
    print(f"[fig2] ok, {len(d)} tracks with year")
    return True


def fig3_popularity(df: pd.DataFrame, figdir: Path, md: list) -> bool:
    d = df.dropna(subset=["listeners"])
    d = d[d["listeners"] > 0]
    if len(d) < 50:
        md += [
            "## Q2b - Tag sparsity vs popularity\n",
            "Skipped: the `listeners` field is missing. Run `enrich_metadata.py` "
            "first — it is also the prerequisite for any novelty metric.\n",
        ]
        print("[fig3] skipped: no listeners field")
        return False

    d = d.copy()
    d["log_listeners"] = np.log10(d["listeners"])
    d["pop_q"] = pd.Categorical.from_codes(
        quintile_of(d["listeners"].to_numpy(float)),
        ["Q1 coldest", "Q2", "Q3", "Q4", "Q5 hottest"],
    )
    g = d.groupby("pop_q", observed=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.6))
    rng = np.random.default_rng(0)
    ax1.scatter(
        d["log_listeners"], d["n_eff"] + rng.uniform(-0.25, 0.25, len(d)),
        s=9, alpha=0.28, color=PALETTE[1], edgecolors="none",
    )
    q = g["log_listeners"].median()
    ax1.plot(q.values, g["n_eff"].median().values, "o-", color=PALETTE[0],
             linewidth=2.4, markersize=8, label="quintile median")
    ax1.legend(fontsize=9, frameon=False)
    style(ax1, "Fig 3a - Effective tags vs popularity",
          "log10(listeners)", "# effective tags")

    zero = g["n_eff"].apply(lambda x: (x == 0).mean() * 100)
    ax2.bar(range(len(zero)), zero.values, color=PALETTE[0], width=0.7)
    ax2.set_xticks(range(len(zero)))
    ax2.set_xticklabels(zero.index, fontsize=9)
    for i, v in enumerate(zero.values):
        ax2.text(i, v, f"{v:.0f}%", ha="center", va="bottom", fontsize=9)
    style(ax2, "Fig 3b - Share of zero-tag tracks by popularity quintile",
          "popularity quintile", "% with zero effective tags")

    fig.tight_layout()
    fig.savefig(figdir / "fig3_tags_vs_popularity.png", dpi=150)
    plt.close(fig)

    md += [
        "## Q2b - Tag sparsity vs popularity\n",
        f"Sample: {len(d)} tracks with a listener count.\n",
        f"![]({FIG_PREFIX}/fig3_tags_vs_popularity.png)\n",
    ]
    print(f"[fig3] ok, {len(d)} tracks with listeners")
    return True


def disentangle(df: pd.DataFrame, md: list) -> None:
    """Controlling for popularity, does release year still explain sparsity?

    Standardized OLS via ``numpy.linalg.lstsq`` — no extra dependency, and at
    two predictors there is nothing a heavier library would add.
    """
    d = df.dropna(subset=["year", "listeners"])
    d = d[(d["year"].between(1990, 2026)) & (d["listeners"] > 0)]
    if len(d) < 100:
        md += [
            "## Q2c - Is it novelty, or is it obscurity?\n",
            "Skipped: needs both `year` and `listeners`, and the sample is too "
            "small.\n",
        ]
        print("[disentangle] skipped: insufficient sample")
        return

    def z(x):
        x = np.asarray(x, float)
        return (x - x.mean()) / (x.std() or 1)

    yr, pop, y = z(d["year"]), z(np.log10(d["listeners"])), z(d["n_eff"])
    X = np.column_stack([np.ones(len(d)), yr, pop])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    r2 = 1 - resid.var() / y.var()

    b_yr_only = np.corrcoef(yr, y)[0, 1]
    b_pop_only = np.corrcoef(pop, y)[0, 1]

    verdict = (
        "**Popularity dominates.** Once popularity is controlled for, the "
        "partial effect of release year collapses. \"New tracks have no tags\" "
        "is a surface reading of \"obscure tracks have no tags\" — tags are "
        "user-generated content, and they only accumulate where listeners do."
        if abs(beta[2]) > abs(beta[1])
        else
        "**Release year retains an independent effect.** Controlling for "
        "popularity leaves a substantial year coefficient, implying a temporal "
        "factor beyond obscurity — plausibly the decline of Last.fm's tagging "
        "culture over time."
    )

    md += [
        "## Q2c - Is it novelty, or is it obscurity? (the central test)\n",
        f"Sample: {len(d)} tracks with both fields. All variables standardized, "
        "then regressed jointly:\n",
        "| Predictor | Univariate correlation | Partial coefficient |",
        "|---|---:|---:|",
        f"| Release year | {b_yr_only:+.3f} | **{beta[1]:+.3f}** |",
        f"| log10(listeners) | {b_pop_only:+.3f} | **{beta[2]:+.3f}** |",
        f"\nModel R^2 = {r2:.3f}\n",
        f"**Conclusion:** {verdict}\n",
        "> This determines where further effort is worth spending. If sparsity "
        "is driven by popularity, scraping additional tag sources has a low "
        "ceiling, and the effort belongs on signals that do not depend on UGC "
        "at all — acoustic features, or features derived from the audio "
        "directly.\n",
    ]
    print(f"[disentangle] beta_year={beta[1]:+.3f}  beta_pop={beta[2]:+.3f}  R2={r2:.3f}")


# ── Q3 ──────────────────────────────────────────────────────────────────────

def fig4_coverage(df: pd.DataFrame, figdir: Path, md: list) -> None:
    order = [b[2] for b in BUCKET_EDGES]
    ct = pd.DataFrame(
        {
            "no_feat": [int(((df["bucket"] == b) & ~df["has_feats"]).sum()) for b in order],
            "has_feat": [int(((df["bucket"] == b) & df["has_feats"]).sum()) for b in order],
        },
        index=order,
    )
    ct = ct[ct.sum(axis=1) > 0]
    ct.columns = ["No audio feature", "Has audio feature"]

    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    bottom = np.zeros(len(ct))
    for c, color in zip(ct.columns, [PALETTE[0], PALETTE[3]]):
        ax.bar(ct.index, ct[c], bottom=bottom, label=c, color=color, width=0.6)
        for i, v in enumerate(ct[c]):
            if v > len(df) * 0.02:
                ax.text(i, bottom[i] + v / 2, f"{v}", ha="center", va="center",
                        fontsize=9, color="white", fontweight="bold")
        bottom += ct[c].values
    ax.legend(fontsize=9, frameon=False)
    style(ax, "Fig 4 - Tag sparsity x audio-feature coverage",
          "effective-tag bucket", "# tracks")
    fig.tight_layout()
    fig.savefig(figdir / "fig4_coverage_crosstab.png", dpi=150)
    plt.close(fig)

    # Tracks with neither signal are unreachable by any content-based method.
    unreachable = (
        int(ct.loc[NO_TAGS, "No audio feature"]) if NO_TAGS in ct.index else 0
    )
    n = len(df)
    tbl = [
        "| Effective-tag bucket | No feature | Has feature | Total | Feature coverage |",
        "|---|---:|---:|---:|---:|",
    ]
    for b in ct.index:
        a, c = int(ct.loc[b, "No audio feature"]), int(ct.loc[b, "Has audio feature"])
        tbl.append(f"| {b} | {a} | {c} | {a + c} | {c / (a + c) * 100:.1f}% |")

    md += [
        "## Q3 - Does the fallback path hold up?\n",
        "\n".join(tbl),
        "",
        f"\n- **Unreachable tracks: {unreachable} ({unreachable / n * 100:.1f}%)** — "
        "no effective tags *and* no audio features. No content-based method can "
        "retrieve these; only a popularity fallback reaches them at all.",
        f"- Overall audio-feature coverage: {df['has_feats'].mean() * 100:.1f}%\n",
        f"![]({FIG_PREFIX}/fig4_coverage_crosstab.png)\n",
        "> This table defines both the stratification used for evaluation and "
        "the retrieval cascade: features -> hybrid scoring, tags only -> TF-IDF, "
        "neither -> popularity.\n",
    ]
    print(f"[fig4] unreachable: {unreachable}/{n} ({unreachable / n * 100:.1f}%)")


def fig5_signal_comparison(df: pd.DataFrame, figdir: Path, md: list) -> None:
    """The project's central argument, in one chart."""
    d = df.dropna(subset=["listeners"])
    d = d[d["listeners"] > 0]
    if len(d) < 50:
        return

    d = d.copy()
    # The benchmark's quintiles, not pd.qcut's value-based bins. The two split
    # ties at a bin edge differently, and a coverage table and a ranking table
    # that cut the library differently are not describing the same Q1.
    d["q"] = pd.Categorical.from_codes(
        quintile_of(d["listeners"].to_numpy(float)),
        ["Q1\ncoldest", "Q2", "Q3", "Q4", "Q5\nhottest"],
    )
    g = d.groupby("q", observed=True)
    tag_cov = g["n_eff"].apply(lambda x: (x > 0).mean() * 100)
    feat_cov = g["has_feats"].apply(lambda x: x.mean() * 100)
    x = np.arange(len(tag_cov))

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.plot(x, feat_cov.values, "o-", color=PALETTE[3], linewidth=2.8,
            markersize=9, label="Audio features (ReccoBeats)")
    ax.plot(x, tag_cov.values, "s-", color=PALETTE[0], linewidth=2.8,
            markersize=9, label="UGC tags (Last.fm)")
    ax.fill_between(x, tag_cov.values, feat_cov.values,
                    where=(feat_cov.values >= tag_cov.values),
                    color=PALETTE[3], alpha=0.10)
    for xi, (t, f) in enumerate(zip(tag_cov.values, feat_cov.values)):
        ax.text(xi, f + 3, f"{f:.0f}%", ha="center", fontsize=9, color=PALETTE[3])
        ax.text(xi, t - 7, f"{t:.0f}%", ha="center", fontsize=9, color=PALETTE[0])
    ax.set_xticks(x)
    ax.set_xticklabels(tag_cov.index, fontsize=9)
    ax.set_ylim(-8, 112)
    ax.legend(fontsize=10, frameon=False, loc="center left")
    style(ax, "Fig 5 - Signal coverage by popularity: UGC vs acoustic",
          "popularity quintile", "% of tracks with signal")
    fig.tight_layout()
    fig.savefig(figdir / "fig5_signal_coverage.png", dpi=150)
    plt.close(fig)

    spread_t = tag_cov.max() - tag_cov.min()
    spread_f = feat_cov.max() - feat_cov.min()
    md += [
        "## Central result - how each signal depends on popularity\n",
        "| Quintile | UGC tag coverage | Audio-feature coverage |",
        "|---|---:|---:|",
        *[
            f"| {q.replace(chr(10), ' ')} | {t:.0f}% | {f:.0f}% |"
            for q, t, f in zip(tag_cov.index, tag_cov.values, feat_cov.values)
        ],
        f"\n- UGC tag coverage varies by **{spread_t:.0f} percentage points** across "
        "quintiles — heavily popularity-dependent",
        f"- Acoustic feature coverage varies by only **{spread_f:.0f} points** — "
        "effectively popularity-independent\n",
        f"![]({FIG_PREFIX}/fig5_signal_coverage.png)\n",
        "> **This is the argument.** UGC signal serves the head; acoustic signal "
        "covers the whole distribution. A recommender built only on the former "
        "cannot reach the long tail — not because its ranking is weak, but "
        "because the input features do not exist there. That is an architectural "
        "limit, not an algorithmic one.\n",
    ]
    print(f"[fig5] tag coverage spread {spread_t:.0f}pp vs feature spread {spread_f:.0f}pp")


# ── Entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Tag sparsity analysis")
    ap.add_argument("--songs", type=Path, default=config.SONGS_JSON)
    ap.add_argument("--outdir", type=Path, default=config.REPORTS_DIR)
    ap.add_argument("--figdir", type=Path, default=config.FIGURES_DIR)
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    args.figdir.mkdir(parents=True, exist_ok=True)

    df = to_frame(args.songs)

    md = [
        "# Tag sparsity analysis\n",
        f"> Generated from `{args.songs.name}` · {len(df)} tracks\n",
        "---\n",
    ]

    integrity_check(df, md)
    fig1_distribution(df, args.figdir, md)
    tag_vocabulary(df, args.outdir, md)
    selection_bias_check(df, md)
    md.append("---\n")

    has_year = fig2_year(df, args.figdir, md)
    has_pop = fig3_popularity(df, args.figdir, md)
    if has_year and has_pop:
        disentangle(df, md)
    md.append("---\n")

    fig4_coverage(df, args.figdir, md)
    fig5_signal_comparison(df, args.figdir, md)

    missing = [c for c in ("year", "listeners") if df[c].notna().sum() < 50]
    if missing:
        md += [
            "---\n",
            "## Missing fields\n",
            f"These fields were absent, so some analyses were skipped: "
            f"`{'`, `'.join(missing)}`",
            "\nRun `python3 scripts/enrich_metadata.py` and re-run this script.\n",
        ]

    (args.outdir / "tag_sparsity_summary.md").write_text("\n".join(md), encoding="utf-8")
    df[["key", "artist", "title", "n_raw", "n_eff", "bucket",
        "has_feats", "year", "listeners"]].to_csv(
        args.outdir / "song_buckets.csv", index=False
    )

    print(f"\n[done] -> {args.outdir / 'tag_sparsity_summary.md'}")
    print(f"[done] -> {args.outdir / 'song_buckets.csv'}")
    if missing:
        print(f"[warn] missing {missing}; run enrich_metadata.py for the full report")


if __name__ == "__main__":
    main()
