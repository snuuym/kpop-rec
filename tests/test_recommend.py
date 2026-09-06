"""The scoring rules here are a port of the app's JavaScript. These tests pin
the parts that would silently change a benchmark result if they drifted: the
feature normalization constants, who is allowed to be recommended, what counts
as a policy having signal, and how ties are resolved."""

import numpy as np
import pytest

from kpoprec.recommend import (
    FEATURE_KEYS,
    Library,
    can_serve,
    feature_vec,
    score_acoustic,
    score_popularity,
    score_tags,
    top_k,
)


def song(title, artist="A", *, listeners=100, features=None, all_tags=None, tags=None):
    return {
        "title": title,
        "artist": artist,
        "listeners": listeners,
        "features": features,
        "all_tags": all_tags if all_tags is not None else [],
        "tags": tags if tags is not None else ["K-pop"],
    }


FEATS = {
    "danceability": 0.5, "energy": 0.5, "valence": 0.5, "acousticness": 0.5,
    "instrumentalness": 0.0, "speechiness": 0.1, "liveness": 0.2,
    "tempo": 120.0, "loudness": -10.0,
}


# ── Feature normalization: the constants are copied from the app ────────────

def test_tempo_and_loudness_use_the_app_rescaling():
    v = feature_vec({"tempo": 125.0, "loudness": -30.0})
    assert v[FEATURE_KEYS.index("tempo")] == pytest.approx(0.5)
    assert v[FEATURE_KEYS.index("loudness")] == pytest.approx(0.5)


def test_out_of_range_values_are_clamped():
    """ReccoBeats occasionally returns a tempo above 250; an unclamped value
    would dominate a weighted euclidean distance on its own."""
    v = feature_vec({"tempo": 400.0, "loudness": 20.0})
    assert v[FEATURE_KEYS.index("tempo")] == 1.0
    assert v[FEATURE_KEYS.index("loudness")] == 1.0
    assert feature_vec({"loudness": -200.0})[FEATURE_KEYS.index("loudness")] == 0.0


def test_missing_features_fall_back_to_neutral_defaults():
    v = feature_vec(None)
    assert v[FEATURE_KEYS.index("energy")] == pytest.approx(0.5)
    assert v[FEATURE_KEYS.index("instrumentalness")] == pytest.approx(0.0)


# ── Policies ────────────────────────────────────────────────────────────────

def test_a_seed_is_never_recommended_back_to_itself():
    """-inf, not zero: a seed that shares every tag with itself would otherwise
    top its own recommendation list. It can only reappear when k exhausts the
    library, which no real run does."""
    lib = Library([song("a"), song("b"), song("c")])
    for scores in (score_popularity(lib, 0), score_tags(lib, 0), score_acoustic(lib, 0)):
        assert scores[0] == -np.inf
        assert 0 not in top_k(scores, 2, np.arange(3))
        assert top_k(scores, 3, np.arange(3))[-1] == 0


def test_popularity_ranks_by_listeners():
    lib = Library([song("a", listeners=1), song("b", listeners=999), song("c", listeners=50)])
    assert top_k(score_popularity(lib, 0), 2, np.arange(3)).tolist() == [1, 2]


def test_acoustic_prefers_the_nearer_track():
    near = dict(FEATS, energy=0.52)
    far = dict(FEATS, energy=0.99, valence=0.05, danceability=0.02)
    lib = Library([song("seed", features=FEATS), song("near", features=near),
                   song("far", features=far)])
    assert top_k(score_acoustic(lib, 0), 1, np.arange(3))[0] == 1


def test_featureless_tracks_rank_below_every_featured_one():
    lib = Library([song("seed", features=FEATS), song("none"),
                   song("far", features=dict(FEATS, energy=1.0, valence=0.0))])
    assert top_k(score_acoustic(lib, 0), 2, np.arange(3)).tolist() == [2, 1]


def test_tag_overlap_beats_no_overlap():
    lib = Library([
        song("seed", all_tags=["ballad", "citypop"]),
        song("match", all_tags=["citypop"]),
        song("miss", all_tags=["trot"]),
    ])
    assert top_k(score_tags(lib, 0), 1, np.arange(3))[0] == 1


# ── Serviceability ──────────────────────────────────────────────────────────

def test_generic_kpop_label_alone_is_not_tag_signal():
    """Regression. Every track carries at least one classified label, and for an
    untagged track that label is the generic K-pop pool, which matches most of
    the library. Counting it as signal reported 100% tag coverage for a corpus
    that is 72.7% untagged, and made the tag policy look universal."""
    lib = Library([song("untagged", all_tags=["kpop", "korean"], tags=["K-pop"])])
    assert lib.eff_tags[0] == set()
    assert not can_serve("tags", lib, 0)


def test_a_discriminative_tag_is_signal():
    lib = Library([song("tagged", all_tags=["kpop", "citypop"])])
    assert can_serve("tags", lib, 0)


def test_acoustic_serves_only_tracks_with_features():
    lib = Library([song("with", features=FEATS), song("without")])
    assert can_serve("acoustic", lib, 0)
    assert not can_serve("acoustic", lib, 1)


def test_hybrid_serves_a_seed_with_either_signal():
    lib = Library([
        song("feats_only", features=FEATS),
        song("tags_only", all_tags=["citypop"]),
        song("neither", all_tags=["kpop"]),
    ])
    assert can_serve("hybrid", lib, 0)
    assert can_serve("hybrid", lib, 1)
    assert not can_serve("hybrid", lib, 2)


def test_baselines_always_serve():
    lib = Library([song("bare", all_tags=["kpop"])])
    assert can_serve("popularity", lib, 0)
    assert can_serve("random", lib, 0)


# ── Tie-breaking ────────────────────────────────────────────────────────────

def test_ties_are_broken_by_the_supplied_permutation_not_by_index():
    """Regression, and the subtlest bug in the harness.

    The library is stored roughly in collection order, and collection ran in
    descending popularity, so index order carries real popularity signal. When
    a policy scores a large block of candidates identically -- what the tag
    policy does for a seed with no discriminative tag -- breaking ties by index
    handed it a slice of the popularity baseline for free, and it scored well
    above random for no reason of its own.
    """
    scores = np.zeros(6)
    assert top_k(scores, 6, np.arange(6)).tolist() == [0, 1, 2, 3, 4, 5]

    shuffled = np.array([5, 4, 3, 2, 1, 0])
    assert top_k(scores, 6, shuffled).tolist() == [5, 4, 3, 2, 1, 0]


def test_real_scores_still_outrank_the_tiebreak():
    scores = np.array([0.0, 9.0, 0.0])
    assert top_k(scores, 1, np.array([2, 1, 0]))[0] == 1


def test_top_k_is_capped_by_library_size():
    assert len(top_k(np.zeros(3), 99, np.arange(3))) == 3


# ── Same-artist handling ────────────────────────────────────────────────────

def test_same_artist_mask_is_case_and_whitespace_insensitive():
    lib = Library([song("a", "BTS"), song("b", " bts "), song("c", "IVE")])
    assert lib.same_artist(0).tolist() == [True, True, False]


def test_same_artist_mask_includes_the_seed():
    """The mask is used to blank scores, and the seed must stay blanked."""
    lib = Library([song("a", "BTS"), song("c", "IVE")])
    assert lib.same_artist(0)[0]


def test_same_artist_tracks_are_kept_in_the_shipped_ranking():
    """The product keeps them on purpose. Only the evaluation variant drops
    them, so nothing in the scoring policies may filter by artist."""
    lib = Library([
        song("seed", "BTS", all_tags=["citypop"]),
        song("same", "BTS", all_tags=["citypop"]),
        song("other", "IVE", all_tags=["trot"]),
    ])
    assert top_k(score_tags(lib, 0), 1, np.arange(3))[0] == 1


# ── Popularity strata ───────────────────────────────────────────────────────

def test_quintiles_are_equal_sized_and_ordered_by_popularity():
    lib = Library([song(f"s{i}", listeners=i) for i in range(100)])
    counts = np.bincount(lib.quintile, minlength=5)
    assert list(counts) == [20] * 5
    assert lib.quintile[0] == 0 and lib.quintile[-1] == 4


def test_quintiles_split_ties_instead_of_collapsing_them():
    """Most of the cold end shares a listener count. Binning by value would put
    every tied track in one quintile and leave the others empty."""
    lib = Library([song(f"s{i}", listeners=7) for i in range(10)])
    assert list(np.bincount(lib.quintile, minlength=5)) == [2] * 5


def test_quintiles_describe_the_library_not_the_evaluated_subset():
    """The cut must not move when only some seeds are evaluable. If it did, Q1
    would silently mean 'the coldest fifth of whatever had labels'."""
    songs = [song(f"s{i}", listeners=i) for i in range(100)]
    full = Library(songs)
    assert full.quintile[5] == 0
    # The coldest ten tracks, scored on their own, are still all Q1 -- they do
    # not get re-spread across five strata just because they are the only ones
    # in front of us.
    assert [int(q) for q in full.quintile[:10]] == [0] * 10


def test_random_floor_does_not_depend_on_the_order_seeds_are_visited():
    """The floor is what every other policy is read against. Drawing it from one
    generator shared across the run makes it a function of dictionary iteration
    order, so the same corpus yields a different floor after an unrelated
    refactor -- which is exactly what happened."""
    from kpoprec.recommend import policy_rng, score_random
    lib = Library([song(f"s{i}", listeners=i) for i in range(30)])
    forwards = {i: score_random(lib, i, policy_rng(0, i)) for i in range(5)}
    backwards = {i: score_random(lib, i, policy_rng(0, i)) for i in reversed(range(5))}
    for i in range(5):
        assert np.array_equal(forwards[i], backwards[i])
    # Still different noise per seed, and still reproducible across runs.
    assert not np.array_equal(forwards[0], forwards[1])
    assert np.array_equal(forwards[3], score_random(lib, 3, policy_rng(0, 3)))
