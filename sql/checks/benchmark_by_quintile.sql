-- evaluate.py's per-quintile table (eval_by_quintile.csv) at the headline
-- cut-off, k = 10: every seed counted, blind spots charged zero. Quintiles are
-- the library's, not the evaluable seeds', so Q1 is the coldest fifth of the
-- catalogue rather than of the tracks that happen to have labels.
SELECT m.policy, q.quintile,
       AVG(m.recall)    AS recall,
       AVG(m.precision) AS precision,
       AVG(m.hit_rate)  AS hit_rate,
       AVG(m.ndcg)      AS ndcg,
       AVG(m.served)    AS served
FROM seed_metrics m
JOIN track_quintile q ON q.track_id = m.seed_id
WHERE m.k = 10
GROUP BY m.policy, q.quintile
ORDER BY m.policy, q.quintile;
