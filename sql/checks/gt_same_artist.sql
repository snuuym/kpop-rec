-- build_ground_truth.diagnose 1: the share of positives by the seed's own
-- artist. Were it high, "recommend more of the same artist" would win the
-- benchmark and it would be measuring artist recognition.
WITH pairs AS (
    SELECT gp.seed_id, p.artist_id = s.artist_id AS same
    FROM gt_positive gp
    JOIN tracks s ON s.track_id = gp.seed_id
    JOIN tracks p ON p.track_id = gp.positive_id
),
per_seed AS (
    SELECT seed_id, AVG(same) AS share FROM pairs GROUP BY seed_id
),
ordered AS (
    SELECT share, ROW_NUMBER() OVER (ORDER BY share) AS rn, COUNT(*) OVER () AS n
    FROM per_seed
)
SELECT (SELECT SUM(same) FROM pairs)  AS same_artist,
       (SELECT COUNT(*) FROM pairs)   AS positives,
       (SELECT AVG(same) FROM pairs)  AS share,
       AVG(share)                     AS median_seed_share
FROM ordered
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);
