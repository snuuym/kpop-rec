-- analyze_tag_sparsity.fig4_coverage: which fallback reaches which track.
-- A track with no effective tag and no audio features is out of reach of
-- every content-based method.
SELECT CASE WHEN n_eff = 0 THEN 'no tags' ELSE 'has tags' END AS bucket,
       SUM(NOT has_features)                                  AS no_feature,
       SUM(has_features)                                      AS has_feature,
       COUNT(*)                                               AS total,
       AVG(has_features)                                      AS feature_coverage,
       -- A window over the grouped rows: coverage across both buckets.
       1.0 * SUM(SUM(has_features)) OVER () / SUM(COUNT(*)) OVER ()
                                                              AS overall_feature_coverage,
       SUM(COUNT(*)) OVER ()                                  AS n_tracks
FROM track_signals
GROUP BY bucket
ORDER BY bucket DESC;
