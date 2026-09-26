-- evaluate.headline at every k (eval_by_k.csv): how often each policy can
-- rank at all, and each metric averaged two ways -- over the seeds it can
-- serve, and over every seed with the blind spots charged zero.
SELECT k, policy,
       AVG(served)                              AS coverage,
       SUM(served)                              AS n_served,
       COUNT(*)                                 AS n_seeds,
       AVG(CASE WHEN served THEN recall END)    AS recall_served,
       AVG(recall)                              AS recall_all,
       AVG(CASE WHEN served THEN precision END) AS precision_served,
       AVG(precision)                           AS precision_all,
       AVG(CASE WHEN served THEN hit_rate END)  AS hit_rate_served,
       AVG(hit_rate)                            AS hit_rate_all,
       AVG(CASE WHEN served THEN ndcg END)      AS ndcg_served,
       AVG(ndcg)                                AS ndcg_all
FROM seed_metrics
GROUP BY k, policy
ORDER BY k, policy;
