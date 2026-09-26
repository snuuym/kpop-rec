-- build_ground_truth.diagnose, density: of every seed in the label file, how
-- many have a positive, and how many each -- with the seed's own artist
-- (as built) and without it (ground_truth_no_same_artist.json).
WITH per_seed AS (
    SELECT g.seed_key,
           COUNT(gp.positive_id)                             AS n_all,
           COUNT(CASE WHEN p.artist_id <> s.artist_id THEN 1 END) AS n_nsa
    FROM gt_seeds g
    LEFT JOIN key_owner k   ON k.song_key = g.seed_key
    LEFT JOIN tracks s      ON s.track_id = k.track_id
    LEFT JOIN gt_positive gp ON gp.seed_id = k.track_id
    LEFT JOIN tracks p      ON p.track_id = gp.positive_id
    GROUP BY g.seed_key
),
long AS (
    SELECT 'all' AS labels, n_all AS n_pos FROM per_seed
    UNION ALL
    SELECT 'nsa', n_nsa FROM per_seed
),
ordered AS (
    SELECT labels, n_pos,
           ROW_NUMBER() OVER (PARTITION BY labels ORDER BY n_pos) - 1 AS i,
           COUNT(*) OVER (PARTITION BY labels)                       AS n
    FROM long
),
-- numpy's default percentile: interpolate linearly between the two ranks
-- either side of (n - 1) * p.
cuts AS (
    SELECT DISTINCT o.labels, p.p, (o.n - 1) * p.p AS h
    FROM ordered o
    CROSS JOIN (SELECT 0.5 AS p UNION ALL SELECT 0.75) p
),
quantiles AS (
    SELECT c.labels, c.p,
           lo.n_pos + (c.h - lo.i) * (COALESCE(hi.n_pos, lo.n_pos) - lo.n_pos) AS value
    FROM cuts c
    JOIN ordered lo      ON lo.labels = c.labels AND lo.i = CAST(c.h AS INTEGER)
    LEFT JOIN ordered hi ON hi.labels = c.labels AND hi.i = lo.i + 1
)
SELECT l.labels,
       COUNT(*)                                          AS n_seeds,
       SUM(l.n_pos > 0)                                  AS with_positive,
       AVG(l.n_pos > 0)                                  AS with_positive_share,
       AVG(l.n_pos)                                      AS mean_positives,
       (SELECT value FROM quantiles q WHERE q.labels = l.labels AND q.p = 0.5)
                                                         AS median_positives,
       (SELECT value FROM quantiles q WHERE q.labels = l.labels AND q.p = 0.75)
                                                         AS p75_positives,
       -- The random floor: the share of the library an average seed calls
       -- relevant, i.e. a random ranker's expected precision.
       AVG(l.n_pos) / (SELECT COUNT(*) FROM key_owner)   AS random_precision
FROM long l
GROUP BY l.labels
ORDER BY l.labels;
