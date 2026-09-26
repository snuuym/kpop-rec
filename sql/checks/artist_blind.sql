-- evaluate.report, same-artist section. The labels are artist-deduplicated,
-- so a top-10 slot spent on the seed's own artist is scored a miss whatever it
-- contains. How much of each list is spent that way, and what NDCG@10 is with
-- that artist removed from the ranking and the labels alike.
WITH same_in_top AS (
    SELECT policy, seed_id, AVG(n_same) AS n_same    -- averaged over draws
    FROM (
        SELECT r.policy, r.seed_id, r.draw, SUM(c.artist_id = s.artist_id) AS n_same
        FROM rankings r
        JOIN tracks s ON s.track_id = r.seed_id
        JOIN tracks c ON c.track_id = r.track_id
        WHERE r.rank <= 10
        GROUP BY r.policy, r.seed_id, r.draw
    )
    GROUP BY policy, seed_id
),
share AS (   -- over the seeds each policy can actually serve
    SELECT sv.policy, AVG(t.n_same) / 10.0 AS same_artist_share
    FROM served sv
    JOIN same_in_top t ON t.policy = sv.policy AND t.seed_id = sv.seed_id
    WHERE sv.served
    GROUP BY sv.policy
),
shipped AS (
    SELECT policy, AVG(ndcg) AS ndcg FROM seed_metrics WHERE k = 10 GROUP BY policy
),
blind AS (
    SELECT policy, AVG(ndcg) AS ndcg, COUNT(*) AS n_seeds, SUM(ndcg IS NULL) AS n_unscorable
    FROM seed_metrics_blind WHERE k = 10 GROUP BY policy
)
SELECT s.policy, s.same_artist_share,
       sh.ndcg   AS ndcg_shipped,
       b.ndcg    AS ndcg_blind,
       b.n_seeds AS blind_seeds,
       b.n_unscorable
FROM share s
JOIN shipped sh USING (policy)
JOIN blind b USING (policy)
ORDER BY s.policy;
