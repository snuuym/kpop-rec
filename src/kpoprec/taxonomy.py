"""K-pop sub-genre taxonomy — the single source of truth.

``build_library.py`` and ``backfill_tags.py`` both classify tracks, and they
must agree: a track tagged in the first pass and a track tagged in the backfill
pass have to land in the same bucket, or the sparsity analysis compares two
different label spaces.

Design notes
------------
* Root tags ("k-pop", "kpop", "korean pop") establish *origin*, not *style*.
  They are used to pull candidate tracks but never emitted as sub-genre labels,
  because a label carried by 100% of the corpus has zero discriminative power.
* All matching rules fire, up to ``MAX_SUBGENRES`` — a track can be both
  "Hip-hop" and "Boy group".
* Unclassified tracks fall back to the generic "K-pop" pool rather than to a
  concrete genre. An earlier version defaulted to "Ballad", which silently
  mislabeled 1,110 tracks and made tag-overlap scoring meaningless.
"""

from __future__ import annotations

MAX_SUBGENRES = 5

# Used to PULL tracks from Last.fm. All are definitionally K-pop.
KPOP_ROOT_TAGS = ["k-pop", "kpop", "korean pop"]

# Style descriptors only. "k-pop"/"kpop"/"korean pop" are intentionally absent.
SUBGENRE_RULES: list[tuple[str, list[str]]] = [
    # Vocal / mood
    ("Ballad",        ["ballad", "k-ballad", "korean ballad", "slow jam"]),
    ("R&B",           ["r&b", "k-r&b", "rnb", "neo soul", "soul"]),
    ("Dream pop",     ["dream pop", "shoegaze", "ambient pop", "ethereal", "chillwave"]),
    ("Bubblegum pop", ["bubblegum pop", "bubble pop", "bubblegum", "cute", "kawaii", "aegyo"]),
    # Rhythm / production
    ("Dance pop",     ["dance pop", "electropop", "synth-pop", "synthpop"]),
    ("Electronic",    ["electronic", "edm", "club", "house", "techno", "trance"]),
    ("Hip-hop",       ["hip hop", "hip-hop", "rap", "trap", "k-rap", "k-hip-hop"]),
    ("Rock",          ["rock", "k-rock", "alternative rock", "alt-rock", "punk"]),
    ("Indie",         ["indie", "k-indie", "indie pop", "lo-fi", "lo fi"]),
    # Act type
    ("Girl group",    ["girl group", "girlgroup", "female idol", "idol girl", "girls"]),
    ("Boy group",     ["boy band", "boy group", "boyband", "male idol", "idol group"]),
    ("Solo",          ["solo", "soloist"]),
    # Context / theme
    ("OST",           ["ost", "korean ost", "k-drama ost", "drama ost", "anime ost"]),
    ("Dance",         ["dance", "choreography", "performance"]),
]

# Origin keywords excluded from sub-genre output.
ROOT_KEYWORDS = {"k-pop", "kpop", "korean pop", "korean", "idol", "k pop"}

# Tags this weak are dropped from the raw signal entirely.
RAW_TAG_MIN = 1
# Tags at or above this vote count are trusted for sub-genre classification.
CLASSIFY_MIN = 5

# Tags with zero discriminative power inside a K-pop-only corpus. Removing
# these is what turns a raw tag count into an *effective* tag count, which is
# the quantity the sparsity analysis actually cares about.
NON_DISCRIMINATIVE_TAGS = {
    "k-pop", "kpop", "k pop", "korean pop", "korea", "korean",
    "pop", "music", "favorites", "favourite", "favourites", "favorite",
    "seen live", "female vocalists", "male vocalists", "asian", "asia",
}


def classify_subgenres(track_tags: list[str]) -> list[str]:
    """Map raw Last.fm tags to at most ``MAX_SUBGENRES`` style labels.

    Returns ``["K-pop"]`` when nothing matches, so downstream code can assume a
    non-empty label list without special-casing.
    """
    blob = " ".join(track_tags)
    matched: list[str] = []
    for label, keywords in SUBGENRE_RULES:
        if any(kw in blob for kw in keywords):
            matched.append(label)
        if len(matched) >= MAX_SUBGENRES:
            break
    return matched or ["K-pop"]


def is_effective(tag: str) -> bool:
    """True when a tag carries signal beyond "this is K-pop"."""
    return bool(tag) and tag not in NON_DISCRIMINATIVE_TAGS
