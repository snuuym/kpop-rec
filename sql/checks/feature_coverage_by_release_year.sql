-- How much of the library the feature provider (ReccoBeats) has indexed, by
-- when the track came out. The year is MusicBrainz's earliest release where
-- resolved, and the Spotify album's where not. Coverage that looks like it
-- depends on popularity turns out to depend on this.
SELECT CASE WHEN COALESCE(year, year_spotify) <= 2024 THEN '<=2024'
            WHEN COALESCE(year, year_spotify) = 2025  THEN '2025'
            ELSE '2026' END        AS released,
       COUNT(*)                    AS tracks,
       AVG(s.has_features)         AS feature_coverage
FROM tracks t
JOIN track_signals s USING (track_id)
WHERE COALESCE(year, year_spotify) IS NOT NULL
GROUP BY released
ORDER BY released;
