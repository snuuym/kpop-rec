-- analyze_tag_sparsity.selection_bias_check. The first tagging pass walked the
-- corpus in descending popularity and was interrupted, so the tracks it
-- reached should be the popular ones: median listeners, first pass against
-- the backfill that finished the job.
WITH ordered AS (
    SELECT COALESCE(tag_source, 'first_pass') AS pass, listeners,
           ROW_NUMBER() OVER (PARTITION BY COALESCE(tag_source, 'first_pass')
                              ORDER BY listeners)                   AS rn,
           COUNT(*) OVER (PARTITION BY COALESCE(tag_source, 'first_pass')) AS n
    FROM tracks
    -- Only the Last.fm pull has a first pass to compare against; playlist
    -- tracks are all tagged by the backfill and would pollute that group.
    WHERE listeners IS NOT NULL
      AND track_id IN (SELECT track_id FROM track_source WHERE source = 'lastfm_tag')
),
medians AS (
    SELECT pass, MAX(n) AS n_tracks, AVG(listeners) AS median_listeners
    FROM ordered
    WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
    GROUP BY pass
)
SELECT f.n_tracks                                      AS first_pass_n,
       f.median_listeners                              AS first_pass_median,
       b.n_tracks                                      AS backfill_n,
       b.median_listeners                              AS backfill_median,
       f.median_listeners / MAX(b.median_listeners, 1) AS ratio
FROM medians f
JOIN medians b ON f.pass = 'first_pass' AND b.pass = 'backfill';
