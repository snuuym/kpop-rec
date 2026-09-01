"""Metrics are the part of a benchmark nobody double-checks, so they are checked
here against cases whose answers can be worked out by hand."""

import numpy as np
import pytest

from kpoprec.metrics import METRIC_NAMES, evaluate_ranking, mean_metrics, zero_metrics


def test_perfect_ranking_scores_one():
    ranked = np.array([0, 1, 2, 3, 4])
    m = evaluate_ranking(ranked, {0, 1, 2}, k=3)
    assert m["recall"] == 1.0
    assert m["precision"] == 1.0
    assert m["hit_rate"] == 1.0
    assert m["ndcg"] == pytest.approx(1.0)


def test_empty_ranking_scores_zero():
    m = evaluate_ranking(np.array([7, 8, 9]), {0, 1}, k=3)
    assert all(m[name] == 0.0 for name in METRIC_NAMES)


def test_ndcg_rewards_earlier_hits():
    """The whole reason to carry NDCG alongside recall: same hits, better order."""
    early = evaluate_ranking(np.array([0, 5, 6, 7]), {0}, k=4)
    late = evaluate_ranking(np.array([5, 6, 7, 0]), {0}, k=4)
    assert early["ndcg"] > late["ndcg"]
    assert early["recall"] == late["recall"] == 1.0


def test_recall_and_precision_differ_when_positives_outnumber_k():
    """Recall is bounded by k/|positives|; precision is not. Confusing the two is
    how a benchmark reports 20% and means 100%."""
    m = evaluate_ranking(np.array([0, 1]), {0, 1, 2, 3, 4}, k=2)
    assert m["precision"] == 1.0
    assert m["recall"] == pytest.approx(0.4)


def test_ndcg_ideal_accounts_for_few_positives():
    """With one positive, a single hit at rank 1 is a perfect result -- the ideal
    DCG must not assume k relevant items exist."""
    m = evaluate_ranking(np.array([0, 1, 2]), {0}, k=3)
    assert m["ndcg"] == pytest.approx(1.0)


def test_seed_with_no_positives_is_rejected():
    """Such a seed is unevaluable, not a zero. Silently scoring it zero would
    drag every policy down by the same amount and hide the real coverage story."""
    with pytest.raises(ValueError):
        evaluate_ranking(np.array([0, 1]), set(), k=2)


def test_zero_metrics_are_all_zero():
    assert set(zero_metrics()) == set(METRIC_NAMES)
    assert all(v == 0.0 for v in zero_metrics().values())


def test_mean_is_macro_over_seeds():
    """Every seed counts once regardless of how many labels it has, so a seed
    with 80 positives cannot outvote twenty seeds with one."""
    rows = [
        {"recall": 1.0, "precision": 1.0, "hit_rate": 1.0, "ndcg": 1.0},
        {"recall": 0.0, "precision": 0.0, "hit_rate": 0.0, "ndcg": 0.0},
    ]
    assert mean_metrics(rows)["recall"] == pytest.approx(0.5)


def test_mean_of_nothing_is_nan_not_zero():
    """A policy that served no seed has an undefined score, not a bad one."""
    assert all(np.isnan(v) for v in mean_metrics([]).values())
