# Data

## What ships in this repository

| File | Tracked | Description |
|---|---|---|
| `songs.sample.json` | yes | 200-track sample of the library, stratified across popularity quintiles |
| `ground_truth.sample.json` | yes | labels for the sample, restricted to sample-internal positives |
| `songs.json` | no | full library: the Last.fm tag pull plus the owner's Spotify playlists (see `source`) |
| `playlist_tracks.json` | no | what the playlist import read, kept so a merge can be repeated without authorizing again; one person's listening |
| `ground_truth.json` | no | pseudo relevance labels, seed -> positive keys |
| `ground_truth_no_same_artist.json` | no | same, with same-artist positives removed |
| `*_cache.json` | no | resumable-run caches |
| `kpoprec.sample.db` | no | the sample, its labels and benchmark rankings in SQLite (`make db`) |
| `kpoprec.db` | no | the same for the full library (`make db-full`) |

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

`ground_truth.sample.json` is `ground_truth.json` restricted to the sample: the
same seeds, keeping only positives that are themselves in the sample. It is
derived, not separately collected --

```python
sub = {k: [p for p in gt[k] if p in sample_keys] for k in sample_keys if k in gt}
```

-- which leaves 162 evaluable seeds with a median of 9 positives each, enough
for `make bench` to run end to end on a fresh clone. Absolute scores are not
comparable to the full-corpus run: the candidate pool is 200 tracks rather than
1,267, so every metric sits higher. The *ordering* of the policies is what
carries over.

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
  "tag_source": "backfill",             // set when tags came from the second pass
  "source":    "spotify_playlist",      // how the track entered; absent = "lastfm_tag"
  "year_spotify": 2022                  // year of the album this copy sits on (playlist tracks)
}
```

Two fields carry more weight than their size suggests:

- **`listeners`** is the axis every stratified result is computed against.
  Without it there is no way to distinguish "tags are sparse" from "tags are
  sparse *in the tail*", which is the actual finding.
- **`source`** says how a track entered the library: `lastfm_tag` (the original
  pull from Last.fm's K-pop tag pages; the field is simply absent on those
  records, so the committed sample needs no rewriting) or `spotify_playlist`
  (added by `scripts/import_playlists.py`). The two are different samples, not
  one: the first is what someone tagged as K-pop, the second is what one
  listener chose. The analysis reports both pooled and split by this field.
- **`year_spotify`** is the release year of the album a playlist track sits on.
  It is not the same thing as `year`, which is MusicBrainz's *earliest* release
  of the recording: a reissue or compilation reads later on Spotify. They are
  kept apart rather than one overwriting the other.
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
