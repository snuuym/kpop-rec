# SQL cross-check

> Every number below was recomputed from `kpoprec.db` (built from `songs.json` and `ground_truth.json`)
> by the queries in `sql/checks/`, with no pandas or numpy involved, and
> compared with the report that published it. A printed number matches
> when the SQL value rounds to it; the benchmark CSVs are held to 1e-9.

**197 numbers checked: all match.**

## tag_sparsity_summary.md

| Number | Published | SQL | |
|---|---:|---:|:---:|
| Verified untagged (backfill asked, nobody tagged) | 920 | 920 | ✓ |
| Unverified empty tag lists | 0 | 0 | ✓ |
| Tagged with root tags only | 1 | 1 | ✓ |
| Has an effective tag | 346 | 346 | ✓ |
| Corpus size | 1267 | 1267 | ✓ |
| Mean raw tags per track | 2.7 | 2.7 | ✓ |
| Mean effective tags per track | 1.9 | 1.9 | ✓ |
| Median effective tags | 0 | 0 | ✓ |
| Tracks with no effective tag | 921 | 921 | ✓ |
| ... as a share (%) | 72.7 | 72.7 | ✓ |
| Tracks with 2 or fewer (%) | 73.0 | 73.0 | ✓ |
| Carrying a sub-genre label (%) | 100.0 | 100.0 | ✓ |
| Unique tags | 844 | 844 | ✓ |
| Tags on exactly one track | 567 | 567 | ✓ |
| First pass: tracks | 315 | 315 | ✓ |
| First pass: median listeners | 447,745 | 447,745 | ✓ |
| Backfill: tracks | 952 | 952 | ✓ |
| Backfill: median listeners | 47,012 | 47,012 | ✓ |
| First pass / backfill popularity (x) | 9.5 | 9.5 | ✓ |
| Regression sample | 1098 | 1098 | ✓ |
| Year: univariate r | +0.382 | 0.382 | ✓ |
| Year: partial beta | +0.152 | 0.152 | ✓ |
| log10(listeners): univariate r | +0.620 | 0.620 | ✓ |
| log10(listeners): partial beta | +0.557 | 0.557 | ✓ |
| Model R^2 | 0.403 | 0.403 | ✓ |
| no tags: no audio features | 106 | 106 | ✓ |
| no tags: has audio features | 815 | 815 | ✓ |
| no tags: feature coverage (%) | 88.5 | 88.5 | ✓ |
| has tags: no audio features | 54 | 54 | ✓ |
| has tags: has audio features | 292 | 292 | ✓ |
| has tags: feature coverage (%) | 84.4 | 84.4 | ✓ |
| Unreachable by any content signal | 106 | 106 | ✓ |
| ... as a share (%) | 8.4 | 8.4 | ✓ |
| Overall audio-feature coverage (%) | 87.4 | 87.4 | ✓ |
| Q1 coldest: tag coverage (%) | 0 | 0 | ✓ |
| Q1 coldest: audio-feature coverage (%) | 84 | 84 | ✓ |
| Q2: tag coverage (%) | 0 | 0 | ✓ |
| Q2: audio-feature coverage (%) | 93 | 93 | ✓ |
| Q3: tag coverage (%) | 9 | 9 | ✓ |
| Q3: audio-feature coverage (%) | 85 | 85 | ✓ |
| Q4: tag coverage (%) | 33 | 33 | ✓ |
| Q4: audio-feature coverage (%) | 87 | 87 | ✓ |
| Q5 hottest: tag coverage (%) | 94 | 94 | ✓ |
| Q5 hottest: audio-feature coverage (%) | 89 | 89 | ✓ |
| Tag coverage spread (pp) | 94 | 94 | ✓ |
| Feature coverage spread (pp) | 9 | 9 | ✓ |

## tag_vocabulary.csv

| Number | Published | SQL | |
|---|---:|---:|:---:|
| Every tag's document frequency, in rank order | 844 tags | 844 tags, 0 differ | ✓ |

## gt_diagnostics.md

| Number | Published | SQL | |
|---|---:|---:|:---:|
| Seeds in the label file | 1258 | 1258 | ✓ |
| Seeds with a positive | 1021 | 1021 | ✓ |
| ... as a share (%) | 81.2 | 81.2 | ✓ |
| Positives per seed: mean | 36.2 | 36.2 | ✓ |
| Positives per seed: median | 37 | 37 | ✓ |
| Positives per seed: p75 | 59 | 59 | ✓ |
| Random Precision@10 floor (%) | 2.9 | 2.9 | ✓ |
| Same-artist share of positives (%) | 2.2 | 2.2 | ✓ |
| Same-artist positives | 1012 | 1012 | ✓ |
| All positives | 45601 | 45601 | ✓ |
| Median per-seed same-artist share (%) | 2.0 | 2.0 | ✓ |
| Median listeners, library | 93,286 | 93,286 | ✓ |
| Median listeners, positives | 225,243 | 225,243 | ✓ |
| Positives / library popularity (x) | 2.4 | 2.4 | ✓ |
| Q1: tracks | 254 | 254 | ✓ |
| Q1: share with a positive (%) | 43 | 43 | ✓ |
| Q1: mean positives | 11.1 | 11.1 | ✓ |
| Q2: tracks | 253 | 253 | ✓ |
| Q2: share with a positive (%) | 63 | 63 | ✓ |
| Q2: mean positives | 19.8 | 19.8 | ✓ |
| Q3: tracks | 254 | 254 | ✓ |
| Q3: share with a positive (%) | 100 | 100 | ✓ |
| Q3: mean positives | 49.4 | 49.4 | ✓ |
| Q4: tracks | 253 | 253 | ✓ |
| Q4: share with a positive (%) | 99 | 99 | ✓ |
| Q4: mean positives | 52.6 | 52.6 | ✓ |
| Q5: tracks | 253 | 253 | ✓ |
| Q5: share with a positive (%) | 98 | 98 | ✓ |
| Q5: mean positives | 47.1 | 47.1 | ✓ |
| No same-artist labels: seeds with a positive | 1018 | 1018 | ✓ |
| No same-artist labels: mean positives | 35.4 | 35.4 | ✓ |
| No same-artist labels: median positives | 36 | 36 | ✓ |

## eval_by_k.csv and eval_by_quintile.csv

| Number | Published | SQL | |
|---|---:|---:|:---:|
| `eval_by_k.csv`: every policy, every k, every metric | 220 values | max \|Δ\| = 1.1e-16 | ✓ |
| `eval_by_quintile.csv`: every policy, every quintile | 125 values | 4 places, max \|Δ\| = 0 | ✓ |

## eval_summary.md

| Number | Published | SQL | |
|---|---:|---:|:---:|
| Seeds evaluated | 1021 | 1021 | ✓ |
| Candidate pool | 1267 | 1267 | ✓ |
| Positives per seed: median | 49 | 49 | ✓ |
| Random Precision@10 floor | 0.035 | 0.035 | ✓ |
| Same-artist share of labels (%) | 2.2 | 2.2 | ✓ |
| `random`: same-artist share of top-10 (%) | 1.4 | 1.4 | ✓ |
| `random`: NDCG@10 artist-blind | 0.035 | 0.035 | ✓ |
| `popularity`: same-artist share of top-10 (%) | 2.5 | 2.5 | ✓ |
| `popularity`: NDCG@10 artist-blind | 0.071 | 0.071 | ✓ |
| `tags`: same-artist share of top-10 (%) | 26.6 | 26.6 | ✓ |
| `tags`: NDCG@10 artist-blind | 0.070 | 0.070 | ✓ |
| `acoustic`: same-artist share of top-10 (%) | 2.5 | 2.5 | ✓ |
| `acoustic`: NDCG@10 artist-blind | 0.045 | 0.045 | ✓ |
| `hybrid`: same-artist share of top-10 (%) | 3.5 | 3.5 | ✓ |
| `hybrid`: NDCG@10 artist-blind | 0.056 | 0.056 | ✓ |
| `tags`: same-artist share, in the prose (%) | 27 | 27 | ✓ |
| Q1 seeds with a label (%) | 43 | 43 | ✓ |
| Q2 seeds with a label (%) | 63 | 63 | ✓ |

## README.md

| Number | Published | SQL | |
|---|---:|---:|:---:|
| Corpus with no usable tag (%) | 72.7 | 72.7 | ✓ |
| Unreachable by any content signal (%) | 8.4 | 8.4 | ✓ |
| Q1: tag coverage (%) | 0 | 0 | ✓ |
| Q1: acoustic coverage (%) | 84 | 84 | ✓ |
| Q2: tag coverage (%) | 0 | 0 | ✓ |
| Q2: acoustic coverage (%) | 93 | 93 | ✓ |
| Q3: tag coverage (%) | 9 | 9 | ✓ |
| Q3: acoustic coverage (%) | 85 | 85 | ✓ |
| Q4: tag coverage (%) | 33 | 33 | ✓ |
| Q4: acoustic coverage (%) | 87 | 87 | ✓ |
| Q5: tag coverage (%) | 94 | 94 | ✓ |
| Q5: acoustic coverage (%) | 89 | 89 | ✓ |
| Tag coverage swing (pp) | 94 | 94 | ✓ |
| Acoustic coverage swing (pp) | 9 | 9 | ✓ |
| Regression sample | 1,098 | 1,098 | ✓ |
| Year: univariate | +0.382 | 0.382 | ✓ |
| Year: partial | +0.152 | 0.152 | ✓ |
| log10(listeners): univariate | +0.620 | 0.620 | ✓ |
| log10(listeners): partial | +0.557 | 0.557 | ✓ |
| Zero-tag share, releases before 2010 (%) | 91 | 91 | ✓ |
| Zero-tag share, 2023 and later (%) | 39 | 39 | ✓ |
| First pass / backfill popularity (x) | 9.5 | 9.5 | ✓ |
| Labels / corpus popularity (x) | 2.4 | 2.4 | ✓ |
| `random`: can rank (%) | 100 | 100 | ✓ |
| `random`: NDCG@10 where it can | 0.036 | 0.036 | ✓ |
| `random`: NDCG@10 over every seed | 0.036 | 0.036 | ✓ |
| `random`: NDCG@5 | 0.036 | 0.036 | ✓ |
| `random`: NDCG@10 | 0.036 | 0.036 | ✓ |
| `random`: NDCG@20 | 0.036 | 0.036 | ✓ |
| `random`: NDCG@50 | 0.041 | 0.041 | ✓ |
| `random`: same-artist share of top-10 (%) | 1.4 | 1.4 | ✓ |
| `random`: NDCG@10 artist-blind | 0.035 | 0.035 | ✓ |
| `random`: NDCG@10 in Q1 coldest | 0.022 | 0.022 | ✓ |
| `random`: NDCG@10 in Q2 | 0.024 | 0.024 | ✓ |
| `random`: NDCG@10 in Q3 | 0.040 | 0.040 | ✓ |
| `random`: NDCG@10 in Q4 | 0.041 | 0.041 | ✓ |
| `random`: NDCG@10 in Q5 hottest | 0.039 | 0.039 | ✓ |
| `popularity`: can rank (%) | 100 | 100 | ✓ |
| `popularity`: NDCG@10 where it can | 0.072 | 0.072 | ✓ |
| `popularity`: NDCG@10 over every seed | 0.072 | 0.072 | ✓ |
| `popularity`: NDCG@5 | 0.062 | 0.062 | ✓ |
| `popularity`: NDCG@10 | 0.072 | 0.072 | ✓ |
| `popularity`: NDCG@20 | 0.071 | 0.071 | ✓ |
| `popularity`: NDCG@50 | 0.070 | 0.070 | ✓ |
| `popularity`: same-artist share of top-10 (%) | 2.5 | 2.5 | ✓ |
| `popularity`: NDCG@10 artist-blind | 0.071 | 0.071 | ✓ |
| `popularity`: NDCG@10 in Q1 coldest | 0.006 | 0.006 | ✓ |
| `popularity`: NDCG@10 in Q2 | 0.011 | 0.011 | ✓ |
| `popularity`: NDCG@10 in Q3 | 0.044 | 0.044 | ✓ |
| `popularity`: NDCG@10 in Q4 | 0.094 | 0.094 | ✓ |
| `popularity`: NDCG@10 in Q5 hottest | 0.144 | 0.144 | ✓ |
| `tags`: can rank (%) | 33 | 33 | ✓ |
| `tags`: NDCG@10 where it can | 0.201 | 0.201 | ✓ |
| `tags`: NDCG@10 over every seed | 0.067 | 0.067 | ✓ |
| `tags`: NDCG@5 | 0.076 | 0.076 | ✓ |
| `tags`: NDCG@10 | 0.067 | 0.067 | ✓ |
| `tags`: NDCG@20 | 0.062 | 0.062 | ✓ |
| `tags`: NDCG@50 | 0.058 | 0.058 | ✓ |
| `tags`: same-artist share of top-10 (%) | 26.6 | 26.6 | ✓ |
| `tags`: NDCG@10 artist-blind | 0.070 | 0.070 | ✓ |
| `tags`: NDCG@10 in Q1 coldest | 0.000 | 0.000 | ✓ |
| `tags`: NDCG@10 in Q2 | 0.000 | 0.000 | ✓ |
| `tags`: NDCG@10 in Q3 | 0.017 | 0.017 | ✓ |
| `tags`: NDCG@10 in Q4 | 0.061 | 0.061 | ✓ |
| `tags`: NDCG@10 in Q5 hottest | 0.196 | 0.196 | ✓ |
| `acoustic`: can rank (%) | 87 | 87 | ✓ |
| `acoustic`: NDCG@10 where it can | 0.054 | 0.054 | ✓ |
| `acoustic`: NDCG@10 over every seed | 0.047 | 0.047 | ✓ |
| `acoustic`: NDCG@5 | 0.048 | 0.048 | ✓ |
| `acoustic`: NDCG@10 | 0.047 | 0.047 | ✓ |
| `acoustic`: NDCG@20 | 0.045 | 0.045 | ✓ |
| `acoustic`: NDCG@50 | 0.047 | 0.047 | ✓ |
| `acoustic`: same-artist share of top-10 (%) | 2.5 | 2.5 | ✓ |
| `acoustic`: NDCG@10 artist-blind | 0.045 | 0.045 | ✓ |
| `acoustic`: NDCG@10 in Q1 coldest | 0.035 | 0.035 | ✓ |
| `acoustic`: NDCG@10 in Q2 | 0.034 | 0.034 | ✓ |
| `acoustic`: NDCG@10 in Q3 | 0.057 | 0.057 | ✓ |
| `acoustic`: NDCG@10 in Q4 | 0.055 | 0.055 | ✓ |
| `acoustic`: NDCG@10 in Q5 hottest | 0.043 | 0.043 | ✓ |
| `hybrid`: can rank (%) | 92 | 92 | ✓ |
| `hybrid`: NDCG@10 where it can | 0.063 | 0.063 | ✓ |
| `hybrid`: NDCG@10 over every seed | 0.058 | 0.058 | ✓ |
| `hybrid`: NDCG@5 | 0.062 | 0.062 | ✓ |
| `hybrid`: NDCG@10 | 0.058 | 0.058 | ✓ |
| `hybrid`: NDCG@20 | 0.056 | 0.056 | ✓ |
| `hybrid`: NDCG@50 | 0.059 | 0.059 | ✓ |
| `hybrid`: same-artist share of top-10 (%) | 3.5 | 3.5 | ✓ |
| `hybrid`: NDCG@10 artist-blind | 0.056 | 0.056 | ✓ |
| `hybrid`: NDCG@10 in Q1 coldest | 0.037 | 0.037 | ✓ |
| `hybrid`: NDCG@10 in Q2 | 0.036 | 0.036 | ✓ |
| `hybrid`: NDCG@10 in Q3 | 0.065 | 0.065 | ✓ |
| `hybrid`: NDCG@10 in Q4 | 0.060 | 0.060 | ✓ |
| `hybrid`: NDCG@10 in Q5 hottest | 0.073 | 0.073 | ✓ |
| Q1 coldest: seeds with a label (%) | 43 | 43 | ✓ |
| Q2: seeds with a label (%) | 63 | 63 | ✓ |
| Q3: seeds with a label (%) | 100 | 100 | ✓ |
| Q4: seeds with a label (%) | 99 | 99 | ✓ |
| Q5 hottest: seeds with a label (%) | 98 | 98 | ✓ |
