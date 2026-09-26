-- analyze_tag_sparsity.fig1_distribution: how much tag signal is left once the
-- tags every K-pop track carries are removed.
WITH ordered AS (
    SELECT n_eff,
           ROW_NUMBER() OVER (ORDER BY n_eff) AS rn,
           COUNT(*) OVER ()                   AS n
    FROM track_signals
),
-- SQLite has no MEDIAN. The middle row, or the mean of the middle two when
-- the count is even -- which is what pandas returns.
median AS (
    SELECT AVG(n_eff) AS value
    FROM ordered
    WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
)
SELECT COUNT(*)                      AS n_tracks,
       AVG(n_raw)                    AS mean_raw,
       AVG(n_eff)                    AS mean_eff,
       (SELECT value FROM median)    AS median_eff,
       SUM(n_eff = 0)                AS zero_eff,
       AVG(n_eff = 0)                AS zero_eff_share,
       SUM(n_eff <= 2)               AS thin,
       AVG(n_eff <= 2)               AS thin_share,
       SUM(n_classified > 0)         AS classified,
       AVG(n_classified > 0)         AS classified_share
FROM track_signals;
