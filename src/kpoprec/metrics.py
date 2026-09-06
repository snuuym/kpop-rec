"""Top-K ranking metrics for binary relevance.

Four measures, because they fail in different directions and the disagreements
are informative:

* **Recall@K** -- of everything relevant, how much did we surface? Depends on
  how many positives a seed has, so it is not comparable across seeds with very
  different label counts without saying so.
* **Precision@K** -- of what we showed, how much was relevant? Directly
  comparable to the random floor.
* **HitRate@K** -- did we get *anything* right? The one a user feels first, and
  the only one that stays meaningful when a seed has a single positive.
* **NDCG@K** -- rank-aware: a positive at rank 1 counts for more than one at
  rank 10.

Relevance is binary here because the labels are binary: a track is either in
Last.fm's similar list for the seed or it is not. There is no graded judgement
to weight with, and inventing one would dress up CF output as something it is
not.

Complete and incomplete labels
------------------------------
Two kinds of label set get scored here and they cannot use the same arithmetic.

Last.fm's similar list is *complete* in the sense that matters: it names every
track it considers relevant, so anything absent from it is a genuine negative
and a miss is a miss.

Human annotation is not. Judging the top of a pooled ranking produces verdicts
for a few dozen candidates per seed and silence about the other twelve hundred,
and silence is *unknown*, not *irrelevant*. Scoring an unjudged track as a miss
punishes a policy for surfacing something nobody got round to looking at --
which systematically favours whichever policy the pool was built from.

The fix is the condensed list (Sakai 2007): drop unjudged tracks from the
ranking before scoring, so every position that counts is one a human actually
ruled on. Pass ``judged`` to switch to it. Within the pooling depth the two
agree exactly -- a policy's own top-10 is fully judged when the pool was built
to depth 10 -- and they diverge below it, which is the honest place to diverge.

One caveat travels with ``judged`` and cannot be engineered away: recall is
computed against the positives *found in the pool*, not against every relevant
track in the library. It is recall within the judged set, and reporting it as
anything else would overstate what 400 human judgements can establish.
"""

from __future__ import annotations

import numpy as np

# Discount for positions 1..N, computed once. NDCG's log2(rank + 1).
_MAX_K = 1000
_DISCOUNT = 1.0 / np.log2(np.arange(2, _MAX_K + 2))
# Best possible DCG for r relevant items: the first r positions all hit.
_IDEAL = np.concatenate([[0.0], np.cumsum(_DISCOUNT)])


def evaluate_ranking(
    ranked: np.ndarray,
    positives: set[int],
    k: int,
    judged: set[int] | None = None,
) -> dict[str, float]:
    """Metrics for one seed's ranking against its positive set.

    ``ranked`` is an array of library indices, best first. Only the first ``k``
    are looked at.

    ``judged`` is the set of indices a human actually ruled on for this seed.
    Leave it ``None`` for label sets where absence means irrelevant, which is
    the case for the Last.fm labels. Supply it for annotation, and the ranking
    is condensed to judged positions first: unjudged tracks are removed rather
    than counted as misses, and the metrics are computed over what remains.
    Precision then divides by the number of judged positions actually scored,
    which can be fewer than ``k`` once ``k`` runs past the pooling depth.
    """
    if not positives:
        raise ValueError("a seed with no positives is not evaluable")

    if judged is not None:
        if not positives <= judged:
            raise ValueError("every positive must be judged")
        ranked = np.array([i for i in ranked if i in judged], dtype=int)

    head = ranked[:k]
    hits = np.fromiter((idx in positives for idx in head), dtype=bool, count=len(head))
    n_hit = int(hits.sum())

    # Both denominators follow the list that was actually scored. Under complete
    # labels that list is k long and this is the textbook definition; under a
    # condensed list it is however many judged positions survived, which is the
    # only count a human verdict exists for.
    denom = len(head) if judged is not None else k
    dcg = float(_DISCOUNT[: len(head)][hits].sum())
    ideal = float(_IDEAL[min(len(positives), len(head))])

    return {
        "recall": n_hit / len(positives),
        "precision": n_hit / denom if denom else 0.0,
        "hit_rate": 1.0 if n_hit else 0.0,
        "ndcg": dcg / ideal if ideal else 0.0,
    }


def zero_metrics() -> dict[str, float]:
    """The score for a seed a policy could not rank at all.

    Not the same thing as ranking badly, which is why the harness reports the
    two populations separately -- but when a policy is charged for its blind
    spots, this is what a blind spot is worth.
    """
    return {"recall": 0.0, "precision": 0.0, "hit_rate": 0.0, "ndcg": 0.0}


METRIC_NAMES = ("recall", "precision", "hit_rate", "ndcg")


def mean_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    """Macro-average over seeds: every seed counts once, regardless of label count."""
    if not rows:
        return dict.fromkeys(METRIC_NAMES, float("nan"))
    return {m: float(np.mean([r[m] for r in rows])) for m in METRIC_NAMES}
