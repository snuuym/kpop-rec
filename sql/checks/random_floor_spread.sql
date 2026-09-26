-- How much a single draw of the random floor moves. The floor is averaged over
-- the run's draws (evaluate --random-repeats) because one draw of it, in the
-- coldest quintile where few seeds are evaluable, swings by about as much as the
-- gaps the README claims. Each draw's NDCG@10 over the Q1 seeds, then the
-- spread across draws: this is what averaging removes.
WITH hits AS (
    SELECT r.seed_id, r.draw,
           TOTAL(CASE WHEN gp.positive_id IS NOT NULL THEN d.gain END) AS dcg
    FROM rankings r
    JOIN discount d ON d.rank = r.rank
    LEFT JOIN gt_positive gp
           ON gp.seed_id = r.seed_id AND gp.positive_id = r.track_id
    WHERE r.policy = 'random' AND r.rank <= 10
    GROUP BY r.seed_id, r.draw
),
per_draw AS (
    SELECT h.draw,
           AVG(h.dcg / (SELECT TOTAL(gain) FROM discount
                        WHERE rank <= MIN(e.n_positives, 10))) AS ndcg
    FROM hits h
    JOIN evaluable_seed e ON e.seed_id = h.seed_id
    JOIN track_quintile q ON q.track_id = h.seed_id
    WHERE q.quintile = 0
    GROUP BY h.draw
)
SELECT (SELECT COUNT(*) FROM evaluable_seed e JOIN track_quintile q ON q.track_id = e.seed_id
        WHERE q.quintile = 0) AS q1_seeds,
       COUNT(*)  AS draws,
       MIN(ndcg) AS lowest_draw,
       MAX(ndcg) AS highest_draw,
       AVG(ndcg) AS mean
FROM per_draw;
