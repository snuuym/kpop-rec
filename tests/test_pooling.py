"""A pool that misses a policy's own top-K silently rigs the comparison it was
built to make, and a task file that leaks popularity or provenance turns the
annotator into a second copy of the baseline. Neither failure shows up in the
output, so both are pinned here."""

import numpy as np
import pytest

from kpoprec.normalize import song_key
from kpoprec.pooling import (
    build_pool,
    evaluable_seeds,
    pool_seed,
    select_seeds,
    sheet,
)
from kpoprec.recommend import POLICIES, Library, can_serve

from test_recommend import FEATS, song


def library(n=60):
    """A library with a spread of popularity and a mix of tagged and featured
    tracks, so ``can_serve`` genuinely differs between policies."""
    songs = []
    for i in range(n):
        songs.append(song(
            f"t{i}",
            artist=f"artist{i % 7}",
            listeners=i * 10,
            features=dict(FEATS, energy=i / n) if i % 3 else None,
            all_tags=["citypop", "ballad"] if i % 4 == 0 else [],
        ))
    return songs, Library(songs)


def pool_args(lib, seed=0):
    rng = np.random.default_rng(seed)
    return rng, rng.permutation(lib.n)


# ── The guarantee the whole design rests on ────────────────────────────────

def test_pool_contains_every_policys_own_top_k():
    """Judge only one policy's list and its rivals are scored on candidates
    nobody assessed. The union of all five is what makes the comparison fair,
    so every servable policy's top-`depth` must be inside the pool."""
    songs, lib = library()
    rng, tiebreak = pool_args(lib)
    for i in (3, 17, 40):
        per_policy, union = pool_seed(lib, i, depth=10, tiebreak=tiebreak, run_seed=0)
        for policy, ranked in per_policy.items():
            assert set(ranked) <= set(union), policy
            assert len(ranked) == 10


def test_pool_skips_policies_with_no_signal():
    """An unservable policy has no ranking to defend, and padding the pool with
    one would spend judgements on candidates it did not really choose."""
    songs, lib = library()
    untagged = next(i for i in range(lib.n) if not can_serve("tags", lib, i))
    rng, tiebreak = pool_args(lib)
    per_policy, _ = pool_seed(lib, untagged, depth=10, tiebreak=tiebreak, run_seed=0)
    assert "tags" not in per_policy
    assert "popularity" in per_policy


def test_seed_is_never_its_own_candidate():
    songs, lib = library()
    rng, tiebreak = pool_args(lib)
    _, union = pool_seed(lib, 5, depth=10, tiebreak=tiebreak, run_seed=0)
    assert 5 not in union


def test_pool_is_deduplicated():
    """Policies overlap heavily at the cold end; a candidate two of them rank
    must cost one judgement, not two."""
    songs, lib = library()
    rng, tiebreak = pool_args(lib)
    _, union = pool_seed(lib, 12, depth=10, tiebreak=tiebreak, run_seed=0)
    assert len(union) == len(set(union))
    assert len(union) < 10 * len(POLICIES)


# ── Sampling ────────────────────────────────────────────────────────────────

def test_seeds_are_spread_evenly_over_the_requested_quintiles():
    songs, lib = library()
    rng = np.random.default_rng(0)
    seeds = select_seeds(lib, (0, 1), n_seeds=10, rng=rng)
    assert len(seeds) == 10
    assert sorted(int(lib.quintile[i]) for i in seeds) == [0] * 5 + [1] * 5


def test_sampling_does_not_skip_seeds_no_content_policy_can_rank():
    """How often the cold end cannot be served at all is one of the findings.
    Filtering those seeds out would rebuild the selection bias being escaped."""
    songs, lib = library(n=200)
    rng = np.random.default_rng(0)
    seeds = select_seeds(lib, (0, 1), n_seeds=60, rng=rng)
    unservable = [i for i in seeds if not can_serve("hybrid", lib, i)]
    assert unservable


def test_asking_for_more_seeds_than_exist_returns_what_there_is():
    songs, lib = library(n=25)
    rng = np.random.default_rng(0)
    seeds = select_seeds(lib, (0,), n_seeds=999, rng=rng)
    assert len(seeds) == int((lib.quintile == 0).sum())


def test_empty_quintile_selection_is_rejected():
    songs, lib = library()
    with pytest.raises(ValueError):
        select_seeds(lib, (), n_seeds=5, rng=np.random.default_rng(0))


# ── What the annotator is allowed to see ────────────────────────────────────

def test_task_file_leaks_nothing_that_could_sway_a_judgement():
    """Popularity is the baseline under test. An annotator who can tell which
    candidate is the famous one, or which policy proposed it, stops being
    independent evidence about whether the cold-start ranking works."""
    songs, lib = library()
    rng, tiebreak = pool_args(lib)
    task, key = build_pool(lib, songs, [4, 9], depth=10, rng=rng, tiebreak=tiebreak)

    for s in task["seeds"]:
        for c in s["candidates"]:
            assert set(c) == {"key", "title", "artist"}

    blob = repr(task) + "\n".join(sheet(task))
    for term in ("listeners", "quintile", "hybrid", "acoustic", "tags"):
        assert term not in blob

    # The same facts are kept in the key, which is what scores the judgements.
    assert {"listeners", "quintile", "rankings"} <= set(key["seeds"][0])


def test_candidates_are_shuffled_out_of_policy_order():
    """Order is itself provenance: leaving the union in the order it was built
    puts the first policy's top pick at position one, every time."""
    songs, lib = library(n=120)
    rng, tiebreak = pool_args(lib)
    _, union = pool_seed(lib, 30, depth=10, tiebreak=tiebreak, run_seed=0)
    task, _ = build_pool(lib, songs, [30], depth=10,
                         rng=np.random.default_rng(0), tiebreak=tiebreak)
    shown = [c["key"] for c in task["seeds"][0]["candidates"]]
    assert len(shown) == len(union)
    assert shown != [song_key(songs[j]) for j in union]


def test_key_records_provenance_for_scoring():
    songs, lib = library()
    rng, tiebreak = pool_args(lib)
    task, key = build_pool(lib, songs, [4, 9], depth=10, rng=rng, tiebreak=tiebreak,
                           labelled={4})
    for k in key["seeds"]:
        assert set(k["rankings"]) == set(k["served_by"])
        assert k["pool_size"] == len(set().union(*map(set, k["rankings"].values())))
    # Recorded, not filtered: a seed the labels already reach still gets judged.
    assert [k["has_cf_labels"] for k in key["seeds"]] == [True, False]
    assert len(task["seeds"]) == 2


def test_labels_start_empty_so_the_task_is_the_thing_to_fill_in():
    songs, lib = library()
    rng, tiebreak = pool_args(lib)
    task, _ = build_pool(lib, songs, [4], depth=10, rng=rng, tiebreak=tiebreak)
    assert task["seeds"][0]["labels"] == {}
    assert task["meta"]["n_judgements"] == len(task["seeds"][0]["candidates"])


def test_labelled_means_evaluable_not_merely_present_in_the_ground_truth():
    """Nearly every track has a ground-truth entry; only 1,021 of 1,267 have a
    positive that is actually in the library. Confusing the two would report the
    cold end as fully labelled and hide the gap the pool exists to close."""
    songs, lib = library(n=10)
    keys = [song_key(s) for s in songs]
    gt = {
        keys[0]: ["not::in::library"],   # an entry, but nothing rankable
        keys[1]: [keys[1]],              # only itself
        keys[2]: [keys[5], "absent"],    # one real positive
    }
    assert set(evaluable_seeds(gt, songs)) == {2}
    assert evaluable_seeds(gt, songs)[2] == {5}
