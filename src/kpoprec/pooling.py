"""Build a pooled annotation task for the cold end of the catalogue.

Why this exists
---------------
The benchmark's labels come from Last.fm's ``track.getSimilar``, and those
labels thin out exactly where the project's argument lives. Only 43% of the
coldest quintile has any positive at all, so the other 57% never enters the
evaluation: those seeds are not scored badly, they are not scored. Every cold
-end number in the report is therefore computed on the warmest 43% of the cold
end. No amount of metric work fixes that -- the labels are missing, and the
only way to get numbers for those tracks is to look at them by hand.

Two design decisions do all the work here.

**Pool across policies, not from one.** Judge one policy's top ten and its
misses are the only misses anyone ruled on; every rival is scored on candidates
nobody assessed, and the policy the pool came from wins by construction. The
union of all five policies' top ``depth`` fixes that: each policy's own top
``depth`` is fully judged, so within that depth no policy is charged for an
unseen candidate. Deeper than ``depth`` the labels genuinely run out, which is
what ``evaluate_ranking(judged=...)`` condenses away rather than guesses at.

**Show the annotator nothing that could sway them.** The task file carries
title and artist and nothing else -- no listener counts, no tags, no policy
attribution, and the candidates arrive shuffled. Popularity is the baseline
under test; an annotator who can see which track is the famous one is no longer
an independent source of evidence about whether the cold-start ranking works.
The provenance goes in a separate key file, which is read only when scoring.

Seeds are sampled uniformly from the requested quintiles, including seeds no
content policy can serve and seeds that have no Last.fm labels. Both belong in
the sample: how often the cold end cannot be served at all is one of the things
the exercise is meant to measure, and filtering them out would rebuild the
selection bias this whole file exists to escape.
"""

from __future__ import annotations

import numpy as np

from kpoprec.normalize import song_key
from kpoprec.recommend import (
    POLICIES,
    QUINTILE_LABELS,
    Library,
    can_serve,
    policy_rng,
    score,
    top_k,
)


def evaluable_seeds(gt: dict[str, list[str]], songs: list[dict]) -> dict[int, set[int]]:
    """Seed index -> its in-library positives, for every seed that has any.

    Having a ground-truth *entry* is not the same as being evaluable, and the
    gap is large: nearly every track has an entry, but Last.fm's similar list
    is mostly tracks this library does not contain, so only 1,021 of 1,267
    seeds end up with a positive that can actually be ranked. The benchmark and
    the annotation pool must agree about which is which -- one calling a seed
    labelled while the other scores it as unlabelled would misreport exactly
    the coverage gap the pool exists to close.
    """
    index = {song_key(s): i for i, s in enumerate(songs)}
    out = {}
    for key, positives in gt.items():
        i = index.get(key)
        if i is None:
            continue
        pos = {index[p] for p in positives if p in index and index[p] != i}
        if pos:
            out[i] = pos
    return out


def select_seeds(
    lib: Library,
    quintiles: tuple[int, ...],
    n_seeds: int,
    rng: np.random.Generator,
) -> list[int]:
    """Sample ``n_seeds`` library indices spread evenly over ``quintiles``.

    Even spread, not proportional: the point is to compare strata, so an equal
    number from each keeps every stratum's estimate equally precise. Remainders
    go to the earliest (coldest) quintiles, and a quintile with fewer tracks
    than its share contributes all of them.
    """
    if not quintiles:
        raise ValueError("no quintiles requested")

    pools = {q: np.flatnonzero(lib.quintile == q) for q in quintiles}
    for q, idx in pools.items():
        if len(idx) == 0:
            raise ValueError(f"quintile {QUINTILE_LABELS[q]} is empty")

    base, extra = divmod(n_seeds, len(quintiles))
    picked: list[int] = []
    for rank, q in enumerate(quintiles):
        want = min(base + (1 if rank < extra else 0), len(pools[q]))
        picked += [int(i) for i in rng.choice(pools[q], size=want, replace=False)]
    return sorted(picked)


def pool_seed(
    lib: Library,
    i: int,
    depth: int,
    tiebreak: np.ndarray,
    run_seed: int,
) -> tuple[dict[str, list[int]], list[int]]:
    """Rank seed ``i`` under every policy and return ``(per policy, union)``.

    A policy with no signal for this seed contributes nothing rather than a
    ranking it cannot justify -- the same ``can_serve`` distinction the
    benchmark makes, kept here so an unservable policy does not quietly pad the
    pool with candidates it did not really choose.
    """
    per_policy: dict[str, list[int]] = {}
    union: list[int] = []
    seen: set[int] = set()
    for policy in POLICIES:
        if not can_serve(policy, lib, i):
            continue
        scores = score(policy, lib, i, policy_rng(run_seed, i))
        ranked = [int(j) for j in top_k(scores, depth, tiebreak)]
        per_policy[policy] = ranked
        for j in ranked:
            if j not in seen:
                seen.add(j)
                union.append(j)
    return per_policy, union


def build_pool(
    lib: Library,
    songs: list[dict],
    seeds: list[int],
    depth: int,
    rng: np.random.Generator,
    tiebreak: np.ndarray,
    run_seed: int = 0,
    labelled: set[int] | None = None,
) -> tuple[dict, dict]:
    """Return ``(task, key)``: the file a human labels, and the one that scores it.

    ``labelled`` is the set of seed indices the CF labels can already evaluate,
    from ``evaluable_seeds``. It is recorded per seed and never used to filter,
    so the finished judgements can be split into "agrees with CF where CF
    exists" and "the part CF could not reach" without a second pass.
    """
    task_seeds, key_seeds = [], []

    for i in seeds:
        per_policy, union = pool_seed(lib, i, depth, tiebreak, run_seed)
        # Shuffle so list position carries no information about which policy
        # ranked a candidate first, or how highly.
        shown = [int(j) for j in rng.permutation(union)]
        key = song_key(songs[i])

        task_seeds.append({
            "seed": key,
            "seed_title": songs[i].get("title", ""),
            "seed_artist": songs[i].get("artist", ""),
            "candidates": [
                {
                    "key": song_key(songs[j]),
                    "title": songs[j].get("title", ""),
                    "artist": songs[j].get("artist", ""),
                }
                for j in shown
            ],
            # Filled in by hand: candidate key -> 1 relevant / 0 not.
            "labels": {},
        })
        key_seeds.append({
            "seed": key,
            "quintile": QUINTILE_LABELS[int(lib.quintile[i])],
            "listeners": int(lib.listeners[i]),
            "has_cf_labels": bool(labelled and i in labelled),
            "served_by": sorted(per_policy),
            "pool_size": len(union),
            "rankings": {
                p: [song_key(songs[j]) for j in ranked] for p, ranked in per_policy.items()
            },
        })

    counts = {
        "depth": depth,
        "n_seeds": len(seeds),
        "n_judgements": sum(len(s["candidates"]) for s in task_seeds),
    }
    # The task carries only what judging requires. Which policies were pooled,
    # and how the seeds were drawn, are facts about the experiment rather than
    # about any candidate -- they live in the key, which is not open while
    # anyone is labelling.
    key_meta = dict(counts, policies=list(POLICIES), n_policies=len(POLICIES))
    task_meta = dict(counts, n_policies=len(POLICIES))
    return ({"meta": task_meta, "seeds": task_seeds},
            {"meta": key_meta, "seeds": key_seeds})


def sheet(task: dict) -> list[str]:
    """A markdown worksheet for doing the judgements by hand.

    Built from the task alone, so it cannot carry anything the task file does
    not. Aggregate facts about the sample -- how many of these seeds no content
    policy can rank, how many the Last.fm labels already reach -- are genuinely
    interesting, and they belong in the run's console output rather than on the
    page someone is reading while they judge.
    """
    meta = task["meta"]
    md = [
        "# Annotation pool\n",
        f"{meta['n_seeds']} seeds, pooled to depth {meta['depth']} across "
        f"{meta['n_policies']} ranking policies: **{meta['n_judgements']} judgements**.\n",
        "For each seed, mark every candidate you would be happy to hear next.",
        "Judge the pair, not the track: a good song that does not follow from the",
        "seed is a `0`. Record verdicts under `labels` in the task JSON.\n",
        "Candidates are shuffled and carry no listener count, tag, or attribution,",
        "so the judgements stay independent of the ranking being tested.\n",
        "Re-judge a tenth of these after a few days and report the agreement; a",
        "self-consistency number is what separates an annotation from an opinion.\n",
    ]
    for n, s in enumerate(task["seeds"], 1):
        md.append(f"\n## {n}. {s['seed_artist']} — {s['seed_title']}\n")
        for c in s["candidates"]:
            md.append(f"- [ ] {c['artist']} — {c['title']}")
    return md
