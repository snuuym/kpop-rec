"""Normalization is the join between three APIs that spell tracks differently.

A weak join silently deflates the ground-truth positive count, which would look
like "the labels are sparse" rather than "the join is broken" — so these are
correctness tests, not cosmetics.
"""

import pytest

from kpoprec.normalize import clean_for_search, key_of, norm, normalize_tag, song_key


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Hype Boy", "hype boy"),
        ("HYPE BOY", "hype boy"),
        ("  Hype   Boy  ", "hype boy"),
        ("Hype Boy (feat. Someone)", "hype boy"),
        ("Hype Boy (Feat. Someone)", "hype boy"),
        ("Hype Boy [MV]", "hype boy"),
        ("Hype Boy feat. Someone", "hype boy"),
        ("Hype-Boy!", "hype boy"),
    ],
)
def test_variants_collapse_to_one_key(raw, expected):
    assert norm(raw) == expected


def test_fullwidth_characters_fold():
    """NFKC folding — full-width text appears in Korean-sourced metadata."""
    assert norm("ＨＹＰＥ") == "hype"


def test_key_joins_artist_and_title():
    assert key_of("NewJeans", "Hype Boy") == "newjeans::hype boy"


def test_key_is_stable_across_spelling_variants():
    a = key_of("NewJeans", "Hype Boy (feat. X)")
    b = key_of("newjeans", "HYPE BOY")
    assert a == b


def test_song_key_matches_key_of():
    song = {"artist": "BTS", "title": "Epiphany"}
    assert song_key(song) == key_of("BTS", "Epiphany")


def test_song_key_tolerates_missing_fields():
    assert song_key({}) == "::"


@pytest.mark.parametrize(
    "raw, expected",
    [("  K-Pop  ", "k-pop"), ("R&B,", "r&b"), ("-dance-", "dance")],
)
def test_normalize_tag(raw, expected):
    assert normalize_tag(raw) == expected


def test_clean_for_search_preserves_readability():
    """Outbound queries keep case and punctuation — MusicBrainz and Spotify
    match better on a human-readable string than on a flattened one."""
    assert clean_for_search("Epiphany (feat. X)") == "Epiphany"
    assert clean_for_search("Epiphany - Remastered") == "Epiphany"
    assert clean_for_search("Epiphany [MV]") == "Epiphany"
    assert clean_for_search("Don't Stop") == "Don't Stop"


def test_distinct_tracks_do_not_collide():
    assert key_of("BTS", "Dynamite") != key_of("BTS", "Butter")
    assert key_of("IU", "Blueming") != key_of("BTS", "Blueming")
