"""The static demo is published as-is, so what it may contain is the thing to
test: no credentials in the page, no playlist tracks in the library, and no
drift between the demo page and the app it is a copy of."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_demo import APP_HTML, DOCS, build, check_page, demo_library  # noqa: E402


def test_playlist_tracks_are_refused():
    songs = [{"title": "a", "artist": "b", "spotify_id": "x", "source": "spotify_playlist"}]
    with pytest.raises(ValueError, match="playlist"):
        demo_library(songs)


def test_only_playable_tracks_and_known_fields_survive():
    songs = [
        {"title": "a", "artist": "b", "spotify_id": "x", "mbid": "m", "url": "u"},
        {"title": "c", "artist": "d"},
    ]
    assert demo_library(songs) == [{"title": "a", "artist": "b", "spotify_id": "x"}]


def test_a_key_in_the_page_fails_the_build():
    page = APP_HTML.read_text(encoding="utf-8")
    check_page(page)
    with pytest.raises(ValueError, match="LASTFM_KEY"):
        check_page(page.replace('let LASTFM_KEY = "";', 'let LASTFM_KEY = "abc";'))
    with pytest.raises(ValueError, match="key-shaped"):
        check_page(page + "\n// 0123456789abcdef0123456789abcdef\n")


def test_build_writes_the_app_unchanged(tmp_path):
    n = build(ROOT / "data" / "songs.sample.json", tmp_path)
    assert (tmp_path / "index.html").read_bytes() == APP_HTML.read_bytes()
    library = json.loads((tmp_path / "songs.json").read_text(encoding="utf-8"))
    assert len(library) == n > 0
    assert all(s.get("spotify_id") for s in library)


def test_committed_demo_matches_the_app():
    """Pages serves docs/index.html; editing the app without `make demo`
    would publish a stale page."""
    published = DOCS / "index.html"
    if not published.exists():
        pytest.skip("demo not built")
    assert published.read_bytes() == APP_HTML.read_bytes(), "run `make demo`"
