"""
K-Pop Recommender — local server
---------------------------------
Serves the single-file web app over http://127.0.0.1:5000 (so fetch('songs.json')
works, unlike file://) and adds ONE write endpoint:

    POST /library/add   { title, artist, tags[], all_tags[], dur, durStr, url }

When the web app is searched with a seed song that is NOT yet in the library,
the front-end posts that song here and it gets appended to songs.json. The next
run of build_features.py picks it up and fills in audio features.

Design notes:
  * Binds to 127.0.0.1 only — not reachable from the network.
  * Whitelists/validates every field; never writes arbitrary keys.
  * Backs up songs.json -> songs.json.bak, then writes atomically (tmp + replace)
    so an interrupted write can't corrupt the library.
  * Dedups by "artist::title" (case-insensitive); a repeat is a no-op.

Run:
    pip3 install flask
    python3 server.py
then open http://127.0.0.1:5000
"""

import json, os, tempfile
from flask import Flask, request, jsonify, send_from_directory

HERE       = os.path.dirname(os.path.abspath(__file__))
SONGS_FILE = os.path.join(HERE, "songs.json")
BACKUP     = os.path.join(HERE, "songs.json.bak")
APP_HTML   = "kpop-mp3-player.html"

# Fields we accept from the front-end and their expected types.
STR_FIELDS  = ("title", "artist", "durStr", "url")
LIST_FIELDS = ("tags", "all_tags")

app = Flask(__name__, static_folder=HERE, static_url_path="")


# ── Serve the app ───────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(HERE, APP_HTML)


# ── Validation ──────────────────────────────────────────────────────────────
def clean_song(data):
    """Return a sanitized song dict, or raise ValueError. Only whitelisted
    fields survive; lists are capped and coerced to strings."""
    if not isinstance(data, dict):
        raise ValueError("body must be a JSON object")

    title  = str(data.get("title", "")).strip()
    artist = str(data.get("artist", "")).strip()
    if not title or not artist:
        raise ValueError("title and artist are required")
    if len(title) > 300 or len(artist) > 300:
        raise ValueError("title/artist too long")

    song = {
        "title":  title,
        "artist": artist,
        "tags":     [str(t)[:80] for t in (data.get("tags") or [])][:30]
                    if isinstance(data.get("tags"), list) else [],
        "all_tags": [str(t)[:80] for t in (data.get("all_tags") or [])][:60]
                    if isinstance(data.get("all_tags"), list) else [],
        "dur":    int(data["dur"]) if str(data.get("dur", "")).isdigit() else 0,
        "durStr": str(data.get("durStr", "0:00"))[:12],
        "url":    str(data.get("url", ""))[:500],
    }
    return song


# ── Atomic, backed-up write ─────────────────────────────────────────────────
def write_songs(songs):
    # Back up the current file first.
    if os.path.exists(SONGS_FILE):
        with open(SONGS_FILE, encoding="utf-8") as f:
            current = f.read()
        with open(BACKUP, "w", encoding="utf-8") as f:
            f.write(current)
    # Write to a temp file in the same dir, then atomically replace.
    fd, tmp = tempfile.mkstemp(dir=HERE, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(songs, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SONGS_FILE)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


# ── The one write endpoint ──────────────────────────────────────────────────
@app.route("/library/add", methods=["POST"])
def library_add():
    data = request.get_json(force=True, silent=True)
    try:
        song = clean_song(data)
    except ValueError as e:
        return jsonify(added=False, reason=str(e)), 400

    # Quality guard (A): refuse tag-less songs by default — an empty all_tags is
    # the signature of a mislabeled Last.fm match (the old "Hype Boy - NewJeans" /
    # "Sky" junk had none). The front-end may set force=true when the user has
    # manually approved a tag-less but correctly-identified song (e.g. an obscure
    # release with no Last.fm tags), which bypasses this guard.
    force = bool(isinstance(data, dict) and data.get("force"))
    if not song["all_tags"] and not force:
        return jsonify(added=False, reason="no tags — skipped to avoid junk entries")

    with open(SONGS_FILE, encoding="utf-8") as f:
        songs = json.load(f)

    key = f"{song['artist'].lower()}::{song['title'].lower()}"
    existing = {f"{s['artist'].lower()}::{s['title'].lower()}" for s in songs}
    if key in existing:
        return jsonify(added=False, reason="already in library", total=len(songs))

    songs.append(song)
    write_songs(songs)
    return jsonify(added=True, total=len(songs))


if __name__ == "__main__":
    print("K-Pop recommender running at  http://127.0.0.1:5000")
    print("Open that URL in your browser. Ctrl-C to stop.")
    app.run(host="127.0.0.1", port=5000, debug=False)
