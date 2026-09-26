"""Paths and credentials.

Every path is resolved from the repository root, so the scripts behave the same
whether they are run from the root, from ``scripts/``, or through the Makefile.

Credentials are read from the environment only — nothing secret is ever written
to a tracked file. See ``.env.example`` for the variables involved.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# src/kpoprec/config.py -> src/kpoprec -> src -> repo root
ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = ROOT / "figures"

SONGS_JSON = DATA_DIR / "songs.json"
SONGS_SAMPLE_JSON = DATA_DIR / "songs.sample.json"
GROUND_TRUTH_JSON = DATA_DIR / "ground_truth.json"
GROUND_TRUTH_NSA_JSON = DATA_DIR / "ground_truth_no_same_artist.json"

# What the Spotify playlist import read, kept so a merge can be repeated
# without authorizing again. Gitignored: it is one person's listening.
PLAYLIST_SNAPSHOT = DATA_DIR / "playlist_tracks.json"

# Resumable-run caches. Gitignored: they are large and purely derived.
TAGS_CACHE = DATA_DIR / "tags_cache.json"
ENRICH_CACHE = DATA_DIR / "enrich_cache.json"
GT_CACHE = DATA_DIR / "gt_cache.json"
FEATURES_CACHE = DATA_DIR / "features_cache.json"

# ── API endpoints ───────────────────────────────────────────────────────────
LASTFM_BASE = "https://ws.audioscrobbler.com/2.0/"
MUSICBRAINZ_BASE = "https://musicbrainz.org/ws/2/recording"
RECCOBEATS_BASE = "https://api.reccobeats.com/v1"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_SEARCH_URL = "https://api.spotify.com/v1/search"

# ── Rate limits ─────────────────────────────────────────────────────────────
# Last.fm allows roughly 5 req/s; 0.25 s leaves headroom.
LASTFM_DELAY = 0.25
# MusicBrainz enforces a hard 1 req/s and will ban on sustained excess.
MUSICBRAINZ_DELAY = 1.10
SPOTIFY_SEARCH_DELAY = 0.35

# MusicBrainz requires a User-Agent that identifies the client and a contact.
USER_AGENT = os.environ.get(
    "MUSICBRAINZ_USER_AGENT",
    "kpop-rec/1.0 (https://github.com/snuuym/kpop-rec)",
)


def lastfm_key(required: bool = True) -> str:
    """Return the Last.fm API key from ``LASTFM_API_KEY``.

    Exits with a readable message rather than a traceback when it is missing,
    since every pipeline script fails the same way without it.
    """
    key = os.environ.get("LASTFM_API_KEY", "")
    if not key and required:
        sys.exit(
            "[FATAL] LASTFM_API_KEY is not set.\n"
            "        Get a key at https://www.last.fm/api/account/create\n"
            "        then: export LASTFM_API_KEY=...   (see .env.example)"
        )
    return key


def spotify_credentials() -> tuple[str, str | None]:
    """Return ``(client_id, client_secret)`` from the environment.

    The client ID is not a secret (it is public in the browser PKCE flow), but
    it is still read from the environment so no account-specific value is
    baked into the repository. The secret is only needed by the audio-feature
    pipeline and is never persisted.
    """
    return (
        os.environ.get("SPOTIFY_CLIENT_ID", ""),
        os.environ.get("SPOTIFY_CLIENT_SECRET"),
    )
