# Cold-start recommendation for long-tail K-pop

**Problem.** Build content-based recommendations with no user interaction logs
and no audio-feature API — Spotify deprecated `audio-features` in November
2024 — for a catalogue where most tracks carry no usable metadata.

**Data.** 1,267 K-pop tracks pulled from Last.fm, enriched with listener counts
(Last.fm) and acoustic features (ReccoBeats), plus 45,601 pseudo-relevance
labels derived from `track.getSimilar` and intersected with the local library.

**Result.** User-generated tags are not a viable retrieval signal in the long
tail, and the failure is architectural rather than algorithmic. After removing
the four tags that every K-pop track carries, **72.7% of the corpus has no
usable tag at all** — verified track by track against the API, so this is a
real absence of tagging, not a gap in collection. Broken out by popularity, the
gap is total:

| Popularity quintile | UGC tag coverage | Acoustic feature coverage |
|---|---:|---:|
| Q1 (coldest) | **0%** | 84% |
| Q2 | **0%** | 93% |
| Q3 | 9% | 85% |
| Q4 | 33% | 87% |
| Q5 (hottest) | 94% | 89% |

Tag coverage swings **94 percentage points** across the distribution; acoustic
coverage swings **9**. A recommender built on tags cannot reach the tail because
the input features do not exist there — no amount of ranking work changes that.

![Signal coverage by popularity](figures/fig5_signal_coverage.png)

---

## Why this is the interesting question

The obvious reading of "new tracks have no tags" is that tagging lags release.
The data says otherwise, and this is the one claim worth testing rather than
asserting. Standardizing both predictors and regressing effective tag count on
them jointly, over the 1,098 tracks carrying both a listener count and a
release year inside the 1990-2026 sanity range:

| Predictor | Univariate | Partial |
|---|---:|---:|
| Release year | +0.382 | **+0.152** |
| log10(listeners) | +0.620 | **+0.557** |

Popularity barely moves when year is held constant — it keeps 90% of its
univariate association. Year loses 60% of its own once popularity is held
constant, so most of the apparent age effect was popularity in disguise. And
the residual year coefficient is *positive*: newer tracks carry slightly
**more** tags, which is the opposite of what a tagging-lag story predicts.

![Tags by release year](figures/fig2_tags_vs_year.png)

The right-hand panel is the tagging-lag hypothesis failing in one line: the
share of zero-tag tracks falls monotonically from 91% for pre-2010 releases to
39% for 2023-and-later. Older tracks have had fifteen years to accumulate tags
and still have none.

Tags are user-generated content, and they accumulate only where listeners
already are — which is precisely where a recommender is least needed.

One number makes the mechanism concrete. The first tagging pass traversed the
corpus in descending popularity order and was interrupted partway. The tracks
it had already reached turned out to be **9.5× more popular** (median listeners)
than the ones the backfill pass had to fill in later. The collection bug and the
research finding have the same cause.

That reframes the engineering problem. Scraping more tag sources has a low
ceiling. The effort belongs on signals that do not depend on anyone having
listened to the track first.

## What is actually established

Honest scope: this repository contains the data foundation, the exploratory
analysis, and a diagnosed offline benchmark. **It does not yet report ranking
metrics** — no Recall@K or NDCG numbers are claimed, because the evaluation
harness is not built. The recommendation logic that ships is the heuristic used
by the app (feature-distance nearest neighbour, falling back to tag overlap,
falling back to random).

| Claim | Status |
|---|---|
| 72.7% of tracks have zero effective tags | Measured, per-track API verified |
| Tag coverage is popularity-dependent (94pp spread) | Measured |
| Acoustic coverage is popularity-independent (9pp spread) | Measured |
| 8.4% of tracks are unreachable by any content signal | Measured |
| Sparsity is driven by obscurity, not novelty | Measured — partial coefficients +0.56 popularity vs +0.15 year |
| Content method beats a popularity baseline | **Not measured** |

## Limitations

These are load-bearing, not boilerplate.

1. **The relevance labels come from collaborative filtering.** Last.fm's
   `track.getSimilar` is CF output, not observed user preference. Anything
   scored against these labels measures *how closely a content-based method
   reproduces an industrial CF system* — a real question, but not "does the
   user like it".
2. **The coldest quintile cannot be evaluated offline.** Only 43% of Q1 seeds
   get any in-library positive at all, against 100% for Q3–Q5. The part of the
   catalogue this project is about is exactly the part the benchmark cannot
   score. Closing that needs human relevance judgements, not more CF labels.
3. **Positives skew 2.4× more popular than the corpus median**, so a pure
   popularity baseline will be strong and must be reported alongside any
   content-based method.
4. **The novelty-vs-obscurity regression covers 87% of the corpus, and the
   missing 13% is not random.** MusicBrainz resolves a release year for 1,099
   of 1,267 tracks, but its own coverage is popularity-dependent: 68% in the
   coldest quintile against 93% in the hottest, and unresolved tracks have
   one-eighth the median listeners of resolved ones. The regression therefore
   under-weights exactly the tail this project is about. The result is stable
   across the full corpus and the 200-track sample, but a stronger test needs a
   year source that does not thin out in the tail.
5. **Corpus size is ~1.3k tracks**, which bounds both label density and
   candidate-pool realism. Brute-force similarity is entirely adequate at this
   scale; an ANN index would be premature.

Full diagnostics: [`reports/gt_diagnostics.md`](reports/gt_diagnostics.md) ·
[`reports/tag_sparsity_summary.md`](reports/tag_sparsity_summary.md)

## Quickstart

```bash
git clone https://github.com/snuuym/kpop-rec.git
cd kpop-rec
make install
make test      # 64 tests, no network or credentials needed
make eval      # runs the full analysis on the bundled sample
```

`make eval` runs against `data/songs.sample.json` (200 tracks, stratified across
popularity quintiles), needs no API key, and writes to `reports/sample/` so it
never overwrites the committed full-corpus results. The sample reproduces the
headline finding closely — 74.0% zero-tag against 72.7% on the full corpus, a
98-point coverage spread against 94, and the same central regression result
(partial coefficients +0.54 popularity / +0.15 year, against +0.56 / +0.15 on
the full corpus).

To rebuild the full dataset:

```bash
cp .env.example .env    # fill in LASTFM_API_KEY
set -a && source .env && set +a
make all                # ~40 minutes, rate-limited, resumable
```

Every stage caches incrementally, so an interrupted run resumes where it
stopped rather than starting over.

## Pipeline

| Stage | Script | Produces |
|---|---|---|
| 1 | `build_library.py` | tracks + sub-genre labels from Last.fm |
| 2 | `backfill_tags.py` | tags the first pass missed, marked `tag_source` |
| 3 | `enrich_metadata.py` | listeners / playcount (Last.fm), year (MusicBrainz) |
| 4 | `build_features.py` | acoustic features via Spotify ID → ReccoBeats |
| — | `check_gt_density.py` | feasibility probe: is there enough ground truth? |
| 5 | `build_ground_truth.py` | pseudo-relevance labels + bias diagnostics |
| 6 | `analyze_tag_sparsity.py` | the EDA and every figure above |

Stage 2 exists because of stage 1's failure mode, and stage 5's diagnostics
exist because pseudo ground truth is easy to build and easy to over-trust. The
feasibility probe runs *before* the full ground-truth build so the benchmark
isn't committed to before its density is known.

## Layout

```
app/          single-file web UI + local Flask server
src/kpoprec/  shared library: taxonomy, normalization, Last.fm client, safe I/O
scripts/      the six pipeline stages, each a thin CLI
data/         sample dataset (full library is gitignored — see data/README.md)
reports/      generated analysis, committed so results are reviewable
figures/      generated charts
tests/        64 tests over taxonomy, joins, I/O, and request validation
```

Two design notes worth the words:

- **The taxonomy lives in one module.** Two pipeline stages classify tracks, and
  if they disagree the sparsity analysis is comparing two different label
  spaces. `src/kpoprec/taxonomy.py` is the single source of truth, and a test
  asserts no style rule keys on a root tag.
- **Normalization is a correctness concern, not a formatting one.** Ground truth
  is built by intersecting Last.fm's similar-track list against the local
  library. A weak join deflates the positive count, which is indistinguishable
  from "the labels are sparse" — so the join is centralised and tested.

## The app

A single HTML file with no build step: pick a seed track, get a 50-track queue,
play it through the Spotify Web Playback SDK, export it to a real playlist.

![screenshot](docs/demo/demo.png)

Search and generate:

![search and generate](docs/demo/demo-search.gif)

Saved playlists:

![saved playlists](docs/demo/demo-playlists.gif)

```bash
make app     # http://127.0.0.1:5000
```

The server exists for three reasons: `fetch()` cannot read the library from
`file://`; credentials are read from the environment and served to the page at
`/config.json` rather than baked into the HTML; and searching an off-library
track appends it through a single validated, deduplicated, atomically written
endpoint.

Playback needs a Spotify Premium account and a client ID registered with
`http://127.0.0.1:5000/kpop-mp3-player.html` as a redirect URI. Everything
except playback and export works without it.

## Stack

Python (requests, pandas, numpy, matplotlib, Flask) · vanilla JS front end, no
framework or bundler · [Last.fm](https://www.last.fm/api) for tags and
popularity · [ReccoBeats](https://reccobeats.com/) for acoustic features ·
[MusicBrainz](https://musicbrainz.org/) for release years. No database.

## License

MIT — see [LICENSE](LICENSE). The code is MIT; the underlying track metadata
belongs to Last.fm and its contributors, which is why this repository ships a
sample rather than the full extracted dataset.
