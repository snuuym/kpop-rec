-- analyze_tag_sparsity.d9_lower_bound (D9): how many tracks carry a
-- track-level effective tag, how many only an album-level one, and how many
-- carry neither -- the tightened, still-not-exact lower bound on coverage.
SELECT SUM(n_eff > 0)                      AS track,
       SUM(n_eff = 0 AND n_album_eff > 0)  AS album,
       SUM(n_eff = 0 AND n_album_eff = 0)  AS none,
       COUNT(*)                            AS n_tracks
FROM track_signals;
