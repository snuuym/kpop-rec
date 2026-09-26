-- analyze_tag_sparsity.source_breakdown: the library is two samples, the
-- Last.fm tag pull and the owner's Spotify playlists. What each looks like.
WITH s AS (
    SELECT ts.source, g.n_eff, g.has_features, t.listeners, t.year, t.year_spotify
    FROM tracks t
    JOIN track_signals g USING (track_id)
    JOIN track_source ts USING (track_id)
),
listeners AS (
    SELECT source, listeners AS v,
           ROW_NUMBER() OVER (PARTITION BY source ORDER BY listeners) AS rn,
           COUNT(*)     OVER (PARTITION BY source)                    AS n
    FROM s WHERE listeners IS NOT NULL
),
years AS (
    SELECT source, year AS v,
           ROW_NUMBER() OVER (PARTITION BY source ORDER BY year) AS rn,
           COUNT(*)     OVER (PARTITION BY source)               AS n
    FROM s WHERE year IS NOT NULL
),
-- The middle row, or the mean of the middle two, per source.
med_l AS (SELECT source, AVG(v) AS median FROM listeners WHERE rn IN ((n + 1) / 2, (n + 2) / 2) GROUP BY source),
med_y AS (SELECT source, AVG(v) AS median FROM years     WHERE rn IN ((n + 1) / 2, (n + 2) / 2) GROUP BY source)
SELECT s.source,
       COUNT(*)                     AS tracks,
       AVG(s.n_eff = 0)             AS no_tag,
       AVG(s.has_features)          AS audio_coverage,
       -- no effective tag and no audio features: out of reach of every content method
       AVG(s.n_eff = 0 AND NOT s.has_features) AS unreachable,
       AVG(s.listeners IS NOT NULL) AS listeners_known,
       ml.median                    AS median_listeners,
       AVG(s.year IS NOT NULL)      AS year_resolved,
       -- released 2023 or later, among tracks with a known year (Spotify's where MusicBrainz's is absent)
       1.0 * SUM(COALESCE(s.year_spotify, s.year) >= 2023) / COUNT(COALESCE(s.year_spotify, s.year)) AS recent_share,
       my.median                    AS median_year
FROM s
LEFT JOIN med_l ml ON ml.source = s.source
LEFT JOIN med_y my ON my.source = s.source
GROUP BY s.source
ORDER BY s.source;
