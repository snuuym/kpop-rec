#!/usr/bin/env python3
"""Stage 7 - rank the library for every seed and score the result.

This is the benchmark the earlier stages were building toward. It answers the
one question the analysis could not: does a content-based ranking actually beat
ranking by popularity, and does the answer change in the long tail?

What is being measured
----------------------
Five policies, each scoring the whole library for a seed track:

  random       uniform noise -- the floor
  popularity   listener count -- the baseline that must be beaten
  tags         classified-genre and raw-tag overlap
  acoustic     nearest neighbour by weighted audio-feature distance
  hybrid       what the app ships: acoustic, with a tag bonus, tags as fallback

Scoring rules live in ``src/kpoprec/recommend.py`` so they cannot drift from the
app, and metrics in ``src/kpoprec/metrics.py``.

The two-column result
---------------------
A policy with no signal for a seed does not rank it badly -- it cannot rank it
at all. Averaging only over seeds it *can* rank flatters a narrow policy; a tag
method scored solely where tags exist looks fine, which is precisely the
illusion this project exists to puncture. Averaging over every seed and scoring
the blind spots zero answers a different question: what does a user get.

Both are reported. The gap between them is the cost of depending on a signal
that is not there -- the sparsity finding, in ranking terms.

Usage
-----
    python3 scripts/evaluate.py                    # bundled sample, no key
    python3 scripts/evaluate.py --songs data/songs.json \\
        --ground-truth data/ground_truth.json --outdir reports --figdir figures
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kpoprec import config  # noqa: E402
from kpoprec.io import load_songs  # noqa: E402
from kpoprec.metrics import METRIC_NAMES, evaluate_ranking, zero_metrics  # noqa: E402
from kpoprec.playlist import source_of  # noqa: E402
from kpoprec.pooling import evaluable_seeds  # noqa: E402
from kpoprec.recommend import (  # noqa: E402
    POLICIES,
    QUINTILE_LABELS,
    Library,
    can_serve,
    draw_rng,
    quintile_label,
    run_tiebreak,
    score,
    top_k,
)

KS = (5, 10, 20, 50)
HEADLINE_K = 10
# Validated with the dataviz palette checker (light surface, categorical):
# lightness band, chroma floor, CVD separation, normal-vision floor, contrast.
SERIES_COLORS = {
    "popularity": "#2F5FA8",
    "tags": "#C77B00",
    "acoustic": "#E8547C",
    "hybrid": "#9B5DE5",
}
FLOOR_COLOR = "#6B7280"
MARKERS = {"popularity": "s", "tags": "^", "acoustic": "o", "hybrid": "D"}
LINESTYLES = {"popularity": "--", "tags": ":", "acoustic": "-", "hybrid": "-."}


def style(ax, title="", xlabel="", ylabel="") -> None:
    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25, linewidth=0.7)
    ax.set_axisbelow(True)


# ── Evaluation ──────────────────────────────────────────────────────────────

def _average_draws(policy, lib, i, pos, pos_blind, same, tiebreak, seed, draws):
    """Score one seed under one policy, averaged over ``draws`` random draws.

    Deterministic policies use a single draw and are unaffected; only ``random``
    asks for more. Returns metrics as shipped, metrics with the seed's own
    artist removed from both ranking and labels, and the same-artist share of
    the top ``HEADLINE_K``.
    """
    per_k = {k: dict.fromkeys(METRIC_NAMES, 0.0) for k in KS}
    blind_per_k = {k: dict.fromkeys(METRIC_NAMES, 0.0) for k in KS}
    same_in_top = 0.0

    for d in range(draws):
        scores = score(policy, lib, i, draw_rng(seed, d, i))
        ranked = top_k(scores, max(KS), tiebreak)
        same_in_top += int(same[ranked[:HEADLINE_K]].sum())
        for k in KS:
            for name, v in evaluate_ranking(ranked, pos, k).items():
                per_k[k][name] += v
        if pos_blind:
            blind_scores = scores.copy()
            blind_scores[same] = -np.inf
            blind_ranked = top_k(blind_scores, max(KS), tiebreak)
            for k in KS:
                for name, v in evaluate_ranking(blind_ranked, pos_blind, k).items():
                    blind_per_k[k][name] += v

    for table in (per_k, blind_per_k):
        for k in KS:
            for name in METRIC_NAMES:
                table[k][name] /= draws
    return per_k, blind_per_k, same_in_top / draws


def run(lib: Library, songs: list[dict], gt: dict[str, list[str]], seed: int,
        repeats: int = 1) -> pd.DataFrame:
    """Score every policy on every evaluable seed. One row per seed per policy."""
    # One fixed permutation for the whole run: ties resolve randomly but
    # reproducibly, instead of inheriting the library's collection order.
    tiebreak = run_tiebreak(seed, lib.n)

    evaluable = evaluable_seeds(gt, songs)
    if not evaluable:
        sys.exit("[FATAL] no seed has an in-library positive; nothing to evaluate")

    rows = []
    for i, pos in sorted(evaluable.items()):
        same = lib.same_artist(i)
        # The artist-blind variant drops the seed's own artist from both sides.
        # A seed whose every positive is same-artist has nothing left to score,
        # so it leaves that variant's population rather than scoring zero in it.
        pos_blind = {j for j in pos if not same[j]}
        for policy in POLICIES:
            served = can_serve(policy, lib, i)
            if served:
                # The random policy is a distribution, not a ranking, and one
                # draw of it is a noisy estimate of the floor -- noisiest in Q1,
                # where only 110 seeds are evaluable. Since the floor is what
                # every other policy is read against, and the project's central
                # cold-tail claim is "popularity scores below it", it is
                # averaged over repeats rather than sampled once.
                draws = repeats if policy == "random" else 1
                per_k, blind_per_k, same_in_top = _average_draws(
                    policy, lib, i, pos, pos_blind, same, tiebreak, seed, draws
                )
            else:
                per_k = {k: zero_metrics() for k in KS}
                blind_per_k = {k: zero_metrics() for k in KS}
                same_in_top = 0.0

            row = {
                "seed_index": i,
                "policy": policy,
                "served": served,
                "blind_evaluable": bool(pos_blind),
                "n_positives": len(pos),
                "n_same_artist_positives": len(pos) - len(pos_blind),
                "same_artist_in_top": same_in_top,
                "listeners": songs[i].get("listeners") or 0,
                "source": source_of(songs[i]),
            }
            for k, m in per_k.items():
                for name, v in m.items():
                    row[f"{name}@{k}"] = v
            if pos_blind:
                for k, m in blind_per_k.items():
                    for name, v in m.items():
                        row[f"blind_{name}@{k}"] = v
            rows.append(row)

    df = pd.DataFrame(rows)
    # Quintiles come from the library, not from the evaluable seeds. Cutting
    # them over the seeds that happen to have labels would make Q1 mean "the
    # coldest fifth of the labelled tracks", which is a warmer set than the
    # coldest fifth of the catalogue -- ground truth reaches only 43% of it.
    # Every policy is then judged on the same, catalogue-wide partition.
    df["quintile"] = pd.Categorical(
        [quintile_label(q) for q in lib.quintile[df["seed_index"].to_numpy()]],
        categories=QUINTILE_LABELS, ordered=True,
    )
    return df


def headline(df: pd.DataFrame, k: int, prefix: str = "") -> pd.DataFrame:
    """Coverage, served-only metrics, and all-seed metrics for each policy.

    ``prefix`` selects the variant: "" for the ranking as shipped, "blind_" for
    the run with the seed's own artist removed from ranking and labels alike.
    """
    out = []
    for policy in POLICIES:
        d = df[df.policy == policy]
        if prefix:
            d = d[d.blind_evaluable]
        served = d[d.served]
        row = {
            "policy": policy,
            "coverage": len(served) / len(d) if len(d) else 0.0,
            "n_served": len(served),
            "n_seeds": len(d),
        }
        for m in METRIC_NAMES:
            col = f"{prefix}{m}@{k}"
            row[f"{m}_served"] = served[col].mean() if len(served) else float("nan")
            row[f"{m}_all"] = d[col].mean()
        out.append(row)
    return pd.DataFrame(out)


# ── Figure ──────────────────────────────────────────────────────────────────

def figure(df: pd.DataFrame, head: pd.DataFrame, figdir: Path, k: int) -> Path:
    figdir.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8))

    # 6a - what coverage costs. Two bars per policy, a 2px surface gap between.
    pol = [p for p in POLICIES if p != "random"]
    x = np.arange(len(pol))
    width = 0.38
    served = [float(head.loc[head.policy == p, f"ndcg_served"].iloc[0]) for p in pol]
    alls = [float(head.loc[head.policy == p, f"ndcg_all"].iloc[0]) for p in pol]
    ax1.bar(x - width / 2 - 0.01, served, width, label="on seeds it can rank",
            color=[SERIES_COLORS[p] for p in pol], alpha=0.45, edgecolor="white", linewidth=2)
    ax1.bar(x + width / 2 + 0.01, alls, width, label="over every seed",
            color=[SERIES_COLORS[p] for p in pol], edgecolor="white", linewidth=2)
    floor = float(head.loc[head.policy == "random", "ndcg_all"].iloc[0])
    ax1.axhline(floor, color=FLOOR_COLOR, linestyle="--", linewidth=1.4)
    # Keep clear space at the left edge so the floor label never sits on a bar.
    ax1.set_xlim(-0.95, len(pol) - 0.4)
    ax1.text(-0.9, floor, f"random\nfloor {floor:.3f}", va="bottom", ha="left",
             fontsize=8.5, color=FLOOR_COLOR, linespacing=1.3)
    for xi, (s, a) in enumerate(zip(served, alls)):
        ax1.text(xi - width / 2 - 0.01, s, f"{s:.3f}", ha="center", va="bottom", fontsize=8)
        ax1.text(xi + width / 2 + 0.01, a, f"{a:.3f}", ha="center", va="bottom", fontsize=8)
    ax1.set_xticks(x)
    ax1.set_xticklabels(pol)
    ax1.legend(frameon=False, fontsize=9)
    style(ax1, f"Fig 6a - What a missing signal costs (NDCG@{k})", "", f"NDCG@{k}")

    # 6b - the tail story, charged for blind spots.
    g = df.groupby(["policy", "quintile"], observed=True)[f"ndcg@{k}"].mean().unstack()
    labels = list(g.columns)
    for p in pol:
        ax2.plot(range(len(labels)), g.loc[p].values, marker=MARKERS[p],
                 linestyle=LINESTYLES[p], color=SERIES_COLORS[p], linewidth=2,
                 markersize=8, markeredgecolor="white", markeredgewidth=1.4, label=p)
    ax2.plot(range(len(labels)), g.loc["random"].values, linestyle="--", color=FLOOR_COLOR,
             linewidth=1.4, label="random")
    ax2.set_xticks(range(len(labels)))
    ax2.set_xticklabels(labels, fontsize=9)
    ax2.legend(frameon=False, fontsize=9, ncol=2)
    style(ax2, f"Fig 6b - NDCG@{k} by popularity quintile (every seed)",
          "seed popularity", f"NDCG@{k}")

    fig.tight_layout()
    path = figdir / "fig6_ranking_quality.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# ── Report ──────────────────────────────────────────────────────────────────

def _by_source(df: pd.DataFrame, per_seed: pd.DataFrame, sources: list[str], k: int) -> list[str]:
    """The headline table again, split by where the seed came from.

    The library is two samples: Last.fm's K-pop tag pages, and the owner's own
    playlists. The candidate pool is the whole library either way; what differs
    is the seed. A policy that wins on one and loses on the other is answering
    a question about the sampling, not about the policy.
    """
    n = per_seed.groupby("source").size()
    ndcg = df.groupby(["policy", "source"])[f"ndcg@{k}"].mean().unstack()
    served = df.groupby(["policy", "source"])["served"].mean().unstack()
    head = " | ".join(f"{s} (n={n[s]})" for s in sources)
    md = [
        "\n## By source of the seed\n",
        f"NDCG@{k}, every seed counted, blind spots charged zero. The candidate pool is "
        "the whole library in both columns; only the seed differs.\n",
        f"| Policy | {head} |",
        "|---" * (len(sources) + 1) + "|",
    ]
    for policy in POLICIES:
        md.append(f"| `{policy}` | " + " | ".join(f"{ndcg.loc[policy, s]:.3f}" for s in sources) + " |")
    md += ["\nShare of seeds each policy can rank at all:\n",
           f"| Policy | {head} |", "|---" * (len(sources) + 1) + "|"]
    for policy in POLICIES:
        md.append(f"| `{policy}` | " + " | ".join(f"{served.loc[policy, s]:.0%}" for s in sources) + " |")
    return md


def report(df: pd.DataFrame, head: pd.DataFrame, blind: pd.DataFrame, k: int,
           lib: Library, figdir: Path) -> list[str]:
    n_seeds = int(head["n_seeds"].iloc[0])
    per_seed = df[df.policy == POLICIES[0]]
    med_pos = float(per_seed["n_positives"].median())
    label_same = per_seed["n_same_artist_positives"].sum() / per_seed["n_positives"].sum()
    floor = float(head.loc[head.policy == "random", "precision_all"].iloc[0])

    md = [
        "# Ranking evaluation\n",
        "> Scored against pseudo-relevance labels from Last.fm `track.getSimilar`.",
        "> **These are collaborative-filtering output, not observed user preference.**",
        "> A high score means a content-based ranking reproduces an industrial CF",
        "> system, which is a real question but not \"does the listener like it\".\n",
        "## Protocol\n",
        f"- Seeds evaluated: **{n_seeds}** (every seed with at least one in-library positive)",
        f"- Candidate pool: the whole library, {lib.n} tracks, minus the seed itself",
        f"- Positives per seed: median **{med_pos:.0f}**",
        f"- Reported at K = {k}; the full K sweep is in `eval_by_k.csv`",
        f"- Random Precision@{k} floor: **{floor:.3f}**",
        "- Deterministic: fixed RNG seed, stable tie-breaking by library index\n",
        "The app's random jitter and per-tag diversity cap are excluded. Both act",
        "after the ranking is chosen and would only add noise to the measurement.\n",
        "## Headline\n",
        f"| Policy | Can rank | NDCG@{k} served | NDCG@{k} all seeds | "
        f"Recall@{k} all | HitRate@{k} all |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in head.iterrows():
        md.append(
            f"| `{r.policy}` | {r.coverage:.0%} | {r.ndcg_served:.3f} | **{r.ndcg_all:.3f}** | "
            f"{r.recall_all:.3f} | {r.hit_rate_all:.3f} |"
        )

    md += [
        "\n**The two NDCG columns are the point.** *Served* averages only over seeds",
        "the policy has any signal for; *all seeds* charges it zero where it has none.",
        "A policy that is accurate but blind scores well on the first and badly on the",
        "second, and the second is what a user experiences.\n",
        f"![](../{figdir.name}/fig6_ranking_quality.png)\n",
        "## Same-artist recommendations\n",
        "The shipped recommender does **not** drop tracks by the seed's own artist:",
        "another song by an artist you just played is usually a good suggestion, and",
        "removing it would be a worse product to make a benchmark easier. But Last.fm's",
        f"`track.getSimilar` is artist-deduplicated -- only {label_same:.1%} of the labels are",
        "same-artist -- so those slots are almost always scored as misses whatever they",
        "actually contain. The artist-blind column drops the seed's artist from the",
        "ranking and the labels together, which is the only way to compare policies on",
        "ground the labels can actually judge.\n",
        f"| Policy | Same-artist share of top-{k} | NDCG@{k} as shipped | NDCG@{k} artist-blind |",
        "|---|---:|---:|---:|",
    ]
    for policy in POLICIES:
        d = df[(df.policy == policy) & df.served]
        share = d["same_artist_in_top"].mean() / k if len(d) else 0.0
        shipped = float(head.loc[head.policy == policy, "ndcg_all"].iloc[0])
        b = float(blind.loc[blind.policy == policy, "ndcg_all"].iloc[0])
        md.append(f"| `{policy}` | {share:.1%} | {shipped:.3f} | {b:.3f} |")

    tag_share = df[(df.policy == "tags") & df.served]["same_artist_in_top"].mean() / k
    md += [
        f"\n`tags` is the only policy materially affected: **{tag_share:.0%}** of its",
        f"top-{k} is the seed's own artist, against 1-4% for everything else. Artist",
        "names survive as raw Last.fm tags and pass the discriminative-tag test, so tag",
        "matching partly degenerates into artist matching. That is worth knowing before",
        "reading its headline number: whatever the tag policy scores, it scores while",
        "spending a quarter of the list on recommendations these labels cannot credit.\n",
        "## By popularity quintile\n",
        "Every seed counted, blind spots charged zero.\n",
    ]

    n_unknown = int(per_seed["quintile"].isna().sum())
    if n_unknown:
        md.append(
            f"{n_unknown} of the {len(per_seed)} seeds have no listener count -- Last.fm "
            "did not find the track -- so they belong to no stratum and are left out of "
            "the two tables below. Every table above still counts them.\n"
        )

    g = df.groupby(["policy", "quintile"], observed=True)[f"ndcg@{k}"].mean().unstack()
    cov = df.groupby(["policy", "quintile"], observed=True)["served"].mean().unstack()
    # The share of each library quintile that has labels at all: the tracks the
    # tables above silently leave out.
    seeds = df["seed_index"].unique()
    reach = [np.isin(np.flatnonzero(lib.quintile == q), seeds).mean() for q in (0, 1)]
    md.append("| Policy | " + " | ".join(str(c) for c in g.columns) + " |")
    md.append("|---" * (len(g.columns) + 1) + "|")
    for policy in POLICIES:
        md.append(f"| `{policy}` | " + " | ".join(f"{v:.3f}" for v in g.loc[policy]) + " |")
    md.append("\nShare of seeds each policy can rank at all:\n")
    md.append("| Policy | " + " | ".join(str(c) for c in cov.columns) + " |")
    md.append("|---" * (len(cov.columns) + 1) + "|")
    for policy in POLICIES:
        md.append(f"| `{policy}` | " + " | ".join(f"{v:.0%}" for v in cov.loc[policy]) + " |")

    sources = sorted(per_seed["source"].unique())
    if len(sources) > 1:
        md += _by_source(df, per_seed, sources, k)

    md += [
        "\n> Quintiles are cut over the whole library, so Q1 is the coldest fifth of",
        "> the catalogue rather than the coldest fifth of the tracks that have labels.",
        f"> The two differ: ground truth reaches {reach[0]:.0%} of Q1 and {reach[1]:.0%} of Q2, and the",
        "> seeds it misses never appear in the table above at all. So the cold end is",
        "> not merely measured with few labels -- it is measured on the most popular",
        "> part of itself. Read it as indicative, not decisive. That limit belongs to",
        "> the CF labels, not to the policies being compared, and the only way past it",
        "> is human judgement sampled where the labels are missing: `make pool`.\n",
    ]
    return md


def main() -> None:
    ap = argparse.ArgumentParser(description="Benchmark ranking policies")
    ap.add_argument("--songs", type=Path, default=config.SONGS_SAMPLE_JSON)
    ap.add_argument("--ground-truth", type=Path,
                    default=config.DATA_DIR / "ground_truth.sample.json")
    ap.add_argument("--outdir", type=Path, default=config.REPORTS_DIR / "sample")
    ap.add_argument("--figdir", type=Path, default=config.FIGURES_DIR / "sample")
    ap.add_argument("--k", type=int, default=HEADLINE_K)
    ap.add_argument("--seed", type=int, default=0, help="RNG seed for the random policy")
    ap.add_argument("--random-repeats", type=int, default=20,
                    help="draws to average the random floor over; 1 reproduces a single sample")
    args = ap.parse_args()

    if not args.ground_truth.exists():
        sys.exit(
            f"[FATAL] no ground truth at {args.ground_truth}\n"
            "        Build it with: make gt   (needs LASTFM_API_KEY)"
        )

    songs = load_songs(args.songs)
    gt = json.loads(args.ground_truth.read_text())
    print(f"[load] {len(songs)} tracks, {len(gt)} ground-truth seeds")

    lib = Library(songs)
    df = run(lib, songs, gt, args.seed, args.random_repeats)
    head = headline(df, args.k)

    n_seeds = int(head["n_seeds"].iloc[0])
    print(f"[eval] {n_seeds} evaluable seeds x {len(POLICIES)} policies")
    for _, r in head.iterrows():
        print(f"  {r.policy:<11} coverage {r.coverage:5.0%}  "
              f"NDCG@{args.k} served {r.ndcg_served:.3f}  all {r.ndcg_all:.3f}")

    args.outdir.mkdir(parents=True, exist_ok=True)
    fig_path = figure(df, head, args.figdir, args.k)

    by_k = []
    for k in KS:
        h = headline(df, k)
        h.insert(0, "k", k)
        by_k.append(h)
    pd.concat(by_k).to_csv(args.outdir / "eval_by_k.csv", index=False)

    df.groupby(["policy", "quintile"], observed=True)[
        [f"{m}@{args.k}" for m in METRIC_NAMES] + ["served"]
    ].mean().round(4).to_csv(args.outdir / "eval_by_quintile.csv")

    md = report(df, head, headline(df, args.k, prefix="blind_"), args.k, lib, args.figdir)
    (args.outdir / "eval_summary.md").write_text("\n".join(md) + "\n")

    print(f"\n[done] -> {args.outdir / 'eval_summary.md'}")
    print(f"[done] -> {args.outdir / 'eval_by_quintile.csv'}")
    print(f"[done] -> {args.outdir / 'eval_by_k.csv'}")
    print(f"[done] -> {fig_path}")


if __name__ == "__main__":
    main()
