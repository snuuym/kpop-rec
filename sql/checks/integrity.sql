-- analyze_tag_sparsity.integrity_check. An empty tag list means either
-- "nobody has tagged this track" or "we never asked", and only the first is a
-- finding. Tracks the backfill pass queried one by one are the first kind.
SELECT SUM(s.n_raw = 0 AND t.tag_source = 'backfill')     AS verified_untagged,
       SUM(s.n_raw = 0 AND t.tag_source IS NOT 'backfill') AS unverified,
       SUM(s.n_raw > 0 AND s.n_eff = 0)                    AS root_only,
       SUM(s.n_eff > 0)                                    AS has_effective,
       COUNT(*)                                            AS n_tracks
FROM track_signals s
JOIN tracks t USING (track_id);
