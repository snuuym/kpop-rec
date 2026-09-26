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
- Random Precision@10 floor: **0.035**
- Deterministic: fixed RNG seed, stable tie-breaking by library index

The app's random jitter and per-tag diversity cap are excluded. Both act
after the ranking is chosen and would only add noise to the measurement.

## Headline

| Policy | Can rank | NDCG@10 served | NDCG@10 all seeds | Recall@10 all | HitRate@10 all |
|---|---:|---:|---:|---:|---:|
| `random` | 100% | 0.036 | **0.036** | 0.008 | 0.294 |
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
| `random` | 1.4% | 0.036 | 0.035 |
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
| `random` | 0.022 | 0.024 | 0.040 | 0.041 | 0.039 |
| `popularity` | 0.006 | 0.011 | 0.044 | 0.094 | 0.144 |
| `tags` | 0.000 | 0.000 | 0.017 | 0.061 | 0.196 |
| `acoustic` | 0.035 | 0.034 | 0.057 | 0.055 | 0.043 |
| `hybrid` | 0.037 | 0.036 | 0.065 | 0.060 | 0.073 |

Share of seeds each policy can rank at all:

| Policy | Q1 coldest | Q2 | Q3 | Q4 | Q5 hottest |
|---|---|---|---|---|---|
| `random` | 100% | 100% | 100% | 100% | 100% |
| `popularity` | 100% | 100% | 100% | 100% | 100% |
| `tags` | 0% | 0% | 8% | 33% | 94% |
| `acoustic` | 80% | 94% | 85% | 87% | 89% |
| `hybrid` | 80% | 94% | 91% | 92% | 99% |

> Quintiles are cut over the whole library, so Q1 is the coldest fifth of
> the catalogue rather than the coldest fifth of the tracks that have labels.
> The two differ: ground truth reaches 43% of Q1 and 63% of Q2, and the
> seeds it misses never appear in the table above at all. So the cold end is
> not merely measured with few labels -- it is measured on the most popular
> part of itself. Read it as indicative, not decisive. That limit belongs to
> the CF labels, not to the policies being compared, and the only way past it
> is human judgement sampled where the labels are missing: `make pool`.

