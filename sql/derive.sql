-- Fills the materialized tables in schema.sql once the load is done. These
-- statements are the definitions; the tables exist only to carry an index.

-- The labels resolved to tracks, through key_owner: a duplicated join key
-- resolves to its last track, as it does in the pipeline.
INSERT INTO gt_positive (seed_id, positive_id)
SELECT DISTINCT s.track_id, p.track_id
FROM ground_truth g
JOIN key_owner s ON s.song_key = g.seed_key
JOIN key_owner p ON p.song_key = g.positive_key
WHERE p.track_id <> s.track_id;

-- As deep as the deepest stored ranking, which can run past `depth`.
INSERT INTO discount (rank, gain)
WITH RECURSIVE r(rank) AS (
    SELECT 1
    UNION ALL
    SELECT rank + 1 FROM r WHERE rank < (SELECT MAX(rank) FROM rankings)
)
SELECT rank, 1.0 / log2(rank + 1) FROM r;
