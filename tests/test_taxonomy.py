"""The taxonomy is shared by two pipeline stages, so its contract matters more
than its individual rules: a track classified in the first pass and the same
track classified in the backfill pass must land in the same bucket."""

import pytest

from kpoprec.taxonomy import (
    KPOP_ROOT_TAGS,
    MAX_SUBGENRES,
    NON_DISCRIMINATIVE_TAGS,
    SUBGENRE_RULES,
    classify_subgenres,
    is_effective,
)


def test_unmatched_tags_fall_back_to_generic_pool():
    """Regression: an earlier version defaulted to "Ballad", which silently
    mislabeled 1,110 tracks and made tag-overlap scoring meaningless."""
    assert classify_subgenres([]) == ["K-pop"]
    assert classify_subgenres(["some unmapped tag"]) == ["K-pop"]
    assert "Ballad" not in classify_subgenres(["nonsense"])


def test_all_matching_rules_fire():
    labels = classify_subgenres(["hip hop", "boy band"])
    assert "Hip-hop" in labels
    assert "Boy group" in labels


def test_result_is_capped():
    every_keyword = [kw for _, kws in SUBGENRE_RULES for kw in kws]
    assert len(classify_subgenres(every_keyword)) <= MAX_SUBGENRES


def test_root_tags_never_become_subgenre_labels():
    """Root tags establish origin, not style. A label carried by 100% of the
    corpus has zero discriminative power and must not be emitted."""
    labels = classify_subgenres(KPOP_ROOT_TAGS)
    assert labels == ["K-pop"]  # the generic fallback, not a matched rule


@pytest.mark.parametrize("tag", ["k-pop", "kpop", "korean", "pop", "favorites"])
def test_non_discriminative_tags_are_not_effective(tag):
    assert not is_effective(tag)


@pytest.mark.parametrize("tag", ["ballad", "electropop", "trap", "shoegaze"])
def test_genuine_style_tags_are_effective(tag):
    assert is_effective(tag)


def test_empty_tag_is_not_effective():
    assert not is_effective("")


def test_subgenre_keywords_disjoint_from_root_keywords():
    """A style rule keyed on a root keyword would fire for the whole corpus."""
    for label, keywords in SUBGENRE_RULES:
        overlap = set(keywords) & NON_DISCRIMINATIVE_TAGS
        assert not overlap, f"{label} matches non-discriminative tag(s): {overlap}"


def test_classification_is_deterministic():
    tags = ["rnb", "girl group", "dance"]
    assert classify_subgenres(tags) == classify_subgenres(tags)
