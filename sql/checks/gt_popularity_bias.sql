-- build_ground_truth.diagnose 2: are the positives more popular than the
-- library they are drawn from? Collaborative filtering favours the head; the
-- stronger the skew, the stronger a popularity baseline will look. A positive
-- counts once for every seed that lists it, as in the diagnostic.
WITH long AS (
    SELECT 'library' AS pop, t.listeners
    FROM key_owner k JOIN tracks t USING (track_id)
    WHERE t.listeners > 0
    UNION ALL
    SELECT 'positives', t.listeners
    FROM gt_positive gp JOIN tracks t ON t.track_id = gp.positive_id
    WHERE t.listeners > 0
),
ordered AS (
    SELECT pop, listeners,
           ROW_NUMBER() OVER (PARTITION BY pop ORDER BY listeners) AS rn,
           COUNT(*) OVER (PARTITION BY pop)                        AS n
    FROM long
),
medians AS (
    SELECT pop, AVG(listeners) AS median
    FROM ordered
    WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
    GROUP BY pop
)
SELECT l.median                  AS library_median,
       p.median                  AS positives_median,
       p.median / MAX(l.median, 1) AS ratio
FROM medians l
JOIN medians p ON l.pop = 'library' AND p.pop = 'positives';
