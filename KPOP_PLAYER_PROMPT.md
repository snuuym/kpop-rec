# K-Pop Retro MP3 Player — Project Handoff for Claude Code

## Project Overview
A personal K-pop recommendation web app styled as a retro pink MP3 player (iPod
nano aesthetic). Single user with Spotify Premium. Self-contained HTML/JS + a
small local Python (Flask) server. Recommends K-pop songs by sub-genre tags and
audio-feature similarity, and plays them via the Spotify Web Playback SDK.

> This doc reflects the **current** state of the project (post-P4). The original
> handoff described a 5-phase plan running on a static `http.server`; the project
> has since moved to a Flask server with a library-write endpoint and an offline
> audio-feature pipeline. All five original phases are complete — see below.

---

## Current File Structure
```
project/
├── kpop-mp3-player.html   # Main single-file app (UI + recommendation + Spotify)
├── server.py              # Local Flask server: serves the app + POST /library/add
├── buildlib.py            # One-time: build songs.json from Last.fm (tags)
├── build_features.py      # One-time/resumable: enrich songs.json with audio features
├── songs.json             # Song library (~1264 K-pop tracks; 1107 with features)
├── features_cache.json    # build_features.py resume cache (gitignored)
├── songs.json.bak         # auto-backup written by server.py on each add (gitignored)
├── P3_CONTINUE.md         # P3/P4 build + run notes
├── RECOMMENDATION_FIX.md  # recommendation-engine fix notes
└── KPOP_PLAYER_PROMPT.md  # This file
```

---

## How to Run
```bash
# 1. (first time) install deps  — NOTE: use python3 -m pip (python3 ≠ pip3 here)
python3 -m pip install flask requests

# 2. Free port 5000 first: macOS AirPlay Receiver squats on it.
#    System Settings → General → AirDrop & Handoff → turn OFF "AirPlay Receiver".

# 3. Start the local server (serves the app AND the /library/add write endpoint)
python3 server.py            # → http://127.0.0.1:5000

# 4. Open in a browser (hard-refresh after code changes: Cmd+Shift+R)
open http://127.0.0.1:5000/kpop-mp3-player.html
```
Spotify login (Premium) requires the redirect URI `http://127.0.0.1:5000/kpop-mp3-player.html`
to be registered in the Spotify Developer Dashboard.

### Rebuilding the library / features
```bash
# Add/refresh audio features (resumable; only fetches what's missing). Needs a
# Spotify client secret for the Client-Credentials search step — never committed.
SPOTIFY_CLIENT_SECRET=<secret> python3 build_features.py
```

---

## Architecture Notes
- **Local Flask server (`server.py`)**, bound to `127.0.0.1:5000` only.
  - Serves the single-file app.
  - `POST /library/add` appends a searched-but-missing seed song to `songs.json`
    (whitelisted fields, atomic write + `.bak` backup, dedup by `artist::title`).
  - Quality guard: refuses tag-less songs unless the request carries `force:true`
    (set when the user manually approves via the in-app confirm prompt).
- **Spotify config** (`kpop-mp3-player.html`):
  - Client ID `3b83bb835d39465aaa7e2e857981d7ba`.
  - Redirect URI is computed at runtime: local → `location.origin + "/kpop-mp3-player.html"`,
    GitHub Pages → its own URL, `file://` → the GitHub Pages URL fallback.
  - OAuth 2.0 + PKCE, token in `sessionStorage`; scopes include
    `streaming user-modify-playback-state user-read-playback-state
    playlist-modify-public playlist-modify-private`.
- **Recommendation** is two-tier: audio-feature similarity (ReccoBeats features
  baked into `songs.json` by `build_features.py`) when the seed has features,
  else Last.fm tag overlap, else random.
- **Auto-extend**: searching a song not in the library resolves the best of 5
  Last.fm results (token-similarity + listener tie-break, with a title bonus),
  then offers to add it (auto if it has tags; confirm prompt if tag-less).

---

## Completed Work (all original phases ✅)
- **Phase 1 — Recommendation engine** ✅ tag-based; upgraded with ReccoBeats
  audio-feature similarity (`build_features.py`).
- **Phase 2 — Retro MP3 player UI** ✅ pink iPod-nano body, LCD screen, click
  wheel, toast system, inline SVG icons.
- **Phase 3 — Spotify Web Playback** ✅ PKCE auth, SDK init, Connect button,
  play via `me/player/play`, exact-`spotify_id` lookup with 429 backoff.
- **Phase 4 — Search UX** ✅ "Searching…" state, distinct seed at top, Shuffle,
  no-tags → random fallback.
- **Phase 5 — Export + saved playlists** ✅ Saved Playlists panel (load/rename/
  delete), Export-to-Spotify flow. **See Known Issues — export currently fails.**

---

## Known Issues / Open Items

### 1. Export to Spotify fails ⚠️ — ROOT CAUSE CONFIRMED (2026-06-27)
`exportToSpotify()` creates a private playlist, then adds resolved track URIs.
Console during a failed export showed `POST /v1/users/{id}/playlists → 403` (x5):
the create-playlist call returns **403 insufficient scope**. The
`playlist-modify-*` scopes ARE in the code (`kpop-mp3-player.html:377`), but the
active token was granted *before* they were added, and `spotifyFetch` only
retries on **401**, not 403 — `refreshToken()` keeps the original scopes.

- **Immediate workaround (no code change):** revoke app access at
  spotify.com/account/apps, hard-refresh, reconnect Spotify → the new consent
  includes the playlist scopes.
- **Real fix (planned):** handle **403 insufficient-scope** in `spotifyFetch` by
  forcing a fresh PKCE auth, so users don't have to manually re-consent.

Secondary (not the export blocker): the per-track `findSpotifyUri` resolve loop
hit **429** for songs without a baked `spotify_id` (fuzzy search). Goes away once
`build_features.py` fills in IDs so resolution uses exact lookups.

Other export toasts and their meaning, for reference:
`Export failed: auth error` → `/v1/me` token bad (reconnect);
`No tracks found on Spotify` → URI resolution returned nothing (429 or unmatched).

### 2. Audio-feature coverage is incomplete (ongoing maintenance)
1107/1264 songs have features. Songs added via auto-extend (and ~23 with no
Spotify match) have none until the next `build_features.py` run, so they fall
back to tag-based recommendation. Re-run `build_features.py` periodically to
enrich; it resumes from `features_cache.json` and only fetches what's missing.

---

## Constraints
- No build step (no webpack/vite/npm) — plain HTML + vanilla JS.
- `songs.json` is fetched over HTTP, so the app must run via `server.py` (not `file://`).
- All icons inline SVG; only CDNs are Google Fonts (VT323 + Share Tech Mono) and the Spotify SDK.
- No `alert()` — use the toast system (`showToast` / `showToastConfirm` / `showToastLink`).
- Spotify token lives in `sessionStorage`, never `localStorage`.
- Preserve the retro pink MP3-player aesthetic; no new layout outside the player body.
- Last.fm API key (read-only, in-file): `7f2d0885886279a622e2a0384c807f85`.
