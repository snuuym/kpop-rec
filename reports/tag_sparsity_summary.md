# Tag sparsity analysis

> Generated from `songs.json` · 1267 tracks

---

## Data integrity

| Status | Tracks | Share | Meaning |
|---|---:|---:|---|
| Verified: nobody has tagged it | 920 | 72.6% | **genuine absence of UGC** (confirmed per track via the API) |
| Unverified empty `all_tags` | 0 | 0.0% | possibly a collection gap |
| Tagged, but only with root tags | 1 | 0.1% | **genuine UGC sparsity** |
| Has effective tags | 346 | 27.3% | usable |


> Empty tags were confirmed track by track against the Last.fm API: **this is genuine absence of UGC, not a gap in collection.**


## Q1 - How much signal survives removing root tags?

- Corpus size: **1267** tracks
- Raw tags average 2.7 per track; **effective tags average only 1.9** (median 0)
- **921 tracks (72.7%) have no effective tags at all** -> tag-based retrieval cannot reach them
- 925 tracks (73.0%) have 2 or fewer -> tag-overlap scoring barely discriminates between them
- Carrying a classified sub-genre label: 1267 (100.0%)

![](../figures/fig1_tag_count_distribution.png)

### Tag vocabulary

- Unique tags: **844**
- Tags appearing on exactly one track: **567** (67.2%) -> these contribute almost nothing to similarity, and are where TF-IDF weighting would gain over plain rule matching

| Tag | Tracks | Share | Root tag |
|---|---:|---:|:---:|
| `k-pop` | 329 | 26.0% | yes |
| `kpop` | 296 | 23.4% | yes |
| `korean` | 233 | 18.4% | yes |
| `pop` | 151 | 11.9% | yes |
| `bts` | 83 | 6.6% |  |
| `dance` | 69 | 5.4% |  |
| `dance-pop` | 56 | 4.4% |  |
| `electropop` | 55 | 4.3% |  |
| `julia mofada` | 46 | 3.6% |  |
| `rnb` | 41 | 3.2% |  |
| `rap` | 41 | 3.2% |  |
| `hip-hop` | 37 | 2.9% |  |
| `electronic` | 37 | 2.9% |  |
| `hip hop` | 34 | 2.7% |  |
| `trap` | 33 | 2.6% |  |
| `soty` | 32 | 2.5% |  |
| `pop rap` | 29 | 2.3% |  |
| `edm` | 25 | 2.0% |  |
| `fire` | 23 | 1.8% |  |
| `contemporary rnb` | 23 | 1.8% |  |
| `2023` | 20 | 1.6% |  |
| `2020` | 19 | 1.5% |  |
| `2016` | 19 | 1.5% |  |
| `house` | 18 | 1.4% |  |
| `synthpop` | 18 | 1.4% |  |

### Selection-bias check

The first tagging pass traversed the corpus in descending popularity order, so an interruption leaves a sample skewed toward the head:

| Group | Tracks | Median listeners |
|---|---:|---:|
| Tagged in the first pass | 315 | 447,745 |
| Filled in by backfill | 952 | 47,012 |

First-pass tracks are about **9.5x** as popular. **The bias is confirmed** — drawing conclusions from the first-pass sample alone would have badly overstated tag coverage. It is also independent evidence for the popularity-driven tagging hypothesis.

---

## Q2a - Tag sparsity vs release year

Sample: 1098 tracks with a known year.

![](../figures/fig2_tags_vs_year.png)

## Q2b - Tag sparsity vs popularity

Sample: 1267 tracks with a listener count.

![](../figures/fig3_tags_vs_popularity.png)

## Q2c - Is it novelty, or is it obscurity? (the central test)

Sample: 1098 tracks with both fields. All variables standardized, then regressed jointly:

| Predictor | Univariate correlation | Partial coefficient |
|---|---:|---:|
| Release year | +0.382 | **+0.152** |
| log10(listeners) | +0.620 | **+0.557** |

Model R^2 = 0.403

**Conclusion:** **Popularity dominates.** Once popularity is controlled for, the partial effect of release year collapses. "New tracks have no tags" is a surface reading of "obscure tracks have no tags" — tags are user-generated content, and they only accumulate where listeners do.

> This determines where further effort is worth spending. If sparsity is driven by popularity, scraping additional tag sources has a low ceiling, and the effort belongs on signals that do not depend on UGC at all — acoustic features, or features derived from the audio directly.

---

## Q3 - Does the fallback path hold up?

| Effective-tag bucket | No feature | Has feature | Total | Feature coverage |
|---|---:|---:|---:|---:|
| no tags | 106 | 815 | 921 | 88.5% |
| has tags | 54 | 292 | 346 | 84.4% |


- **Unreachable tracks: 106 (8.4%)** — no effective tags *and* no audio features. No content-based method can retrieve these; only a popularity fallback reaches them at all.
- Overall audio-feature coverage: 87.4%

![](../figures/fig4_coverage_crosstab.png)

> This table defines both the stratification used for evaluation and the retrieval cascade: features -> hybrid scoring, tags only -> TF-IDF, neither -> popularity.

## Central result - how each signal depends on popularity

| Quintile | UGC tag coverage | Audio-feature coverage |
|---|---:|---:|
| Q1 coldest | 0% | 84% |
| Q2 | 0% | 93% |
| Q3 | 9% | 85% |
| Q4 | 33% | 87% |
| Q5 hottest | 94% | 89% |

- UGC tag coverage varies by **94 percentage points** across quintiles — heavily popularity-dependent
- Acoustic feature coverage varies by only **9 points** — effectively popularity-independent

![](../figures/fig5_signal_coverage.png)

> **This is the argument.** UGC signal serves the head; acoustic signal covers the whole distribution. A recommender built only on the former cannot reach the long tail — not because its ranking is weak, but because the input features do not exist there. That is an architectural limit, not an algorithmic one.
