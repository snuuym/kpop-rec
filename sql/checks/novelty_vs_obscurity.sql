-- analyze_tag_sparsity.disentangle, the central test: is a track untagged
-- because it is new, or because it is obscure? Effective tag count regressed
-- on release year and log10(listeners), all three standardized.
--
-- numpy solves it with lstsq. With two standardized predictors the solution
-- has a closed form in the three pairwise correlations, which SQL can reach
-- with plain aggregates (x1 = year, x2 = popularity, y = tags):
--
--   beta_1 = (r_1y - r_2y r_12) / (1 - r_12^2)
--   beta_2 = (r_2y - r_1y r_12) / (1 - r_12^2)
--   R^2    = (r_1y^2 + r_2y^2 - 2 r_1y r_2y r_12) / (1 - r_12^2)
--
-- Correlations do not depend on whether the spread is taken with n or n - 1,
-- so numpy's population std and this agree exactly.
WITH d AS (
    SELECT t.year AS x1, log10(t.listeners) AS x2, s.n_eff AS y
    FROM tracks t
    JOIN track_signals s USING (track_id)
    WHERE t.year BETWEEN 1990 AND 2026
      AND t.listeners > 0
),
m AS (
    SELECT COUNT(*) AS n, AVG(x1) AS m1, AVG(x2) AS m2, AVG(y) AS my FROM d
),
-- Centre first, then sum: summing raw squares of years (~4e6 each) and
-- subtracting afterwards would cancel most of the significant digits.
c AS (
    SELECT SUM((x1 - m1) * (x1 - m1)) AS s11,
           SUM((x2 - m2) * (x2 - m2)) AS s22,
           SUM((y - my) * (y - my))   AS syy,
           SUM((x1 - m1) * (x2 - m2)) AS s12,
           SUM((x1 - m1) * (y - my))  AS s1y,
           SUM((x2 - m2) * (y - my))  AS s2y
    FROM d, m
),
r AS (
    SELECT s12 / sqrt(s11 * s22) AS r12,
           s1y / sqrt(s11 * syy) AS r1y,
           s2y / sqrt(s22 * syy) AS r2y
    FROM c
)
SELECT (SELECT n FROM m)                                           AS n_tracks,
       r1y                                                          AS r_year,
       r2y                                                          AS r_pop,
       (r1y - r2y * r12) / (1 - r12 * r12)                          AS beta_year,
       (r2y - r1y * r12) / (1 - r12 * r12)                          AS beta_pop,
       (r1y * r1y + r2y * r2y - 2 * r1y * r2y * r12) / (1 - r12 * r12) AS r2
FROM r;
