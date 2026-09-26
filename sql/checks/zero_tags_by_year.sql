-- analyze_tag_sparsity.fig2_year (Fig 2b): the share of tracks with no
-- effective tag, by release-year band. If untagged meant "too new to have
-- been tagged yet", this would rise toward recent years. The bands are
-- pd.cut's, closed on the right.
SELECT CASE WHEN year <= 2009 THEN '<=2009'
            WHEN year <= 2014 THEN '10-14'
            WHEN year <= 2017 THEN '15-17'
            WHEN year <= 2020 THEN '18-20'
            WHEN year <= 2022 THEN '21-22'
            ELSE '23+'
       END             AS band,
       COUNT(*)        AS n_tracks,
       AVG(n_eff = 0)  AS zero_share
FROM tracks
JOIN track_signals USING (track_id)
WHERE year BETWEEN 1990 AND 2026
GROUP BY band
ORDER BY MIN(year);
