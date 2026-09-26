# Ground-truth diagnostics

> Last.fm `track.getSimilar` intersected with the local library.
> **These labels come from collaborative filtering, not from observed user preference.**

---

## Density

- Seeds: **1883**
- With at least one positive: **1587** (84.3%)
- Positives per seed: mean **38.5** / median **40** / p75 62
- Relative to library size, 2.0% of the corpus is labelled relevant for an average seed
  -> **a random recommender's expected Precision@10 is ~2.0%**. Any method must clear this floor before it means anything.

## Diagnostic 1 — same-artist contamination

- Share of positives by the seed's own artist: **2.5%** (1821/72588)
- Median per-seed share: **2.5%**

> Acceptable — same-artist positives are not driving the labels.

## Diagnostic 2 — popularity bias

| | median listeners |
|---|---:|
| Whole library | 70,551 |
| Positive samples | 197,698 |

Positives are about **2.8x** as popular as the corpus median. The CF labels lean heavily toward the head, so a popularity baseline will be strong and must be reported. If a content-based method cannot beat it, that is the finding.

## Diagnostic 3 — evaluation reliability by popularity quintile

| Quintile | Tracks | With positives | Mean positives | Reliability |
|---|---:|---:|---:|---|
| Q1 | 379 | 47% | 10.9 | **Not reliable** |
| Q2 | 378 | 76% | 22.5 | Treat with caution |
| Q3 | 378 | 98% | 46.4 | Reliable |
| Q4 | 378 | 99% | 56.3 | Reliable |
| Q5 | 378 | 98% | 55.9 | Reliable |

> Quintiles with low coverage are blind spots of the offline benchmark and must be labelled as such wherever results are reported. Closing them requires human relevance judgements, not more CF labels.


---
## Density after removing same-artist positives

- With at least one positive: 1576/1883 (83.7%)
- Positives per seed: mean 37.6 / median 39
