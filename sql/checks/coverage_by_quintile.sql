-- The project's central table (analyze_tag_sparsity.fig5, README): how much of
-- each popularity quintile each signal reaches. Tag coverage should swing with
-- popularity; acoustic coverage should not.
SELECT q.quintile,
       COUNT(*)                                                   AS n_tracks,
       AVG(s.n_eff > 0)                                           AS tag_coverage,
       AVG(s.has_features)                                        AS feature_coverage,
       MAX(AVG(s.n_eff > 0)) OVER () - MIN(AVG(s.n_eff > 0)) OVER ()
                                                                  AS tag_spread,
       MAX(AVG(s.has_features)) OVER () - MIN(AVG(s.has_features)) OVER ()
                                                                  AS feature_spread
FROM track_quintile q
JOIN track_signals s USING (track_id)
GROUP BY q.quintile
ORDER BY q.quintile;
