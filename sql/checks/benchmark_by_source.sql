-- evaluate._by_source: NDCG@10 and the share of seeds each policy can rank,
-- split by where the seed came from. Every seed counted, blind spots charged
-- zero; the candidate pool is the whole library either way.
SELECT m.policy, ts.source,
       COUNT(*)      AS n_seeds,
       AVG(m.ndcg)   AS ndcg,
       AVG(m.served) AS served
FROM seed_metrics m
JOIN track_source ts ON ts.track_id = m.seed_id
WHERE m.k = 10
GROUP BY m.policy, ts.source
ORDER BY m.policy, ts.source;
