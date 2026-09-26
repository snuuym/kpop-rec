-- How much of each popularity quintile the labels can evaluate at all. This is
-- the blind spot every cold-end number in the README is qualified by: a seed
-- with no in-library positive is not scored badly, it is not scored.
SELECT q.quintile,
       COUNT(*)                          AS n_tracks,
       AVG(e.seed_id IS NOT NULL)        AS with_positives,
       AVG(COALESCE(e.n_positives, 0))   AS mean_positives
FROM track_quintile q
LEFT JOIN evaluable_seed e ON e.seed_id = q.track_id
GROUP BY q.quintile
ORDER BY q.quintile;
