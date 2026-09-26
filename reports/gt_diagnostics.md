# Ground-truth diagnostics

> Last.fm `track.getSimilar` intersected with the local library.
> **These labels come from collaborative filtering, not from observed user preference.**

---

## Density

- Seeds: **1258**
- With at least one positive: **1021** (81.2%)
- Positives per seed: mean **36.2** / median **37** / p75 59
- Relative to library size, 2.9% of the corpus is labelled relevant for an average seed
  -> **a random recommender's expected Precision@10 is ~2.9%**. Any method must clear this floor before it means anything.

## Diagnostic 1 — same-artist contamination

- Share of positives by the seed's own artist: **2.2%** (1012/45601)
- Median per-seed share: **2.0%**

> Acceptable — same-artist positives are not driving the labels.

## Diagnostic 2 — popularity bias

| | median listeners |
|---|---:|
| Whole library | 93,286 |
| Positive samples | 225,243 |

Positives are about **2.4x** as popular as the corpus median. The CF labels lean heavily toward the head, so a popularity baseline will be strong and must be reported. If a content-based method cannot beat it, that is the finding.

## Diagnostic 3 — evaluation reliability by popularity quintile

| Quintile | Tracks | With positives | Mean positives | Reliability |
|---|---:|---:|---:|---|
| Q1 | 254 | 43% | 11.1 | **Not reliable** |
| Q2 | 253 | 63% | 19.8 | Treat with caution |
| Q3 | 254 | 100% | 49.4 | Reliable |
| Q4 | 253 | 99% | 52.6 | Reliable |
| Q5 | 253 | 98% | 47.1 | Reliable |

> Quintiles with low coverage are blind spots of the offline benchmark and must be labelled as such wherever results are reported. Closing them requires human relevance judgements, not more CF labels.


---
## Density after removing same-artist positives

- With at least one positive: 1018/1258 (80.9%)
- Positives per seed: mean 35.4 / median 36
