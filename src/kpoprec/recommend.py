"""Ranking policies, lifted out of the browser app so they can be benchmarked.

The app ranks in JavaScript, inside ``app/kpop-mp3-player.html``. A benchmark
cannot call that, and re-deriving the scoring rules by eye is exactly how two
copies drift apart, so the rules live here and the app's behaviour is mirrored
term for term.

Two things the app does are deliberately **not** reproduced, because they exist
to make a 50-track queue pleasant to listen to and would only add noise to a
ranking measurement:

* the random jitter added to every score, and the weighted shuffle;
* the per-tag diversity cap applied when the queue is finally cut.

Both act after the ranking is decided. What is measured here is the ranking.

Every policy returns a score vector over the whole library -- higher is better,
one entry per song, same order as the input list. Ranking is then just an
argsort, which keeps the policies comparable and keeps the metric code from
having to know anything about how a score was produced.
"""

from __future__ import annotations

import numpy as np

from kpoprec.normalize import normalize_tag
from kpoprec.taxonomy import is_effective

# Perceptual weights, copied from the app: mood and energy dominate, production
# traits matter less. Order fixes the column layout of the feature matrix.
FEATURE_WEIGHTS: dict[str, float] = {
    "energy": 1.0,
    "valence": 1.0,
    "danceability": 1.0,
    "acousticness": 0.7,
    "tempo": 0.6,
    "instrumentalness": 0.5,
    "speechiness": 0.4,
    "liveness": 0.3,
    "loudness": 0.3,
}
FEATURE_KEYS: list[str] = list(FEATURE_WEIGHTS)
_W = np.array([FEATURE_WEIGHTS[k] for k in FEATURE_KEYS], dtype=float)

# Defaults for a missing field, and the two rescalings that put every feature on
# a 0..1 axis so a euclidean distance is meaningful. Same constants as the app.
_DEFAULTS = {
    "danceability": 0.5,
    "energy": 0.5,
    "valence": 0.5,
    "acousticness": 0.5,
    "instrumentalness": 0.0,
    "speechiness": 0.1,
    "liveness": 0.2,
}
TEMPO_SCALE = 250.0
LOUDNESS_OFFSET, LOUDNESS_SCALE = 60.0, 60.0

# The app's feature mode keeps the 150 nearest neighbours and adds a small tag
# bonus within that shortlist; everything else is backfill scored far below.
NEIGHBOURHOOD = 150
TAG_BONUS = 0.02
# Tag mode weights a classified-genre hit above a raw shared tag.
RAW_TAG_WEIGHT = 0.5
# Featureless tracks are reachable only as backfill, at a tenth of tag weight.
BACKFILL_SCALE = 0.1


def feature_vec(f: dict | None) -> np.ndarray:
    """One song's features as a 0..1 vector in ``FEATURE_KEYS`` order."""
    f = f or {}
    out = np.empty(len(FEATURE_KEYS), dtype=float)
    for i, k in enumerate(FEATURE_KEYS):
        if k == "tempo":
            out[i] = min(1.0, (f.get("tempo") or 120.0) / TEMPO_SCALE)
        elif k == "loudness":
            lo = f.get("loudness")
            lo = -10.0 if lo is None else lo
            out[i] = min(1.0, max(0.0, (lo + LOUDNESS_OFFSET) / LOUDNESS_SCALE))
        else:
            v = f.get(k)
            out[i] = _DEFAULTS[k] if v is None else v
    return out


def has_features(song: dict) -> bool:
    """The app's test: a features object that actually carries danceability."""
    f = song.get("features") or {}
    return bool(f) and f.get("danceability") is not None


def effective_tags(song: dict) -> set[str]:
    """Normalized raw tags with the universal K-pop root tags removed."""
    return {t for t in (normalize_tag(x) for x in (song.get("all_tags") or [])) if t and is_effective(t)}


def classified_tags(song: dict) -> set[str]:
    """The pipeline's sub-genre labels for a song."""
    return set(song.get("tags") or [])


class Library:
    """Precomputed views of the library that every policy reads.

    Built once and reused across seeds; the per-seed work is then a couple of
    vector operations rather than a re-walk of the corpus.
    """

    def __init__(self, songs: list[dict]) -> None:
        self.songs = songs
        self.n = len(songs)
        self.matrix = np.vstack([feature_vec(s.get("features")) for s in songs])
        self.has_feat = np.array([has_features(s) for s in songs], dtype=bool)
        self.eff_tags = [effective_tags(s) for s in songs]
        self.cls_tags = [classified_tags(s) for s in songs]
        self.listeners = np.array([s.get("listeners") or 0 for s in songs], dtype=float)
        self.artist = np.array([str(s.get("artist", "")).strip().lower() for s in songs])

    def same_artist(self, i: int) -> np.ndarray:
        """Mask of tracks by the seed's own artist, the seed included.

        Used only when scoring. The shipped recommender deliberately keeps
        same-artist tracks -- another song by an artist you just played is
        usually a good suggestion -- but Last.fm's ``track.getSimilar`` is
        artist-deduplicated, so the labels almost never contain one and cannot
        judge those slots either way. Reporting a variant that drops them from
        both the ranking and the positives says how much of a score depends on
        recommendations the benchmark is blind to.
        """
        return self.artist == self.artist[i]

    def distances(self, i: int) -> np.ndarray:
        """Weighted euclidean distance from song ``i`` to every song."""
        diff = self.matrix - self.matrix[i]
        return np.sqrt((_W * diff * diff).sum(axis=1))


# ── Policies ────────────────────────────────────────────────────────────────
# Each returns a score vector over the library. The seed's own slot is set to
# -inf so it can never be recommended back to itself.


def _blank(lib: Library, i: int) -> np.ndarray:
    s = np.zeros(lib.n, dtype=float)
    s[i] = -np.inf
    return s


def score_popularity(lib: Library, i: int) -> np.ndarray:
    """Rank by listener count. The baseline a content method has to beat."""
    s = lib.listeners.astype(float).copy()
    s[i] = -np.inf
    return s


def score_random(lib: Library, i: int, rng: np.random.Generator) -> np.ndarray:
    """Uniform noise. The floor any method must clear to mean anything."""
    s = rng.random(lib.n)
    s[i] = -np.inf
    return s


def score_tags(lib: Library, i: int) -> np.ndarray:
    """Tag mode: classified-genre overlap, plus raw shared tags at half weight."""
    seed_cls, seed_eff = lib.cls_tags[i], lib.eff_tags[i]
    s = _blank(lib, i)
    for j in range(lib.n):
        if j == i:
            continue
        s[j] = len(lib.cls_tags[j] & seed_cls) + RAW_TAG_WEIGHT * len(lib.eff_tags[j] & seed_eff)
    return s


def score_acoustic(lib: Library, i: int) -> np.ndarray:
    """Feature mode: nearest neighbours by weighted feature distance."""
    s = _blank(lib, i)
    d = lib.distances(i)
    s[lib.has_feat] = 1.0 / (1.0 + d[lib.has_feat])
    s[~lib.has_feat] = 0.0
    s[i] = -np.inf
    return s


def score_hybrid(lib: Library, i: int) -> np.ndarray:
    """What the app actually ships.

    Feature distance when the seed has features, with a small tag bonus inside
    the nearest-neighbour shortlist and featureless tracks demoted to backfill;
    tag mode otherwise.
    """
    if not lib.has_feat[i]:
        return score_tags(lib, i)

    s = _blank(lib, i)
    d = lib.distances(i)
    feat_idx = np.flatnonzero(lib.has_feat)
    feat_idx = feat_idx[feat_idx != i]
    nearest = feat_idx[np.argsort(d[feat_idx], kind="stable")[:NEIGHBOURHOOD]]

    seed_cls, seed_eff = lib.cls_tags[i], lib.eff_tags[i]
    for j in nearest:
        s[j] = 1.0 / (1.0 + d[j]) + TAG_BONUS * len(lib.cls_tags[j] & seed_cls)

    # Everything the shortlist did not reach is backfill: tag-scored, far below.
    rest = np.ones(lib.n, dtype=bool)
    rest[nearest] = False
    rest[i] = False
    for j in np.flatnonzero(rest):
        overlap = len(lib.cls_tags[j] & seed_cls) + RAW_TAG_WEIGHT * len(lib.eff_tags[j] & seed_eff)
        s[j] = overlap * BACKFILL_SCALE
    s[i] = -np.inf
    return s


# ── Serviceability ──────────────────────────────────────────────────────────
# A policy that cannot see the signal it needs does not produce a weak ranking,
# it produces no ranking. Scoring those seeds as if they were ordinary failures
# hides the difference; ignoring them flatters the policy. The harness needs to
# know which is which, so it asks here.


def can_serve(policy: str, lib: Library, i: int) -> bool:
    """Whether ``policy`` has any signal at all for seed ``i``.

    For tags this is ``n_eff > 0`` -- the same definition of "has a usable tag"
    the sparsity analysis uses, so the benchmark and the EDA cannot disagree
    about what counts as signal. Classified labels are not a separate escape
    hatch: every track carries at least one, but for a track with no effective
    raw tag that label is the generic K-pop pool, which matches most of the
    library and therefore discriminates nothing. Counting it as signal would
    report 100% tag coverage for a corpus that is 72.7% untagged.
    """
    if policy == "tags":
        return bool(lib.eff_tags[i])
    if policy == "acoustic":
        return bool(lib.has_feat[i])
    if policy == "hybrid":
        return bool(lib.has_feat[i] or lib.eff_tags[i])
    return True  # popularity and random always have something to say


POLICIES = ("random", "popularity", "tags", "acoustic", "hybrid")


def score(policy: str, lib: Library, i: int, rng: np.random.Generator) -> np.ndarray:
    if policy == "random":
        return score_random(lib, i, rng)
    if policy == "popularity":
        return score_popularity(lib, i)
    if policy == "tags":
        return score_tags(lib, i)
    if policy == "acoustic":
        return score_acoustic(lib, i)
    if policy == "hybrid":
        return score_hybrid(lib, i)
    raise ValueError(f"unknown policy: {policy}")


def top_k(scores: np.ndarray, k: int, tiebreak: np.ndarray) -> np.ndarray:
    """Indices of the ``k`` highest scores, best first, ties broken at random.

    ``tiebreak`` must be a fixed permutation supplied by the caller, which keeps
    a run reproducible while removing a real measurement artifact: the library
    is stored roughly in the order it was collected, and collection ran in
    descending popularity, so index order correlates with popularity at about
    rho = 0.29. Breaking ties by index would hand any policy that scores a large
    block of candidates equally -- exactly what a tag policy does for a seed
    with no discriminative tag -- a free slice of the popularity baseline, and
    it would score well above random for no reason of its own.
    """
    k = min(k, len(scores))
    return np.lexsort((tiebreak, -scores))[:k]
