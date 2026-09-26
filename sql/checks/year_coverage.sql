-- How much of the library MusicBrainz resolved a release year for, and how
-- unevenly. Its coverage thins out where popularity does, which is a bias in
-- the novelty-vs-obscurity regression: it under-weights the tail.
WITH known AS (
    SELECT t.track_id, t.year, t.listeners, q.quintile
    FROM tracks t LEFT JOIN track_quintile q USING (track_id)
),
med AS (
    SELECT resolved, AVG(listeners) AS median
    FROM (SELECT year IS NOT NULL AS resolved, listeners,
                 ROW_NUMBER() OVER (PARTITION BY year IS NOT NULL ORDER BY listeners) AS rn,
                 COUNT(*)     OVER (PARTITION BY year IS NOT NULL)                   AS n
          FROM known WHERE listeners IS NOT NULL)
    WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
    GROUP BY resolved
)
SELECT COUNT(*)                                        AS tracks,
       SUM(year IS NOT NULL)                           AS resolved,
       1.0 * SUM(year IS NOT NULL) / COUNT(*)          AS resolved_share,
       AVG(CASE WHEN quintile = 0 THEN year IS NOT NULL END) AS q1_resolved,
       AVG(CASE WHEN quintile = 4 THEN year IS NOT NULL END) AS q5_resolved,
       (SELECT median FROM med WHERE resolved = 1)     AS median_resolved,
       (SELECT median FROM med WHERE resolved = 0)     AS median_unresolved
FROM known;
