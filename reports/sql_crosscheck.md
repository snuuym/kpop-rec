# SQL cross-check

> Every number below was recomputed from `kpoprec.db` (built from `songs.json` and `ground_truth.json`)
> by the queries in `sql/checks/`, with no pandas or numpy involved, and
> compared with the report that published it. A printed number matches
> when the SQL value rounds to it; the benchmark CSVs are held to 1e-9.

**396 numbers checked: all match.**

## tag_sparsity_summary.md

| Number | Published | SQL | |
|---|---:|---:|:---:|
| Verified untagged (backfill asked, nobody tagged) | 1461 | 1461 | ✓ |
| Unverified empty tag lists | 0 | 0 | ✓ |
| Tagged with root tags only | 3 | 3 | ✓ |
| Has an effective tag | 428 | 428 | ✓ |
| Corpus size | 1892 | 1892 | ✓ |
| Mean raw tags per track | 2.2 | 2.2 | ✓ |
| Mean effective tags per track | 1.6 | 1.6 | ✓ |
| Median effective tags | 0 | 0 | ✓ |
| Tracks with no effective tag | 1464 | 1464 | ✓ |
| ... as a share (%) | 77.4 | 77.4 | ✓ |
| Tracks with 2 or fewer (%) | 77.7 | 77.7 | ✓ |
| Carrying a sub-genre label (%) | 100.0 | 100.0 | ✓ |
| Unique tags | 1013 | 1013 | ✓ |
| Tags on exactly one track | 672 | 672 | ✓ |
| First pass: tracks | 315 | 315 | ✓ |
| First pass: median listeners | 449,255 | 449,255 | ✓ |
| Backfill: tracks | 952 | 952 | ✓ |
| Backfill: median listeners | 47,530 | 47,530 | ✓ |
| First pass / backfill popularity (x) | 9.5 | 9.5 | ✓ |
| Regression sample | 1657 | 1657 | ✓ |
| Year: univariate r | +0.194 | 0.194 | ✓ |
| Year: partial beta | +0.087 | 0.087 | ✓ |
| log10(listeners): univariate r | +0.572 | 0.572 | ✓ |
| log10(listeners): partial beta | +0.555 | 0.555 | ✓ |
| Model R^2 | 0.334 | 0.334 | ✓ |
| no tags: no audio features | 301 | 301 | ✓ |
| no tags: has audio features | 1163 | 1163 | ✓ |
| no tags: feature coverage (%) | 79.4 | 79.4 | ✓ |
| has tags: no audio features | 90 | 90 | ✓ |
| has tags: has audio features | 338 | 338 | ✓ |
| has tags: feature coverage (%) | 79.0 | 79.0 | ✓ |
| Unreachable by any content signal | 301 | 301 | ✓ |
| ... as a share (%) | 15.9 | 15.9 | ✓ |
| Overall audio-feature coverage (%) | 79.3 | 79.3 | ✓ |
| Q1 coldest: tag coverage (%) | 0 | 0 | ✓ |
| Q1 coldest: audio-feature coverage (%) | 72 | 72 | ✓ |
| Q2: tag coverage (%) | 2 | 2 | ✓ |
| Q2: audio-feature coverage (%) | 75 | 75 | ✓ |
| Q3: tag coverage (%) | 8 | 8 | ✓ |
| Q3: audio-feature coverage (%) | 78 | 78 | ✓ |
| Q4: tag coverage (%) | 21 | 21 | ✓ |
| Q4: audio-feature coverage (%) | 84 | 84 | ✓ |
| Q5 hottest: tag coverage (%) | 82 | 82 | ✓ |
| Q5 hottest: audio-feature coverage (%) | 87 | 87 | ✓ |
| Tag coverage spread (pp) | 82 | 82 | ✓ |
| Feature coverage spread (pp) | 15 | 15 | ✓ |
| lastfm_tag: tracks | 1267 | 1267 | ✓ |
| lastfm_tag: no effective tag (%) | 72.7 | 72.7 | ✓ |
| lastfm_tag: audio-feature coverage (%) | 87.4 | 87.4 | ✓ |
| lastfm_tag: listener count known (%) | 100.0 | 100.0 | ✓ |
| lastfm_tag: median listeners | 94,136 | 94,136 | ✓ |
| lastfm_tag: year resolved (%) | 86.8 | 86.8 | ✓ |
| lastfm_tag: median year | 2018 | 2018 | ✓ |
| spotify_playlist: tracks | 625 | 625 | ✓ |
| spotify_playlist: no effective tag (%) | 86.9 | 86.9 | ✓ |
| spotify_playlist: audio-feature coverage (%) | 63.0 | 63.0 | ✓ |
| spotify_playlist: listener count known (%) | 99.8 | 99.8 | ✓ |
| spotify_playlist: median listeners | 54,236 | 54,236 | ✓ |
| spotify_playlist: year resolved (%) | 89.4 | 89.4 | ✓ |
| spotify_playlist: median year | 2024 | 2024 | ✓ |
| Q1 coldest, lastfm_tag: tracks | 290 | 290 | ✓ |
| Q1 coldest, lastfm_tag: tag coverage (%) | 0 | 0 | ✓ |
| Q1 coldest, lastfm_tag: audio coverage (%) | 85 | 85 | ✓ |
| Q1 coldest, spotify_playlist: tracks | 89 | 89 | ✓ |
| Q1 coldest, spotify_playlist: tag coverage (%) | 0 | 0 | ✓ |
| Q1 coldest, spotify_playlist: audio coverage (%) | 31 | 31 | ✓ |
| Q2, lastfm_tag: tracks | 193 | 193 | ✓ |
| Q2, lastfm_tag: tag coverage (%) | 0 | 0 | ✓ |
| Q2, lastfm_tag: audio coverage (%) | 94 | 94 | ✓ |
| Q2, spotify_playlist: tracks | 185 | 185 | ✓ |
| Q2, spotify_playlist: tag coverage (%) | 4 | 4 | ✓ |
| Q2, spotify_playlist: audio coverage (%) | 55 | 55 | ✓ |
| Q3, lastfm_tag: tracks | 180 | 180 | ✓ |
| Q3, lastfm_tag: tag coverage (%) | 6 | 6 | ✓ |
| Q3, lastfm_tag: audio coverage (%) | 86 | 86 | ✓ |
| Q3, spotify_playlist: tracks | 198 | 198 | ✓ |
| Q3, spotify_playlist: tag coverage (%) | 11 | 11 | ✓ |
| Q3, spotify_playlist: audio coverage (%) | 71 | 71 | ✓ |
| Q4, lastfm_tag: tracks | 261 | 261 | ✓ |
| Q4, lastfm_tag: tag coverage (%) | 20 | 20 | ✓ |
| Q4, lastfm_tag: audio coverage (%) | 87 | 87 | ✓ |
| Q4, spotify_playlist: tracks | 117 | 117 | ✓ |
| Q4, spotify_playlist: tag coverage (%) | 23 | 23 | ✓ |
| Q4, spotify_playlist: audio coverage (%) | 79 | 79 | ✓ |
| Q5 hottest, lastfm_tag: tracks | 343 | 343 | ✓ |
| Q5 hottest, lastfm_tag: tag coverage (%) | 83 | 83 | ✓ |
| Q5 hottest, lastfm_tag: audio coverage (%) | 87 | 87 | ✓ |
| Q5 hottest, spotify_playlist: tracks | 35 | 35 | ✓ |
| Q5 hottest, spotify_playlist: tag coverage (%) | 77 | 77 | ✓ |
| Q5 hottest, spotify_playlist: audio coverage (%) | 86 | 86 | ✓ |
| regression, all: tracks | 1657 | 1657 | ✓ |
| regression, all: year (partial) | +0.087 | 0.087 | ✓ |
| regression, all: log10(listeners) (partial) | +0.555 | 0.555 | ✓ |
| regression, all: R^2 | 0.334 | 0.334 | ✓ |
| regression, lastfm_tag: tracks | 1099 | 1099 | ✓ |
| regression, lastfm_tag: year (partial) | +0.152 | 0.152 | ✓ |
| regression, lastfm_tag: log10(listeners) (partial) | +0.556 | 0.556 | ✓ |
| regression, lastfm_tag: R^2 | 0.402 | 0.402 | ✓ |
| regression, spotify_playlist: tracks | 558 | 558 | ✓ |
| regression, spotify_playlist: year (partial) | +0.141 | 0.141 | ✓ |
| regression, spotify_playlist: log10(listeners) (partial) | +0.396 | 0.396 | ✓ |
| regression, spotify_playlist: R^2 | 0.171 | 0.171 | ✓ |

## tag_vocabulary.csv

| Number | Published | SQL | |
|---|---:|---:|:---:|
| Every tag's document frequency, in rank order | 1013 tags | 1013 tags, 0 differ | ✓ |

## gt_diagnostics.md

| Number | Published | SQL | |
|---|---:|---:|:---:|
| Seeds in the label file | 1883 | 1883 | ✓ |
| Seeds with a positive | 1587 | 1587 | ✓ |
| ... as a share (%) | 84.3 | 84.3 | ✓ |
| Positives per seed: mean | 38.5 | 38.5 | ✓ |
| Positives per seed: median | 40 | 40 | ✓ |
| Positives per seed: p75 | 62 | 62 | ✓ |
| Random Precision@10 floor (%) | 2.0 | 2.0 | ✓ |
| Same-artist share of positives (%) | 2.5 | 2.5 | ✓ |
| Same-artist positives | 1821 | 1821 | ✓ |
| All positives | 72588 | 72588 | ✓ |
| Median per-seed same-artist share (%) | 2.5 | 2.5 | ✓ |
| Median listeners, library | 70,551 | 70,551 | ✓ |
| Median listeners, positives | 197,698 | 197,698 | ✓ |
| Positives / library popularity (x) | 2.8 | 2.8 | ✓ |
| Q1: tracks | 379 | 379 | ✓ |
| Q1: share with a positive (%) | 47 | 47 | ✓ |
| Q1: mean positives | 10.9 | 10.9 | ✓ |
| Q2: tracks | 378 | 378 | ✓ |
| Q2: share with a positive (%) | 76 | 76 | ✓ |
| Q2: mean positives | 22.5 | 22.5 | ✓ |
| Q3: tracks | 378 | 378 | ✓ |
| Q3: share with a positive (%) | 98 | 98 | ✓ |
| Q3: mean positives | 46.4 | 46.4 | ✓ |
| Q4: tracks | 378 | 378 | ✓ |
| Q4: share with a positive (%) | 99 | 99 | ✓ |
| Q4: mean positives | 56.3 | 56.3 | ✓ |
| Q5: tracks | 378 | 378 | ✓ |
| Q5: share with a positive (%) | 98 | 98 | ✓ |
| Q5: mean positives | 55.9 | 55.9 | ✓ |
| No same-artist labels: seeds with a positive | 1576 | 1576 | ✓ |
| No same-artist labels: mean positives | 37.6 | 37.6 | ✓ |
| No same-artist labels: median positives | 39 | 39 | ✓ |

## eval_by_k.csv and eval_by_quintile.csv

| Number | Published | SQL | |
|---|---:|---:|:---:|
| `eval_by_k.csv`: every policy, every k, every metric | 220 values | max \|Δ\| = 1.1e-16 | ✓ |
| `eval_by_quintile.csv`: every policy, every quintile | 125 values | 4 places, max \|Δ\| = 0 | ✓ |

## eval_summary.md

| Number | Published | SQL | |
|---|---:|---:|:---:|
| Seeds evaluated | 1587 | 1587 | ✓ |
| Candidate pool | 1892 | 1892 | ✓ |
| Positives per seed: median | 49 | 49 | ✓ |
| Random Precision@10 floor | 0.025 | 0.025 | ✓ |
| Same-artist share of labels (%) | 2.5 | 2.5 | ✓ |
| `random`: same-artist share of top-10 (%) | 1.1 | 1.1 | ✓ |
| `random`: NDCG@10 artist-blind | 0.024 | 0.024 | ✓ |
| `popularity`: same-artist share of top-10 (%) | 1.6 | 1.6 | ✓ |
| `popularity`: NDCG@10 artist-blind | 0.059 | 0.059 | ✓ |
| `tags`: same-artist share of top-10 (%) | 21.3 | 21.3 | ✓ |
| `tags`: NDCG@10 artist-blind | 0.060 | 0.060 | ✓ |
| `acoustic`: same-artist share of top-10 (%) | 2.2 | 2.2 | ✓ |
| `acoustic`: NDCG@10 artist-blind | 0.031 | 0.031 | ✓ |
| `hybrid`: same-artist share of top-10 (%) | 3.1 | 3.1 | ✓ |
| `hybrid`: NDCG@10 artist-blind | 0.044 | 0.044 | ✓ |
| `tags`: same-artist share, in the prose (%) | 21 | 21 | ✓ |
| Q1 seeds with a label (%) | 47 | 47 | ✓ |
| Q2 seeds with a label (%) | 76 | 76 | ✓ |
| lastfm_tag: seeds | 1021 | 1021 | ✓ |
| spotify_playlist: seeds | 566 | 566 | ✓ |
| `random`, lastfm_tag: NDCG@10 | 0.027 | 0.027 | ✓ |
| `random`, spotify_playlist: NDCG@10 | 0.020 | 0.020 | ✓ |
| `random`, lastfm_tag: can rank (%) | 100 | 100 | ✓ |
| `random`, spotify_playlist: can rank (%) | 100 | 100 | ✓ |
| `popularity`, lastfm_tag: NDCG@10 | 0.061 | 0.061 | ✓ |
| `popularity`, spotify_playlist: NDCG@10 | 0.052 | 0.052 | ✓ |
| `popularity`, lastfm_tag: can rank (%) | 100 | 100 | ✓ |
| `popularity`, spotify_playlist: can rank (%) | 100 | 100 | ✓ |
| `tags`, lastfm_tag: NDCG@10 | 0.072 | 0.072 | ✓ |
| `tags`, spotify_playlist: NDCG@10 | 0.031 | 0.031 | ✓ |
| `tags`, lastfm_tag: can rank (%) | 33 | 33 | ✓ |
| `tags`, spotify_playlist: can rank (%) | 13 | 13 | ✓ |
| `acoustic`, lastfm_tag: NDCG@10 | 0.038 | 0.038 | ✓ |
| `acoustic`, spotify_playlist: NDCG@10 | 0.020 | 0.020 | ✓ |
| `acoustic`, lastfm_tag: can rank (%) | 87 | 87 | ✓ |
| `acoustic`, spotify_playlist: can rank (%) | 65 | 65 | ✓ |
| `hybrid`, lastfm_tag: NDCG@10 | 0.051 | 0.051 | ✓ |
| `hybrid`, spotify_playlist: NDCG@10 | 0.033 | 0.033 | ✓ |
| `hybrid`, lastfm_tag: can rank (%) | 92 | 92 | ✓ |
| `hybrid`, spotify_playlist: can rank (%) | 70 | 70 | ✓ |

## README.md

| Number | Published | SQL | |
|---|---:|---:|:---:|
| Corpus with no usable tag (%) | 77.4 | 77.4 | ✓ |
| Unreachable by any content signal (%) | 15.9 | 15.9 | ✓ |
| Q1: tag coverage (%) | 0 | 0 | ✓ |
| Q1: acoustic coverage (%) | 72 | 72 | ✓ |
| Q2: tag coverage (%) | 2 | 2 | ✓ |
| Q2: acoustic coverage (%) | 75 | 75 | ✓ |
| Q3: tag coverage (%) | 8 | 8 | ✓ |
| Q3: acoustic coverage (%) | 78 | 78 | ✓ |
| Q4: tag coverage (%) | 21 | 21 | ✓ |
| Q4: acoustic coverage (%) | 84 | 84 | ✓ |
| Q5: tag coverage (%) | 82 | 82 | ✓ |
| Q5: acoustic coverage (%) | 87 | 87 | ✓ |
| Tag coverage swing (pp) | 82 | 82 | ✓ |
| Acoustic coverage swing (pp) | 15 | 15 | ✓ |
| Regression sample | 1,657 | 1,657 | ✓ |
| Year: univariate | +0.194 | 0.194 | ✓ |
| Year: partial | +0.087 | 0.087 | ✓ |
| log10(listeners): univariate | +0.572 | 0.572 | ✓ |
| log10(listeners): partial | +0.555 | 0.555 | ✓ |
| Zero-tag share, releases before 2010 (%) | 92 | 92 | ✓ |
| Zero-tag share, 2023 and later (%) | 69 | 69 | ✓ |
| First pass / backfill popularity (x) | 9.5 | 9.5 | ✓ |
| Labels / corpus popularity (x) | 2.8 | 2.8 | ✓ |
| `random`: can rank (%) | 100 | 100 | ✓ |
| `random`: NDCG@10 where it can | 0.025 | 0.025 | ✓ |
| `random`: NDCG@10 over every seed | 0.025 | 0.025 | ✓ |
| `random`: NDCG@5 | 0.024 | 0.024 | ✓ |
| `random`: NDCG@10 | 0.025 | 0.025 | ✓ |
| `random`: NDCG@20 | 0.025 | 0.025 | ✓ |
| `random`: NDCG@50 | 0.028 | 0.028 | ✓ |
| `random`: same-artist share of top-10 (%) | 1.1 | 1.1 | ✓ |
| `random`: NDCG@10 artist-blind | 0.024 | 0.024 | ✓ |
| `random`: NDCG@10 in Q1 coldest | 0.013 | 0.013 | ✓ |
| `random`: NDCG@10 in Q2 | 0.015 | 0.015 | ✓ |
| `random`: NDCG@10 in Q3 | 0.026 | 0.026 | ✓ |
| `random`: NDCG@10 in Q4 | 0.030 | 0.030 | ✓ |
| `random`: NDCG@10 in Q5 hottest | 0.031 | 0.031 | ✓ |
| `popularity`: can rank (%) | 100 | 100 | ✓ |
| `popularity`: NDCG@10 where it can | 0.058 | 0.058 | ✓ |
| `popularity`: NDCG@10 over every seed | 0.058 | 0.058 | ✓ |
| `popularity`: NDCG@5 | 0.062 | 0.062 | ✓ |
| `popularity`: NDCG@10 | 0.058 | 0.058 | ✓ |
| `popularity`: NDCG@20 | 0.064 | 0.064 | ✓ |
| `popularity`: NDCG@50 | 0.058 | 0.058 | ✓ |
| `popularity`: same-artist share of top-10 (%) | 1.6 | 1.6 | ✓ |
| `popularity`: NDCG@10 artist-blind | 0.059 | 0.059 | ✓ |
| `popularity`: NDCG@10 in Q1 coldest | 0.004 | 0.004 | ✓ |
| `popularity`: NDCG@10 in Q2 | 0.012 | 0.012 | ✓ |
| `popularity`: NDCG@10 in Q3 | 0.047 | 0.047 | ✓ |
| `popularity`: NDCG@10 in Q4 | 0.075 | 0.075 | ✓ |
| `popularity`: NDCG@10 in Q5 hottest | 0.113 | 0.113 | ✓ |
| `tags`: can rank (%) | 26 | 26 | ✓ |
| `tags`: NDCG@10 where it can | 0.219 | 0.219 | ✓ |
| `tags`: NDCG@10 over every seed | 0.057 | 0.057 | ✓ |
| `tags`: NDCG@5 | 0.067 | 0.067 | ✓ |
| `tags`: NDCG@10 | 0.057 | 0.057 | ✓ |
| `tags`: NDCG@20 | 0.051 | 0.051 | ✓ |
| `tags`: NDCG@50 | 0.043 | 0.043 | ✓ |
| `tags`: same-artist share of top-10 (%) | 21.3 | 21.3 | ✓ |
| `tags`: NDCG@10 artist-blind | 0.060 | 0.060 | ✓ |
| `tags`: NDCG@10 in Q1 coldest | 0.000 | 0.000 | ✓ |
| `tags`: NDCG@10 in Q2 | 0.001 | 0.001 | ✓ |
| `tags`: NDCG@10 in Q3 | 0.018 | 0.018 | ✓ |
| `tags`: NDCG@10 in Q4 | 0.042 | 0.042 | ✓ |
| `tags`: NDCG@10 in Q5 hottest | 0.183 | 0.183 | ✓ |
| `acoustic`: can rank (%) | 79 | 79 | ✓ |
| `acoustic`: NDCG@10 where it can | 0.040 | 0.040 | ✓ |
| `acoustic`: NDCG@10 over every seed | 0.031 | 0.031 | ✓ |
| `acoustic`: NDCG@5 | 0.032 | 0.032 | ✓ |
| `acoustic`: NDCG@10 | 0.031 | 0.031 | ✓ |
| `acoustic`: NDCG@20 | 0.031 | 0.031 | ✓ |
| `acoustic`: NDCG@50 | 0.032 | 0.032 | ✓ |
| `acoustic`: same-artist share of top-10 (%) | 2.2 | 2.2 | ✓ |
| `acoustic`: NDCG@10 artist-blind | 0.031 | 0.031 | ✓ |
| `acoustic`: NDCG@10 in Q1 coldest | 0.023 | 0.023 | ✓ |
| `acoustic`: NDCG@10 in Q2 | 0.018 | 0.018 | ✓ |
| `acoustic`: NDCG@10 in Q3 | 0.033 | 0.033 | ✓ |
| `acoustic`: NDCG@10 in Q4 | 0.042 | 0.042 | ✓ |
| `acoustic`: NDCG@10 in Q5 hottest | 0.035 | 0.035 | ✓ |
| `hybrid`: can rank (%) | 84 | 84 | ✓ |
| `hybrid`: NDCG@10 where it can | 0.053 | 0.053 | ✓ |
| `hybrid`: NDCG@10 over every seed | 0.044 | 0.044 | ✓ |
| `hybrid`: NDCG@5 | 0.048 | 0.048 | ✓ |
| `hybrid`: NDCG@10 | 0.044 | 0.044 | ✓ |
| `hybrid`: NDCG@20 | 0.042 | 0.042 | ✓ |
| `hybrid`: NDCG@50 | 0.041 | 0.041 | ✓ |
| `hybrid`: same-artist share of top-10 (%) | 3.1 | 3.1 | ✓ |
| `hybrid`: NDCG@10 artist-blind | 0.044 | 0.044 | ✓ |
| `hybrid`: NDCG@10 in Q1 coldest | 0.024 | 0.024 | ✓ |
| `hybrid`: NDCG@10 in Q2 | 0.019 | 0.019 | ✓ |
| `hybrid`: NDCG@10 in Q3 | 0.046 | 0.046 | ✓ |
| `hybrid`: NDCG@10 in Q4 | 0.055 | 0.055 | ✓ |
| `hybrid`: NDCG@10 in Q5 hottest | 0.062 | 0.062 | ✓ |
| Q1 coldest: seeds with a label (%) | 47 | 47 | ✓ |
| Q2: seeds with a label (%) | 76 | 76 | ✓ |
| Q3: seeds with a label (%) | 98 | 98 | ✓ |
| Q4: seeds with a label (%) | 99 | 99 | ✓ |
| Q5 hottest: seeds with a label (%) | 98 | 98 | ✓ |
| Library size | 1,892 | 1,892 | ✓ |
| Last.fm tracks | 1,267 | 1,267 | ✓ |
| Playlist tracks | 625 | 625 | ✓ |
| Pseudo-relevance labels | 72,588 | 72,588 | ✓ |
| Untagged, queried individually | 1,461 | 1,461 | ✓ |
| Untagged, in all | 1,464 | 1,464 | ✓ |
| Tracks, Last.fm | 1,267 | 1,267 | ✓ |
| Tracks, playlists | 625 | 625 | ✓ |
| Median release year, Last.fm | 2018 | 2018 | ✓ |
| Median release year, playlists | 2024 | 2024 | ✓ |
| Median listeners, Last.fm | 94,136 | 94,136 | ✓ |
| Median listeners, playlists | 54,236 | 54,236 | ✓ |
| No effective tag, Last.fm | 72.7 | 72.7 | ✓ |
| No effective tag, playlists | 86.9 | 86.9 | ✓ |
| Audio features, Last.fm | 87.4 | 87.4 | ✓ |
| Audio features, playlists | 63.0 | 63.0 | ✓ |
| Q1 (coldest): tag coverage, Last.fm (%) | 0 | 0 | ✓ |
| Q1 (coldest): tag coverage, playlists (%) | 0 | 0 | ✓ |
| Q1 (coldest): audio coverage, Last.fm (%) | 85 | 85 | ✓ |
| Q1 (coldest): audio coverage, playlists (%) | 31 | 31 | ✓ |
| Q2: tag coverage, Last.fm (%) | 0 | 0 | ✓ |
| Q2: tag coverage, playlists (%) | 4 | 4 | ✓ |
| Q2: audio coverage, Last.fm (%) | 94 | 94 | ✓ |
| Q2: audio coverage, playlists (%) | 55 | 55 | ✓ |
| Q3: tag coverage, Last.fm (%) | 6 | 6 | ✓ |
| Q3: tag coverage, playlists (%) | 11 | 11 | ✓ |
| Q3: audio coverage, Last.fm (%) | 86 | 86 | ✓ |
| Q3: audio coverage, playlists (%) | 71 | 71 | ✓ |
| Q4: tag coverage, Last.fm (%) | 20 | 20 | ✓ |
| Q4: tag coverage, playlists (%) | 23 | 23 | ✓ |
| Q4: audio coverage, Last.fm (%) | 87 | 87 | ✓ |
| Q4: audio coverage, playlists (%) | 79 | 79 | ✓ |
| Q5 (hottest): tag coverage, Last.fm (%) | 83 | 83 | ✓ |
| Q5 (hottest): tag coverage, playlists (%) | 77 | 77 | ✓ |
| Q5 (hottest): audio coverage, Last.fm (%) | 87 | 87 | ✓ |
| Q5 (hottest): audio coverage, playlists (%) | 86 | 86 | ✓ |
| regression, Last.fm tag pages: tracks | 1,099 | 1,099 | ✓ |
| regression, Last.fm tag pages: year (partial) | +0.152 | 0.152 | ✓ |
| regression, Last.fm tag pages: log10(listeners) (partial) | +0.556 | 0.556 | ✓ |
| regression, Owner's playlists: tracks | 558 | 558 | ✓ |
| regression, Owner's playlists: year (partial) | +0.141 | 0.141 | ✓ |
| regression, Owner's playlists: log10(listeners) (partial) | +0.396 | 0.396 | ✓ |
| regression, Pooled: tracks | 1,657 | 1,657 | ✓ |
| regression, Pooled: year (partial) | +0.087 | 0.087 | ✓ |
| regression, Pooled: log10(listeners) (partial) | +0.555 | 0.555 | ✓ |
| Features, released 2024 or earlier (%) | 90 | 90 | ✓ |
| ... tracks | 1,357 | 1,357 | ✓ |
| Features, released 2025 (%) | 50 | 50 | ✓ |
| ... tracks | 238 | 238 | ✓ |
| Features, released 2026 (%) | 11 | 11 | ✓ |
| ... tracks | 130 | 130 | ✓ |
| Unreachable, Last.fm (%) | 8.4 | 8.4 | ✓ |
| Unreachable, playlists (%) | 31.2 | 31.2 | ✓ |
| Unreachable, pooled (%) | 15.9 | 15.9 | ✓ |
| Seeds, Last.fm | 1021 | 1021 | ✓ |
| Seeds, playlists | 566 | 566 | ✓ |
| `random`, Last.fm seeds: NDCG@10 | 0.027 | 0.027 | ✓ |
| `random`, playlist seeds: NDCG@10 | 0.020 | 0.020 | ✓ |
| `popularity`, Last.fm seeds: NDCG@10 | 0.061 | 0.061 | ✓ |
| `popularity`, playlist seeds: NDCG@10 | 0.052 | 0.052 | ✓ |
| `tags`, Last.fm seeds: NDCG@10 | 0.072 | 0.072 | ✓ |
| `tags`, playlist seeds: NDCG@10 | 0.031 | 0.031 | ✓ |
| `acoustic`, Last.fm seeds: NDCG@10 | 0.038 | 0.038 | ✓ |
| `acoustic`, playlist seeds: NDCG@10 | 0.020 | 0.020 | ✓ |
| `hybrid`, Last.fm seeds: NDCG@10 | 0.051 | 0.051 | ✓ |
| `hybrid`, playlist seeds: NDCG@10 | 0.033 | 0.033 | ✓ |
| Last.fm seeds, tags | 0.072 | 0.072 | ✓ |
| Last.fm seeds, popularity | 0.061 | 0.061 | ✓ |
| Playlist seeds, tags | 0.031 | 0.031 | ✓ |
| Playlist seeds, popularity | 0.052 | 0.052 | ✓ |
| Tags can rank, playlist seeds (%) | 13 | 13 | ✓ |
| Tags can rank, Last.fm seeds (%) | 33 | 33 | ✓ |
| Acoustic can rank, playlist seeds (%) | 65 | 65 | ✓ |
| Acoustic can rank, Last.fm seeds (%) | 87 | 87 | ✓ |
| Tags vs popularity, every seed: tags | 0.057 | 0.057 | ✓ |
| Tags vs popularity, every seed: popularity | 0.058 | 0.058 | ✓ |
| Tags where a tag exists | 0.219 | 0.219 | ✓ |
| K=5: tags | 0.067 | 0.067 | ✓ |
| K=5: popularity | 0.062 | 0.062 | ✓ |
| Popularity keeps (%) | 97 | 97 | ✓ |
| Year loses (%) | 55 | 55 | ✓ |
| `tags` gains without its artist | 0.0025 | 0.0025 | ✓ |
| Precision multiple at 5 | 1.91 | 1.91 | ✓ |
| Precision multiple at 50 | 1.42 | 1.42 | ✓ |
| Hit rate at 5 (%) | 18 | 18 | ✓ |
| Hit rate at 50 (%) | 63 | 63 | ✓ |
| Random hit rate at 50 (%) | 65 | 65 | ✓ |
| Hit rate at 20 (%) | 43 | 43 | ✓ |
| Precision multiple at 20 | 1.61 | 1.61 | ✓ |
| Evaluable Q1 seeds | 178 | 178 | ✓ |
| Lowest of 20 draws | 0.008 | 0.008 | ✓ |
| Highest of 20 draws | 0.020 | 0.020 | ✓ |
| Popularity in Q1 | 0.004 | 0.004 | ✓ |
| Popularity's Q1 score is under every one of the draws | under all 20 | 0.0037 < 0.0083 | ✓ |
| Acoustic Q1 | 0.023 | 0.023 | ✓ |
| Hybrid Q1 | 0.024 | 0.024 | ✓ |
| Random floor Q1 | 0.013 | 0.013 | ✓ |
| Acoustic can rank, lowest (%) | 65 | 65 | ✓ |
| Acoustic can rank, highest (%) | 87 | 87 | ✓ |
| Hybrid can rank, lowest (%) | 65 | 65 | ✓ |
| Hybrid can rank, highest (%) | 97 | 97 | ✓ |
| Q1 seeds with a label, cold-end section (%) | 47 | 47 | ✓ |
| Candidate pool of the sample benchmark | 1,892 | 1,892 | ✓ |
| Q1 seeds with a label, limitation (%) | 47 | 47 | ✓ |
| ... the most popular share of itself (%) | 47 | 47 | ✓ |
| Year coverage (%) | 88 | 88 | ✓ |
| Year coverage, missing (%) | 12 | 12 | ✓ |
| Years resolved | 1,659 | 1,659 | ✓ |
| Coldest quintile years resolved (%) | 74 | 74 | ✓ |
| Hottest quintile years resolved (%) | 93 | 93 | ✓ |
| Unresolved tracks have under a third of the median listeners | under 1/3 | 0.31 | ✓ |
| Playlist share released 2023 or later (%) | 82 | 82 | ✓ |
| Feature coverage, 2025 (%), limitation | 50 | 50 | ✓ |
| Feature coverage, 2026 (%), limitation | 11 | 11 | ✓ |
| Zero-tag share, summary table (%) | 77.4 | 77.4 | ✓ |
| Tag spread, summary table (pp) | 82 | 82 | ✓ |
| Feature coverage through 2024, summary (%) | 90 | 90 | ✓ |
| Feature coverage 2026, summary (%) | 11 | 11 | ✓ |
| Unreachable, summary, Last.fm (%) | 8.4 | 8.4 | ✓ |
| Unreachable, summary, playlists (%) | 31.2 | 31.2 | ✓ |
| Tags vs baseline (x) | 3.8 | 3.8 | ✓ |
