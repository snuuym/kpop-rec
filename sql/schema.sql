-- The library, its labels and the benchmark's rankings, as relational tables.
--
-- songs.json stays the pipeline's source of truth: every stage writes it
-- atomically and resumes from it, and the committed sample is JSON. This
-- database is derived from it (`make db`) and exists to answer questions in
-- SQL -- above all, to recompute every published number independently of the
-- pandas/numpy code that produced it (`make sqlcheck`).
--
-- Tables hold what the JSON holds, losslessly (db.export_songs round-trips
-- it). Everything computed is defined once in SQL -- as a view here, or, for
-- the two sets the benchmark joins a million rows against, as a table filled
-- by sql/derive.sql -- so "effective tag" or "popularity quintile" means one
-- thing wherever it is used.

-- ── Library ─────────────────────────────────────────────────────────────────

-- Artist identity is normalize.norm(name). The benchmark compares
-- name.strip().lower() instead; on this library the two induce the same
-- partition, which db.load_library asserts rather than assumes.
CREATE TABLE artists (
    artist_id INTEGER PRIMARY KEY,
    name_norm TEXT NOT NULL UNIQUE
);

CREATE TABLE tracks (
    -- Position in songs.json. Every numpy array in the project is indexed the
    -- same way, so a track_id is directly comparable with a library index.
    track_id   INTEGER PRIMARY KEY,
    -- normalize.song_key(). Deliberately NOT unique: remix and feat. variants
    -- ("FAKE LOVE" / "FAKE LOVE (Rocking Vibe Mix)") normalize to one key.
    song_key   TEXT    NOT NULL,
    title      TEXT    NOT NULL,
    artist     TEXT    NOT NULL,             -- the credit as spelled
    artist_id  INTEGER NOT NULL REFERENCES artists,
    dur        INTEGER NOT NULL,             -- seconds
    url        TEXT,
    spotify_id TEXT,
    mbid       TEXT,
    year       INTEGER,
    listeners  INTEGER,
    playcount  INTEGER,
    tag_source TEXT CHECK (tag_source IN ('backfill'))
);
CREATE INDEX tracks_song_key ON tracks (song_key);
CREATE INDEX tracks_artist ON tracks (artist_id);

-- Raw Last.fm tags (all_tags), in order. tag_norm is normalize.normalize_tag()
-- of the raw text: SQLite's lower() folds ASCII only, so normalization stays
-- in the one Python module that defines it.
CREATE TABLE track_tags (
    track_id INTEGER NOT NULL REFERENCES tracks,
    ord      INTEGER NOT NULL,
    tag      TEXT    NOT NULL,
    tag_norm TEXT    NOT NULL,
    PRIMARY KEY (track_id, ord)
) WITHOUT ROWID;

-- Sub-genre labels from taxonomy.classify_subgenres (the JSON's `tags`).
CREATE TABLE track_genres (
    track_id INTEGER NOT NULL REFERENCES tracks,
    ord      INTEGER NOT NULL,
    genre    TEXT    NOT NULL,
    PRIMARY KEY (track_id, ord),
    UNIQUE (track_id, genre)
) WITHOUT ROWID;

-- taxonomy.NON_DISCRIMINATIVE_TAGS: tags every K-pop track carries.
CREATE TABLE non_discriminative_tags (
    tag TEXT PRIMARY KEY
) WITHOUT ROWID;

-- ReccoBeats features. A track without features has no row.
CREATE TABLE audio_features (
    track_id         INTEGER PRIMARY KEY REFERENCES tracks,
    danceability     REAL,
    energy           REAL,
    valence          REAL,
    tempo            REAL,
    acousticness     REAL,
    instrumentalness REAL,
    loudness         REAL,
    speechiness      REAL,
    liveness         REAL
);

-- ── Labels ──────────────────────────────────────────────────────────────────

-- ground_truth.json as stored: join keys, not yet resolved to tracks. A seed
-- whose list is empty still has a row in gt_seeds -- "has no positive" and
-- "was never a seed" are different facts.
CREATE TABLE gt_seeds (
    seed_key TEXT PRIMARY KEY
) WITHOUT ROWID;

CREATE TABLE ground_truth (
    seed_key     TEXT    NOT NULL REFERENCES gt_seeds,
    ord          INTEGER NOT NULL,
    positive_key TEXT    NOT NULL,
    PRIMARY KEY (seed_key, ord)
) WITHOUT ROWID;

-- ── Benchmark ───────────────────────────────────────────────────────────────

CREATE TABLE policies (
    policy TEXT PRIMARY KEY
) WITHOUT ROWID;

-- Each policy's ranking for each evaluable seed, produced by the same
-- recommend.score / top_k calls evaluate.py makes, `depth` deep or deeper
-- (see db.rank_rows). Only the ranking comes from Python; whether a seed is
-- evaluable, whether a policy can serve it, and every metric are recomputed
-- from here in SQL. Rankings are stored for every policy on every evaluable
-- seed, servable or not, so that serviceability is decided by the views
-- below and not inherited.
CREATE TABLE rankings (
    policy   TEXT    NOT NULL REFERENCES policies,
    seed_id  INTEGER NOT NULL REFERENCES tracks,
    draw     INTEGER NOT NULL,               -- > 0 only for `random`
    rank     INTEGER NOT NULL,               -- 1-based
    track_id INTEGER NOT NULL REFERENCES tracks,
    PRIMARY KEY (policy, seed_id, draw, rank)
) WITHOUT ROWID;

-- The cut-offs the benchmark reports.
CREATE TABLE ks (
    k INTEGER PRIMARY KEY
);

-- How the database was built: input paths, run seed, draws, depth.
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;

-- ── Derived, materialized ───────────────────────────────────────────────────
-- Filled by sql/derive.sql once the load is done, which is where their
-- definitions live. They are tables rather than views for one reason: the
-- benchmark joins a million ranking rows against them, and a view cannot
-- carry an index.

-- The labels resolved to tracks: distinct, and never the seed itself.
CREATE TABLE gt_positive (
    seed_id     INTEGER NOT NULL REFERENCES tracks,
    positive_id INTEGER NOT NULL REFERENCES tracks,
    PRIMARY KEY (seed_id, positive_id)
) WITHOUT ROWID;

-- NDCG's discount, 1 / log2(rank + 1), for every stored rank.
CREATE TABLE discount (
    rank INTEGER PRIMARY KEY,
    gain REAL NOT NULL
);

-- ── Derived: library ────────────────────────────────────────────────────────

-- One track per join key: the last in library order. That is how both
-- build_ground_truth ({key: song}) and pooling.evaluable_seeds ({key: index})
-- resolve a key, so the earlier tracks of a duplicated key are never seeds
-- and never positives.
CREATE VIEW key_owner AS
SELECT song_key, MAX(track_id) AS track_id
FROM tracks
GROUP BY song_key;

CREATE VIEW effective_tags AS
SELECT track_id, ord, tag_norm AS tag
FROM track_tags
WHERE tag_norm <> ''
  AND tag_norm NOT IN (SELECT tag FROM non_discriminative_tags);

-- Per-track signal counts. Counts are of list entries, duplicates included,
-- matching analyze_tag_sparsity.to_frame; only "is it zero" matters to the
-- benchmark, and duplicates cannot change that.
CREATE VIEW track_signals AS
SELECT t.track_id,
       COALESCE(r.n, 0)            AS n_raw,
       COALESCE(e.n, 0)            AS n_eff,
       COALESCE(g.n, 0)            AS n_classified,
       f.track_id IS NOT NULL      AS has_features
FROM tracks t
LEFT JOIN (SELECT track_id, COUNT(*) AS n FROM track_tags
           WHERE tag_norm <> '' GROUP BY track_id) r USING (track_id)
LEFT JOIN (SELECT track_id, COUNT(*) AS n FROM effective_tags
           GROUP BY track_id) e USING (track_id)
LEFT JOIN (SELECT track_id, COUNT(*) AS n FROM track_genres
           GROUP BY track_id) g USING (track_id)
LEFT JOIN audio_features f
       ON f.track_id = t.track_id AND f.danceability IS NOT NULL;

-- recommend.quintile_of, exactly: rank by listeners (missing = 0) with ties
-- broken by library position, then floor(rank * 5 / n). Not NTILE(5): when n
-- is not a multiple of five NTILE hands the spare tracks to the first groups,
-- and at n = 1,267 that moves one track into a different quintile.
CREATE VIEW track_quintile AS
SELECT track_id,
       (ROW_NUMBER() OVER (ORDER BY COALESCE(listeners, 0), track_id) - 1) * 5
           / COUNT(*) OVER () AS quintile
FROM tracks;
-- ── Derived: labels ─────────────────────────────────────────────────────────

CREATE VIEW evaluable_seed AS
SELECT seed_id, COUNT(*) AS n_positives
FROM gt_positive
GROUP BY seed_id;

-- ── Derived: benchmark ──────────────────────────────────────────────────────

-- recommend.can_serve: a policy with no signal for a seed does not rank it.
CREATE VIEW served AS
SELECT p.policy, e.seed_id,
       CASE p.policy
           WHEN 'tags'     THEN s.n_eff > 0
           WHEN 'acoustic' THEN s.has_features
           WHEN 'hybrid'   THEN s.has_features OR s.n_eff > 0
           ELSE 1
       END AS served
FROM policies p
CROSS JOIN evaluable_seed e
JOIN track_signals s ON s.track_id = e.seed_id;

-- metrics.evaluate_ranking under complete labels, for every policy, seed and
-- k: a ranked track is a hit iff it is a positive, and the ideal DCG puts
-- min(|positives|, k) hits at the top. Draws are averaged per seed, as the
-- harness averages the random floor. Where the policy cannot serve the seed
-- every metric is zero -- a blind spot is charged, not skipped.
CREATE VIEW seed_metrics AS
WITH hits AS (
    SELECT r.policy, r.seed_id, r.draw, k.k,
           COUNT(gp.positive_id)                                    AS n_hit,
           TOTAL(CASE WHEN gp.positive_id IS NOT NULL THEN d.gain END) AS dcg
    FROM rankings r
    JOIN ks k ON r.rank <= k.k
    JOIN discount d ON d.rank = r.rank
    LEFT JOIN gt_positive gp
           ON gp.seed_id = r.seed_id AND gp.positive_id = r.track_id
    GROUP BY r.policy, r.seed_id, r.draw, k.k
),
per_seed AS (
    SELECT h.policy, h.seed_id, h.k,
           AVG(1.0 * h.n_hit / e.n_positives) AS recall,
           AVG(1.0 * h.n_hit / h.k)           AS precision,
           AVG(h.n_hit > 0)                   AS hit_rate,
           AVG(h.dcg / (SELECT TOTAL(gain) FROM discount
                        WHERE rank <= MIN(e.n_positives, h.k))) AS ndcg
    FROM hits h
    JOIN evaluable_seed e ON e.seed_id = h.seed_id
    GROUP BY h.policy, h.seed_id, h.k
)
SELECT p.policy, p.seed_id, p.k, s.served,
       CASE WHEN s.served THEN p.recall    ELSE 0.0 END AS recall,
       CASE WHEN s.served THEN p.precision ELSE 0.0 END AS precision,
       CASE WHEN s.served THEN p.hit_rate  ELSE 0.0 END AS hit_rate,
       CASE WHEN s.served THEN p.ndcg      ELSE 0.0 END AS ndcg
FROM per_seed p
JOIN served s ON s.policy = p.policy AND s.seed_id = p.seed_id;

-- The artist-blind variant: the seed's own artist removed from the ranking
-- and from the positives, over the seeds that keep at least one positive.
-- The ranking is the stored one with those tracks filtered out and re-ranked;
-- setting their scores to -inf, as the harness does, leaves everyone else's
-- order untouched. Any positive that survives the filter is by construction
-- not the seed's artist, so hits need no second artist test. A filtered list
-- shorter than k cannot be scored from the stored depth and yields NULL.
CREATE VIEW seed_metrics_blind AS
WITH n_blind AS (
    SELECT gp.seed_id, COUNT(*) AS n_positives
    FROM gt_positive gp
    JOIN tracks s ON s.track_id = gp.seed_id
    JOIN tracks p ON p.track_id = gp.positive_id
    WHERE p.artist_id <> s.artist_id
    GROUP BY gp.seed_id
),
kept AS (
    SELECT r.policy, r.seed_id, r.draw, r.track_id,
           ROW_NUMBER() OVER (PARTITION BY r.policy, r.seed_id, r.draw
                              ORDER BY r.rank) AS rank
    FROM rankings r
    JOIN tracks s ON s.track_id = r.seed_id
    JOIN tracks c ON c.track_id = r.track_id
    WHERE c.artist_id <> s.artist_id
),
hits AS (
    SELECT kp.policy, kp.seed_id, kp.draw, k.k,
           COUNT(*)                                                 AS n_ranked,
           COUNT(gp.positive_id)                                    AS n_hit,
           TOTAL(CASE WHEN gp.positive_id IS NOT NULL THEN d.gain END) AS dcg
    FROM kept kp
    JOIN ks k ON kp.rank <= k.k
    JOIN discount d ON d.rank = kp.rank
    LEFT JOIN gt_positive gp
           ON gp.seed_id = kp.seed_id AND gp.positive_id = kp.track_id
    GROUP BY kp.policy, kp.seed_id, kp.draw, k.k
),
per_seed AS (
    SELECT h.policy, h.seed_id, h.k,
           CASE WHEN MIN(h.n_ranked) = h.k THEN
               AVG(h.dcg / (SELECT TOTAL(gain) FROM discount
                            WHERE rank <= MIN(b.n_positives, h.k)))
           END AS ndcg
    FROM hits h
    JOIN n_blind b ON b.seed_id = h.seed_id
    GROUP BY h.policy, h.seed_id, h.k
)
SELECT p.policy, p.seed_id, p.k, s.served,
       CASE WHEN s.served THEN p.ndcg ELSE 0.0 END AS ndcg
FROM per_seed p
JOIN served s ON s.policy = p.policy AND s.seed_id = p.seed_id;
