-- The central table by source: how much of each library-wide popularity
-- quintile each signal reaches, within each sample. A combination that has no
-- tracks has no row.
SELECT q.quintile, ts.source,
       COUNT(*)                 AS tracks,
       AVG(s.n_eff > 0)         AS tag_coverage,
       AVG(s.has_features)      AS audio_coverage
FROM track_quintile q
JOIN track_signals s USING (track_id)
JOIN track_source ts USING (track_id)
GROUP BY q.quintile, ts.source
ORDER BY q.quintile, ts.source;
