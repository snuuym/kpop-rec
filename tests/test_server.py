"""The write endpoint is the only way user input reaches the library file, so
its validation is the security boundary worth testing."""

import pytest

from server import clean_song


def test_minimal_valid_song():
    song = clean_song({"title": "Hype Boy", "artist": "NewJeans"})
    assert song["title"] == "Hype Boy"
    assert song["artist"] == "NewJeans"


@pytest.mark.parametrize("body", [None, "a string", 42, ["a", "list"]])
def test_non_object_bodies_rejected(body):
    with pytest.raises(ValueError, match="JSON object"):
        clean_song(body)


@pytest.mark.parametrize(
    "body",
    [{}, {"title": "x"}, {"artist": "y"}, {"title": "  ", "artist": "y"}],
)
def test_title_and_artist_required(body):
    with pytest.raises(ValueError, match="required"):
        clean_song(body)


def test_overlong_names_rejected():
    with pytest.raises(ValueError, match="too long"):
        clean_song({"title": "x" * 301, "artist": "y"})


def test_unknown_fields_are_dropped():
    """A whitelist, not a blacklist — arbitrary keys must never reach disk."""
    song = clean_song(
        {"title": "t", "artist": "a", "evil": "payload", "__proto__": "x"}
    )
    assert set(song) == {
        "title", "artist", "tags", "all_tags", "dur", "durStr", "url"
    }


def test_tag_lists_are_capped_and_stringified():
    song = clean_song(
        {"title": "t", "artist": "a", "tags": list(range(100)), "all_tags": ["x"] * 100}
    )
    assert len(song["tags"]) == 30
    assert len(song["all_tags"]) == 60
    assert all(isinstance(t, str) for t in song["tags"])


def test_individual_tags_are_length_capped():
    song = clean_song({"title": "t", "artist": "a", "tags": ["z" * 500]})
    assert len(song["tags"][0]) == 80


def test_non_list_tags_become_empty():
    song = clean_song({"title": "t", "artist": "a", "tags": "not-a-list"})
    assert song["tags"] == []


def test_url_is_truncated():
    song = clean_song({"title": "t", "artist": "a", "url": "u" * 900})
    assert len(song["url"]) == 500


@pytest.mark.parametrize(
    "dur, expected", [("240", 240), (None, 0), ("abc", 0), ("-5", 0)]
)
def test_duration_coercion(dur, expected):
    assert clean_song({"title": "t", "artist": "a", "dur": dur})["dur"] == expected


def test_whitespace_is_stripped():
    song = clean_song({"title": "  Hype Boy  ", "artist": "  NewJeans  "})
    assert song["title"] == "Hype Boy"
    assert song["artist"] == "NewJeans"
