-- The novelty-vs-obscurity regression (see novelty_vs_obscurity.sql for the
-- closed form), pooled and within each source. The two samples differ sharply
-- in how new their tracks are, so a source-by-source fit is the sharpest test
-- of whether year and popularity can be told apart at all.
WITH base AS (
    SELECT ts.source AS source, t.year AS x1, log10(t.listeners) AS x2, g.n_eff AS y
    FROM tracks t
    JOIN track_signals g USING (track_id)
    JOIN track_source ts USING (track_id)
    WHERE t.year BETWEEN 1990 AND 2026
      AND t.listeners > 0
),
d AS (
    SELECT 'all' AS grp, x1, x2, y FROM base
    UNION ALL
    SELECT source, x1, x2, y FROM base
),
-- Centre within each group first, then sum: raw sums of squared years would
-- cancel most of their significant digits.
m AS (
    SELECT grp, x1, x2, y,
           AVG(x1) OVER w AS m1, AVG(x2) OVER w AS m2, AVG(y) OVER w AS my
    FROM d
    WINDOW w AS (PARTITION BY grp)
),
c AS (
    SELECT grp, COUNT(*) AS n,
           SUM((x1 - m1) * (x1 - m1)) AS s11,
           SUM((x2 - m2) * (x2 - m2)) AS s22,
           SUM((y - my) * (y - my))   AS syy,
           SUM((x1 - m1) * (x2 - m2)) AS s12,
           SUM((x1 - m1) * (y - my))  AS s1y,
           SUM((x2 - m2) * (y - my))  AS s2y
    FROM m
    GROUP BY grp
),
r AS (
    SELECT grp, n,
           s12 / sqrt(s11 * s22) AS r12,
           s1y / sqrt(s11 * syy) AS r1y,
           s2y / sqrt(s22 * syy) AS r2y
    FROM c
)
SELECT grp                                                             AS sample,
       n                                                               AS n_tracks,
       (r1y - r2y * r12) / (1 - r12 * r12)                             AS beta_year,
       (r2y - r1y * r12) / (1 - r12 * r12)                             AS beta_pop,
       (r1y * r1y + r2y * r2y - 2 * r1y * r2y * r12) / (1 - r12 * r12) AS r2
FROM r
ORDER BY grp <> 'all', grp;
