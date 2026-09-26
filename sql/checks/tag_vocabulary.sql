-- analyze_tag_sparsity.tag_vocabulary: document frequency of every normalized
-- raw tag. A tag repeated on one track counts once for it.
SELECT tag_norm                                  AS tag,
       COUNT(DISTINCT track_id)                  AS doc_freq,
       COUNT(*) OVER ()                          AS n_unique,
       SUM(COUNT(DISTINCT track_id) = 1) OVER () AS n_singleton
FROM track_tags
WHERE tag_norm <> ''
GROUP BY tag_norm
ORDER BY doc_freq DESC, tag;
