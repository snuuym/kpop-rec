-- evaluate.report, protocol: how many seeds the benchmark can score, against
-- how large a pool, and how many positives the median seed has.
WITH ordered AS (
    SELECT n_positives,
           ROW_NUMBER() OVER (ORDER BY n_positives) AS rn,
           COUNT(*) OVER ()                         AS n
    FROM evaluable_seed
)
SELECT (SELECT COUNT(*) FROM evaluable_seed) AS n_seeds,
       (SELECT COUNT(*) FROM tracks)         AS n_library,
       AVG(n_positives)                      AS median_positives
FROM ordered
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);
