#!/usr/bin/env python3
"""Local Flask server for the single-file web app.

Exists for three reasons, in order of importance:

1. ``fetch('songs.json')`` does not work from ``file://``, so the library has
   to be served over HTTP.
2. Credentials must not live in the HTML. This process reads them from the
   environment and hands them to the page at ``GET /config.json``.
3. Searching for a track that is not in the library appends it, via the single
   write endpoint ``POST /library/add``.

Safety properties of the write path:

* binds to 127.0.0.1 only — not reachable from the network;
* every field is whitelisted, length-capped and coerced — arbitrary keys never
  reach the library file;
* the library is backed up and then written atomically, so an interrupted
  write cannot corrupt hours of collected data;
* de-duplicates on ``"artist::title"``; a repeat is a no-op.

Run
---
    pip install -r requirements.txt
    export LASTFM_API_KEY=...        # see .env.example
    export SPOTIFY_CLIENT_ID=...     # optional, for playback
    python3 app/server.py

then open http://127.0.0.1:5000
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kpoprec import config  # noqa: E402
from kpoprec.io import write_json_with_backup  # noqa: E402

APP_DIR = Path(__file__).resolve().parent
APP_HTML = "kpop-mp3-player.html"

HOST = os.environ.get("KPOPREC_HOST", "127.0.0.1")
PORT = int(os.environ.get("KPOPREC_PORT", "5000"))

# Accepted from the front end, with their expected types.
STR_FIELDS = ("title", "artist", "durStr", "url")
LIST_FIELDS = ("tags", "all_tags")

MAX_NAME_LEN = 300
MAX_TAG_LEN = 80
MAX_TAGS = 30
MAX_ALL_TAGS = 60

app = Flask(__name__, static_folder=str(APP_DIR), static_url_path="")


# ── Serving ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(APP_DIR, APP_HTML)


@app.route("/songs.json")
def songs_json():
    """Serve the library from data/, falling back to the bundled sample.

    The fallback is what makes a fresh clone usable: without it the app is a
    blank screen until someone spends 20 minutes running the full pipeline.
    """
    path = config.SONGS_JSON if config.SONGS_JSON.exists() else config.SONGS_SAMPLE_JSON
    if not path.exists():
        return jsonify(error="no library found; run `make library`"), 404
    return send_from_directory(path.parent, path.name)


@app.route("/config.json")
def client_config():
    """Hand the page its runtime credentials.

    A browser app cannot hide an API key, so this is not a security boundary —
    it is what keeps keys out of the repository. The Spotify *secret* is
    deliberately never included: the page uses PKCE and does not need one.
    """
    client_id, _ = config.spotify_credentials()
    return jsonify(
        lastfm_api_key=os.environ.get("LASTFM_API_KEY", ""),
        spotify_client_id=client_id,
    )


# ── Validation ──────────────────────────────────────────────────────────────

def clean_song(data) -> dict:
    """Return a sanitized song dict, or raise ``ValueError``."""
    if not isinstance(data, dict):
        raise ValueError("body must be a JSON object")

    title = str(data.get("title", "")).strip()
    artist = str(data.get("artist", "")).strip()
    if not title or not artist:
        raise ValueError("title and artist are required")
    if len(title) > MAX_NAME_LEN or len(artist) > MAX_NAME_LEN:
        raise ValueError("title/artist too long")

    def tag_list(field: str, cap: int) -> list[str]:
        value = data.get(field)
        if not isinstance(value, list):
            return []
        return [str(t)[:MAX_TAG_LEN] for t in value][:cap]

    return {
        "title": title,
        "artist": artist,
        "tags": tag_list("tags", MAX_TAGS),
        "all_tags": tag_list("all_tags", MAX_ALL_TAGS),
        "dur": int(data["dur"]) if str(data.get("dur", "")).isdigit() else 0,
        "durStr": str(data.get("durStr", "0:00"))[:12],
        "url": str(data.get("url", ""))[:500],
    }


# ── The one write endpoint ──────────────────────────────────────────────────

@app.route("/library/add", methods=["POST"])
def library_add():
    data = request.get_json(force=True, silent=True)
    try:
        song = clean_song(data)
    except ValueError as e:
        return jsonify(added=False, reason=str(e)), 400

    # An empty all_tags is the signature of a mislabeled Last.fm match rather
    # than a genuinely untagged track, so it is refused by default. The front
    # end sets force=true once a human has confirmed the match is correct —
    # obscure releases really do exist with no tags at all.
    force = bool(isinstance(data, dict) and data.get("force"))
    if not song["all_tags"] and not force:
        return jsonify(added=False, reason="no tags — skipped to avoid junk entries")

    if not config.SONGS_JSON.exists():
        return jsonify(added=False, reason="no writable library; run `make library`"), 409

    songs = json.loads(config.SONGS_JSON.read_text(encoding="utf-8"))
    key = f"{song['artist'].lower()}::{song['title'].lower()}"
    existing = {f"{s['artist'].lower()}::{s['title'].lower()}" for s in songs}
    if key in existing:
        return jsonify(added=False, reason="already in library", total=len(songs))

    songs.append(song)
    write_json_with_backup(config.SONGS_JSON, songs)
    return jsonify(added=True, total=len(songs))


if __name__ == "__main__":
    if not os.environ.get("LASTFM_API_KEY"):
        print("[warn] LASTFM_API_KEY is not set — search and auto-extend are disabled.")
        print("       See .env.example.")
    print(f"K-pop recommender running at  http://{HOST}:{PORT}")
    print("Ctrl-C to stop.")
    app.run(host=HOST, port=PORT, debug=False)
