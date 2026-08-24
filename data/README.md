# Data

## What ships in this repository

| File | Tracked | Description |
|---|---|---|
| `songs.sample.json` | yes | 200-track sample of the library, stratified across popularity quintiles |
| `songs.json` | no | full library (~1,270 tracks) |
| `ground_truth.json` | no | pseudo relevance labels, seed -> positive keys |
| `ground_truth_no_same_artist.json` | no | same, with same-artist positives removed |
| `*_cache.json` | no | resumable-run caches |

## Why only a sample

The library is derived from the Last.fm API. Redistributing the full extracted
dataset is a different act from providing the code that builds it, so this
repository ships a sample sufficient to run and inspect the pipeline, and the
scripts to rebuild the rest:

```bash
export LASTFM_API_KEY=...   # see ../.env.example
make all                    # ~40 minutes, rate-limited
```

The sample is stratified by popularity rather than taken from the head, because
the entire analysis turns on how coverage differs between popular and obscure
tracks. A head-only sample would show none of the effect.

## Record schema

```jsonc
{
  "title":     "Epiphany",
  "artist":    "BTS",
  "tags":      ["Ballad"],              // classified sub-genres (taxonomy.py)
  "all_tags":  ["k-pop", "ballad"],     // raw Last.fm tags, the audit trail
  "dur":       240,                     // seconds
  "durStr":    "4:00",
  "url":       "https://www.last.fm/...",
  "spotify_id": "6L88EH68XwlaXwvChlTS41",  // present only if resolved
  "features":  {                        // ReccoBeats; absent when unresolved
    "danceability": 0.508, "energy": 0.559, "valence": 0.329,
    "tempo": 135.866, "acousticness": 0.2, "instrumentalness": 0.0,
    "loudness": -5.2, "speechiness": 0.05, "liveness": 0.1
  },
  "listeners": 412331,                  // Last.fm; the popularity axis
  "playcount": 8842190,
  "mbid":      "...",
  "year":      2018,                    // MusicBrainz first release
  "tag_source": "backfill"              // set when tags came from the second pass
}
```

Two fields carry more weight than their size suggests:

- **`listeners`** is the axis every stratified result is computed against.
  Without it there is no way to distinguish "tags are sparse" from "tags are
  sparse *in the tail*", which is the actual finding.
- **`tag_source`** marks records filled by `backfill_tags.py`. It exists so the
  selection bias introduced by an interrupted first pass can be measured rather
  than assumed away.

## Ground-truth format

```jsonc
{ "bts::epiphany": ["bts::magic shop", "rm::seoul", ...] }
```

Keys are normalized `artist::title` (see `src/kpoprec/normalize.py`). Read
`../reports/gt_diagnostics.md` before using these labels — they come from
collaborative filtering, not from observed user preference, and the coldest
popularity quintile is not reliably evaluable with them.
