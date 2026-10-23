#!/usr/bin/env python3
"""Build the static, credential-free demo served by GitHub Pages from docs/.

The app needs no credentials to recommend: ranking runs in the browser over
``songs.json``. Served without ``config.json`` it searches the bundled library
instead of Last.fm and plays through the Spotify embed instead of the Web
Playback SDK, so a static copy of the page is a working demo.

What this writes
----------------
``docs/index.html``  the app, byte for byte -- one page, not a fork of it
``docs/songs.json``  the bundled sample, cut to tracks the embed can play and
                     to the fields the page reads
``docs/.nojekyll``   serve the files as they are

What it refuses to write
------------------------
The old Pages demo worked only because a Last.fm key sat in the HTML, which is
how a credential ended up publicly served. So the build fails if the page
carries anything key-shaped, and the library is the committed sample only --
never the full corpus, and never a track from the owner's playlists.

Usage
-----
    python3 scripts/build_demo.py
    python3 -m http.server -d docs 8000      # then open http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kpoprec import config  # noqa: E402
from kpoprec.io import load_songs, write_json  # noqa: E402

APP_HTML = config.ROOT / "app" / "kpop-mp3-player.html"
DOCS = config.ROOT / "docs"

# What the page actually reads from a library entry.
FIELDS = ("title", "artist", "tags", "all_tags", "features", "spotify_id",
          "dur", "durStr", "listeners")

# A Last.fm key is 32 hex characters; a Spotify client ID is 32 alphanumerics.
KEY_SHAPED = re.compile(r"(?<![0-9A-Za-z])[0-9a-fA-F]{32}(?![0-9A-Za-z])")


def demo_library(songs: list[dict]) -> list[dict]:
    """The playable part of the sample, with only the fields the page uses."""
    private = [s for s in songs if s.get("source") == "spotify_playlist"]
    if private:
        raise ValueError(f"{len(private)} playlist tracks in the demo library; "
                         "the demo must not publish the owner's playlists")
    return [{k: s[k] for k in FIELDS if k in s} for s in songs if s.get("spotify_id")]


def check_page(html: str) -> None:
    """Fail on anything that looks like a credential baked into the page."""
    for name in ("LASTFM_KEY", "SPOTIFY_CLIENT_ID"):
        if not re.search(rf'let {name} = "";', html):
            raise ValueError(f"{name} is not empty in the page")
    hit = KEY_SHAPED.search(html)
    if hit:
        raise ValueError(f"key-shaped string in the page: {hit.group(0)[:6]}…")


def build(songs_path: Path, out: Path) -> int:
    html = APP_HTML.read_text(encoding="utf-8")
    check_page(html)
    library = demo_library(load_songs(songs_path))
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(APP_HTML, out / "index.html")
    write_json(out / "songs.json", library)
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return len(library)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the static demo")
    ap.add_argument("--songs", type=Path, default=config.SONGS_SAMPLE_JSON)
    ap.add_argument("--out", type=Path, default=DOCS)
    args = ap.parse_args()
    n = build(args.songs, args.out)
    print(f"[demo] {n} playable tracks -> {args.out / 'songs.json'}")
    print(f"[demo] page -> {args.out / 'index.html'}")
    print(f"[demo] preview: python3 -m http.server -d {args.out} 8000")


if __name__ == "__main__":
    main()
