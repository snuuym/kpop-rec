# Ranking evaluation

> Scored against pseudo-relevance labels from Last.fm `track.getSimilar`.
> **These are collaborative-filtering output, not observed user preference.**
> A high score means a content-based ranking reproduces an industrial CF
> system, which is a real question but not "does the listener like it".

## Protocol

- Seeds evaluated: **1021** (every seed with at least one in-library positive)
- Candidate pool: the whole library, 1267 tracks, minus the seed itself
- Positives per seed: median **49**
- Reported at K = 10; the full K sweep is in `eval_by_k.csv`
- Random Precision@10 floor: **0.034**
- Deterministic: fixed RNG seed, stable tie-breaking by library index

The app's random jitter and per-tag diversity cap are excluded. Both act
after the ranking is chosen and would only add noise to the measurement.

## Headline

| Policy | Can rank | NDCG@10 served | NDCG@10 all seeds | Recall@10 all | HitRate@10 all |
|---|---:|---:|---:|---:|---:|
| `random` | 100% | 0.034 | **0.034** | 0.007 | 0.285 |
| `popularity` | 100% | 0.072 | **0.072** | 0.016 | 0.414 |
| `tags` | 33% | 0.201 | **0.067** | 0.015 | 0.259 |
| `acoustic` | 87% | 0.054 | **0.047** | 0.011 | 0.348 |
| `hybrid` | 92% | 0.063 | **0.058** | 0.014 | 0.376 |

**The two NDCG columns are the point.** *Served* averages only over seeds
the policy has any signal for; *all seeds* charges it zero where it has none.
A policy that is accurate but blind scores well on the first and badly on the
second, and the second is what a user experiences.

![](../figures/fig6_ranking_quality.png)

## Same-artist recommendations

The shipped recommender does **not** drop tracks by the seed's own artist:
another song by an artist you just played is usually a good suggestion, and
removing it would be a worse product to make a benchmark easier. But Last.fm's
`track.getSimilar` is artist-deduplicated -- only 2.2% of the labels are
same-artist -- so those slots are almost always scored as misses whatever they
actually contain. The artist-blind column drops the seed's artist from the
ranking and the labels together, which is the only way to compare policies on
ground the labels can actually judge.

| Policy | Same-artist share of top-10 | NDCG@10 as shipped | NDCG@10 artist-blind |
|---|---:|---:|---:|
| `random` | 1.4% | 0.034 | 0.034 |
| `popularity` | 2.5% | 0.072 | 0.071 |
| `tags` | 26.6% | 0.067 | 0.070 |
| `acoustic` | 2.5% | 0.047 | 0.045 |
| `hybrid` | 3.5% | 0.058 | 0.056 |

`tags` is the only policy materially affected: **27%** of its
top-10 is the seed's own artist, against 1-4% for everything else. Artist
names survive as raw Last.fm tags and pass the discriminative-tag test, so tag
matching partly degenerates into artist matching. That is worth knowing before
reading its headline number: whatever the tag policy scores, it scores while
spending a quarter of the list on recommendations these labels cannot credit.

## By popularity quintile

Every seed counted, blind spots charged zero.

| Policy | Q1 coldest | Q2 | Q3 | Q4 | Q5 hottest |
|---|---|---|---|---|---|
| `random` | 0.016 | 0.036 | 0.039 | 0.039 | 0.040 |
| `popularity` | 0.007 | 0.024 | 0.066 | 0.110 | 0.151 |
| `tags` | 0.000 | 0.008 | 0.023 | 0.096 | 0.207 |
| `acoustic` | 0.036 | 0.049 | 0.055 | 0.054 | 0.041 |
| `hybrid` | 0.037 | 0.057 | 0.059 | 0.062 | 0.075 |

Share of seeds each policy can rank at all:

| Policy | Q1 coldest | Q2 | Q3 | Q4 | Q5 hottest |
|---|---|---|---|---|---|
| `random` | 100% | 100% | 100% | 100% | 100% |
| `popularity` | 100% | 100% | 100% | 100% | 100% |
| `tags` | 0% | 3% | 15% | 50% | 97% |
| `acoustic` | 87% | 89% | 87% | 85% | 89% |
| `hybrid` | 87% | 92% | 92% | 92% | 100% |

> Q1 and Q2 carry few labels per seed and are flagged unreliable in
> `gt_diagnostics.md` -- 43% and 64% of their seeds have any positive at all.
> Read the cold end as indicative, not decisive. That limit is a property of
> the CF labels, not of the policies being compared.

