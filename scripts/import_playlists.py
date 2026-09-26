#!/usr/bin/env python3
"""Stage 0b - add the owner's own Spotify playlists to the library.

The library was built from Last.fm tag pages, which is one way of sampling
K-pop. A person's playlists are another: they contain what one listener chose,
whether or not anyone tagged it. Adding them widens the candidate pool, and
because each record carries where it came from (``source``) it also lets the
analysis ask whether the tag-sparsity finding holds under a different sampling
frame.

How it works
------------
1. Authorize once in the browser (OAuth authorization code with PKCE -- no
   client secret needed) and read each playlist's items.
2. Save a slimmed copy of what came back to ``data/playlist_tracks.json``.
3. Merge the new tracks into ``songs.json`` (``kpoprec.playlist``).

Step 3 reads the snapshot, so it can be repeated without authorizing again
(``--from-snapshot``), and a ``--dry-run`` shows what would be added first.

Spotify's rules for a development-mode app (since March 2026)
-------------------------------------------------------------
* ``GET /playlists/{id}/items`` serves only playlists the user owns or
  collaborates on; anything else is a 403.
* The token must carry ``playlist-read-private``.
* The redirect URI must match one registered in the app's dashboard *exactly*.
  The default is the one the web app already registers for port 8080; nothing
  needs adding.

Usage
-----
    export SPOTIFY_CLIENT_ID=...           # public; see .env.example
    export SPOTIFY_PLAYLIST_IDS=id1,id2    # or --playlist <id or share link>
    python3 scripts/import_playlists.py --dry-run
    python3 scripts/import_playlists.py
    python3 scripts/import_playlists.py --from-snapshot    # merge again, offline

Afterwards the new tracks have no tags, listeners, year or audio features. Run
the pipeline stages for them (``make backfill enrich features gt``); every
stage caches, so only the new tracks cost a request.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kpoprec import config, playlist  # noqa: E402
from kpoprec.io import load_songs, read_json, write_json, write_json_with_backup  # noqa: E402

API = "https://api.spotify.com/v1"
# Registered in the app's dashboard already (the web app's second local port).
DEFAULT_REDIRECT = "http://127.0.0.1:8080/kpop-mp3-player.html"
PAGE = 50  # the endpoint's maximum
# Spotify's Retry-After can be hours long when it throttles hard, and this
# account has been locked out for 18 hours before. Sleep through a short one;
# stop and say so on a long one rather than hammer the API.
MAX_RETRY_AFTER = 60


# ── Authorization ───────────────────────────────────────────────────────────

def wait_for_code(redirect_uri: str, state: str, timeout: float = 180.0) -> str:
    """Listen on the redirect URI's host and port until the browser lands on it."""
    u = urlparse(redirect_uri)
    if u.hostname not in ("127.0.0.1", "localhost") or not u.port:
        sys.exit(f"[FATAL] cannot listen on {redirect_uri}: need a local http address with a port")
    got: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server's name)
            target = urlparse(self.path)
            if target.path != u.path:      # a favicon request, say
                self.send_error(404)
                return
            got.update({k: v[0] for k, v in parse_qs(target.query).items()})
            body = (
                b"<!doctype html><meta charset=utf-8><title>kpop-rec</title>"
                b"<body style='font-family:system-ui;margin:3rem'>"
                b"<h2>Authorized.</h2><p>You can close this tab and go back to the terminal.</p>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # keep the terminal to our own output
            pass

    try:
        server = HTTPServer((u.hostname, u.port), Handler)
    except OSError as e:
        sys.exit(f"[FATAL] cannot listen on port {u.port} ({e}). Is the web app running "
                 f"there? Stop it, or pass --redirect-uri with another registered URI.")
    server.timeout = timeout
    deadline = time.time() + timeout
    try:
        while not got and time.time() < deadline:
            server.handle_request()
    finally:
        server.server_close()

    if not got:
        sys.exit(f"[FATAL] no answer from the browser within {timeout:.0f}s")
    if "error" in got:
        sys.exit(f"[FATAL] Spotify refused the authorization: {got['error']}")
    if got.get("state") != state:
        sys.exit("[FATAL] the authorization response did not carry our state; refusing it")
    if "code" not in got:
        sys.exit("[FATAL] the authorization response carried no code")
    return got["code"]


def authorize(client_id: str, redirect_uri: str) -> str:
    """Run the browser flow and return an access token."""
    verifier, challenge = playlist.pkce_pair()
    state = secrets.token_urlsafe(16)
    url = playlist.authorize_url(client_id, redirect_uri, challenge, state)
    print("[auth] opening the browser to approve read access to your playlists.")
    print("       If it does not open, visit:\n")
    print(f"       {url}\n")
    webbrowser.open(url)
    code = wait_for_code(redirect_uri, state)

    r = requests.post(
        config.SPOTIFY_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": verifier,
        },
        timeout=15,
    )
    if r.status_code != 200:
        sys.exit(f"[FATAL] token exchange failed ({r.status_code}): {r.text[:300]}")
    return r.json()["access_token"]


# ── Fetching ────────────────────────────────────────────────────────────────

def get(url: str, token: str, **params) -> requests.Response:
    for _ in range(4):
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"},
                         params=params or None, timeout=20)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", "2"))
            if wait > MAX_RETRY_AFTER:
                sys.exit(f"[FATAL] Spotify asked us to wait {wait}s. Stopping rather than "
                         "pushing on; the snapshot is only written once every playlist is read.")
            time.sleep(wait + 1)
            continue
        return r
    sys.exit("[FATAL] Spotify kept rate-limiting; try again later")


def slim(entry: dict) -> dict:
    """Keep only what ``playlist.track_record`` reads, in the shape it reads it."""
    item = entry.get("item", entry.get("track"))
    if isinstance(item, dict):
        item = {
            "id": item.get("id"),
            "name": item.get("name"),
            "type": item.get("type"),
            "is_local": item.get("is_local"),
            "duration_ms": item.get("duration_ms"),
            "artists": [{"name": a.get("name")} for a in item.get("artists") or []],
            "album": {"release_date": (item.get("album") or {}).get("release_date")},
        }
    return {"added_at": entry.get("added_at"), "is_local": entry.get("is_local"), "item": item}


def fetch_playlist(pid: str, token: str) -> dict:
    meta = get(f"{API}/playlists/{pid}", token, fields="name")
    name = meta.json().get("name", pid) if meta.status_code == 200 else pid

    entries: list[dict] = []
    url, params = f"{API}/playlists/{pid}/items", {"limit": PAGE, "offset": 0}
    while url:
        r = get(url, token, **params)
        if r.status_code == 403:
            sys.exit(
                f"[FATAL] 403 reading playlist {pid} ({name!r}). Spotify serves items only for "
                "playlists you own or collaborate on, to a token with playlist-read-private. "
                "Check that this playlist is yours and that you approved the read access."
            )
        if r.status_code != 200:
            sys.exit(f"[FATAL] reading playlist {pid} failed ({r.status_code}): {r.text[:300]}")
        page = r.json()
        entries += [slim(e) for e in page.get("items") or []]
        url, params = page.get("next"), {}   # `next` already carries its own query
    print(f"[fetch] {name!r}: {len(entries)} entries")
    return {"id": pid, "name": name, "entries": entries}


# ── Reporting ───────────────────────────────────────────────────────────────

def print_report(report: playlist.MergeReport, n_library: int) -> None:
    print(f"\n[merge] {report.entries} playlist entries")
    for reason, n in report.skipped.most_common():
        print(f"        skipped, {reason}: {n}")
    for reason, n in report.duplicates.most_common():
        print(f"        {reason}: {n}")
    print(f"        NEW: {report.added}   (library {n_library} -> {n_library + report.added})")
    if report.variants:
        print(f"\n        {len(report.variants)} entries share a track key with a library track "
              "but not its title, and were left out:")
        for artist, title, held in report.variants[:12]:
            print(f"          {artist}: {title!r}  ~  {held!r}")
        if len(report.variants) > 12:
            print(f"          ... and {len(report.variants) - 12} more")


def main() -> None:
    ap = argparse.ArgumentParser(description="Import Spotify playlists into the library")
    ap.add_argument("--playlist", action="append", default=[],
                    help="playlist id or share link; repeat for several "
                         "(default: SPOTIFY_PLAYLIST_IDS, comma-separated)")
    ap.add_argument("--songs", type=Path, default=config.SONGS_JSON)
    ap.add_argument("--snapshot", type=Path, default=config.PLAYLIST_SNAPSHOT)
    ap.add_argument("--redirect-uri", default=DEFAULT_REDIRECT)
    ap.add_argument("--from-snapshot", action="store_true",
                    help="merge from the saved snapshot; no authorization, no network")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be added, and leave songs.json alone")
    args = ap.parse_args()

    if args.from_snapshot:
        snap = read_json(args.snapshot)
        if not snap:
            sys.exit(f"[FATAL] no snapshot at {args.snapshot}; run without --from-snapshot first")
        print(f"[snapshot] {args.snapshot.name}, fetched {snap.get('fetched', '?')}")
    else:
        raw = args.playlist or [p for p in os.environ.get("SPOTIFY_PLAYLIST_IDS", "").split(",") if p.strip()]
        if not raw:
            sys.exit("[FATAL] no playlists: pass --playlist, or set SPOTIFY_PLAYLIST_IDS (see .env.example)")
        try:
            ids = list(dict.fromkeys(playlist.parse_playlist_id(p) for p in raw))
        except ValueError as e:
            sys.exit(f"[FATAL] {e}")
        client_id, _ = config.spotify_credentials()
        if not client_id:
            sys.exit("[FATAL] SPOTIFY_CLIENT_ID is not set (the client id from your app's "
                     "dashboard; it is public, and the PKCE flow needs no secret).")
        token = authorize(client_id, args.redirect_uri)
        snap = {
            "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "playlists": [fetch_playlist(pid, token) for pid in ids],
        }
        write_json(args.snapshot, snap, indent=1)
        print(f"[snapshot] -> {args.snapshot}")

    songs = load_songs(args.songs)
    entries = [e for p in snap["playlists"] for e in p["entries"]]
    new, report = playlist.merge_playlist_tracks(songs, entries)
    print_report(report, len(songs))

    if args.dry_run:
        print("\n[dry-run] songs.json left untouched")
        return
    if not new:
        print("\n[done] nothing to add")
        return
    write_json_with_backup(args.songs, songs + new)
    print(f"\n[done] {len(new)} tracks appended to {args.songs}; backup -> {args.songs}.bak")
    print("Next: make backfill enrich features gt   (only the new tracks cost a request)")


if __name__ == "__main__":
    main()
