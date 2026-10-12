-- analyze_tag_sparsity.d9_lower_bound, the by-quintile table: track-level
-- coverage next to the track-or-album lower bound, and how much the gradient
-- narrows (but does not vanish) once the album fallback is added.
SELECT q.quintile,
       COUNT(*)                                            AS n_tracks,
       AVG(s.n_eff > 0)                                     AS track_coverage,
       AVG(s.n_eff > 0 OR s.n_album_eff > 0)                 AS combined_coverage,
       MAX(AVG(s.n_eff > 0 OR s.n_album_eff > 0)) OVER ()
         - MIN(AVG(s.n_eff > 0 OR s.n_album_eff > 0)) OVER () AS combined_spread
FROM track_quintile q
JOIN track_signals s USING (track_id)
GROUP BY q.quintile
ORDER BY q.quintile;
