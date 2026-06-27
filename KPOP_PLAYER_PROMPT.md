# K-Pop Retro MP3 Player — Project Handoff for Claude Code

## Project Overview
A personal K-pop music recommendation web app styled as a retro pink MP3 player (iPod nano aesthetic). Built for a single user with Spotify Premium. The goal is a self-contained HTML/JS/Python project that recommends K-pop songs by sub-genre and plays them via Spotify.

---

## Current File Structure
```
project/
├── kpop-mp3-player.html   # Main app (Phase 2 + Phase 1 logic complete)
├── build_library.py       # One-time script to generate songs.json
├── songs.json             # Generated song library (~500–800 K-pop tracks)
└── KPOP_PLAYER_PROMPT.md  # This file
```

---

## Completed Work

### Phase 2 — Retro MP3 Player UI ✅
- Pink rounded-body player (iPod nano style, horizontal layout)
- Left side: dark LCD screen showing album art (animated spinning disc), track title, artist, sub-genre tags (multi-label), progress bar with seek, playback status dot, track counter
- Right side: click wheel with:
  - Top = Previous track (⏮)
  - Bottom = Next track (⏭)
  - Left = VOL− (volume down)
  - Right = VOL+ (volume up)
  - Center circle = Play / Pause toggle
- Below wheel: "Save" button (localStorage) + "Spotify" button (Phase 5 stub)
- Search bar + "Generate" button above playlist
- Scrollable mini playlist below search
- Toast notification system for feedback
- All icons are inline SVG (no external icon font dependency)
- Fonts: VT323 (LCD feel) + Share Tech Mono (from Google Fonts)
- All UI text in English

### Phase 1 — Recommendation Engine ✅
- `build_library.py` (v4): pulls tracks from Last.fm root tags `k-pop`, `kpop`, `korean pop` only (guaranteed K-pop origin). Per-track tags fetched via `track.getTopTags` (count ≥ 10). Each track gets up to 5 style sub-genre labels stored in `tags[]` array.
- `songs.json` schema per track:
  ```json
  {
    "title": "Hype Boy",
    "artist": "NewJeans",
    "tags": ["Bubblegum pop", "Dance pop", "Girl group"],
    "all_tags": ["bubblegum pop", "dance pop", "girl group", "r&b", ...],
    "dur": 177,
    "durStr": "2:57",
    "url": "https://www.last.fm/music/NewJeans/_/Hype+Boy"
  }
  ```
- Sub-genre taxonomy (14 style labels, no origin labels like "K-pop"):
  - Vocal/mood: `Ballad`, `R&B`, `Dream pop`, `Bubblegum pop`
  - Rhythm/production: `Dance pop`, `Electronic`, `Hip-hop`, `Rock`, `Indie`
  - Group type: `Girl group`, `Boy group`, `Solo`
  - Context: `OST`, `Dance`
- Recommendation logic in `kpop-mp3-player.html`:
  1. User searches a song → `track.search` on Last.fm → get top result
  2. Fetch that track's tags → `classifySubgenres()` → array of style labels
  3. Score every library track by overlap count between its `tags[]` and search tags
  4. Weighted random shuffle + per-tag cap for variety → 50-track playlist
- Last.fm API key: `7f2d0885886279a622e2a0384c807f85`

---

## Remaining Phases

### Phase 3 — Real Audio Playback (NEXT PRIORITY) 🔧
Connect the player to actual audio using **Spotify Web Playback SDK**.

**Spotify credentials:**
- Client ID: `3b83bb835d39465aaa7e2e857981d7ba`
- Redirect URI: `http://127.0.0.1:8080` (confirmed working in Spotify Developer Dashboard)
- Local server must be started with: `python3 -m http.server 8080 --bind 127.0.0.1`
- Open at: `http://127.0.0.1:8080/kpop-mp3-player.html`

**Auth requirements:**
- OAuth 2.0 with PKCE (no backend, runs entirely in browser)
- Required scopes: `streaming user-read-email user-read-private user-modify-playback-state user-read-playback-state`
- Store access token in `sessionStorage` (NOT localStorage)
- Handle token refresh: if token expires, re-trigger PKCE flow silently

**SDK integration:**
- Load SDK: `<script src="https://sdk.scdn.co/spotify-player.js"></script>`
- Initialize `Spotify.Player` with Client ID, token, and volume
- Player name: `"K-Pop MP3 Player"`
- On `ready` event: store `device_id`, show "Connected" toast
- On `not_ready`: show "Spotify disconnected" toast

**Playback flow:**
1. When playlist is generated, search each track on Spotify:
   `GET https://api.spotify.com/v1/search?q={title}+{artist}&type=track&limit=1`
   Store `uri` (e.g. `spotify:track:xxxxxx`) back onto each playlist track object
2. On play/skip: call `PUT https://api.spotify.com/v1/me/player/play` with `{ uris: [uri], device_id }`
3. Progress bar: poll `player.getCurrentState()` every 500ms, sync `position` and `duration`
4. VOL+ / VOL−: call `player.setVolume(volume / 100)` (SDK takes 0.0–1.0)
5. Pause/resume: use `player.togglePlay()`
6. Previous/next: use `player.previousTrack()` / `player.nextTrack()` or re-call play with new URI

**UI additions (minimal, preserve existing design):**
- Add a "Connect Spotify" button on the LCD screen shown before auth (replaces the "Search a song to start" idle state)
- After auth, hide the connect button and show normal search UI
- On `player_state_changed` event, sync track title/artist displayed on screen with what Spotify is actually playing

**Do NOT modify:**
- Any CSS or visual layout
- The click wheel structure or button positions
- The toast notification system
- The playlist rendering logic

### Phase 4 — Search UX Polish
- Show "Searching..." state on LCD screen during playlist generation
- Display seed track at top of playlist, visually distinct (different color)
- Add "Shuffle" button to re-randomize current playlist without re-searching
- Edge case: if Last.fm returns no tags, fall back to random 50-track sample from library

### Phase 5 — Spotify Export + Saved Playlists
- **Saved Playlists panel**: MENU button on click wheel opens an overlay panel listing localStorage-saved playlists; clicking one reloads it into the player
- **Export to Spotify**:
  1. `POST /v1/users/{user_id}/playlists` → create new playlist named after the search query
  2. Collect all `uri` values from current playlist tracks
  3. `POST /v1/playlists/{playlist_id}/tracks` → add tracks (max 100 per request)
  4. Toast with "Exported! Open in Spotify →" and a link

---

## Technical Constraints
- **No backend server** — everything runs client-side in the browser
- **Must run at `http://127.0.0.1:8080`** via `python3 -m http.server 8080 --bind 127.0.0.1`
- `songs.json` fetched via `fetch('songs.json')` — requires local server (not `file://`)
- All icons must remain inline SVG — no external icon libraries
- No build step (no webpack/vite/npm) — plain HTML + vanilla JS only
- Google Fonts (VT323 + Share Tech Mono) are the only allowed CDN besides Spotify SDK
- Do NOT use `alert()` — use the existing toast system (`showToast()`)
- Spotify token must go in `sessionStorage`, never `localStorage`

## Design Constraints
- Preserve the retro pink MP3 player aesthetic exactly
- Screen area is small — all new text must use existing font/color CSS variables
- No new layout elements outside the existing player body
- Toast is the only notification mechanism

---

## How to Run
```bash
# 1. Generate song library (first time only, ~8 min)
pip install requests
python3 build_library.py

# 2. Start local server (must use 127.0.0.1, not localhost)
python3 -m http.server 8080 --bind 127.0.0.1

# 3. Open in browser
open http://127.0.0.1:8080/kpop-mp3-player.html
```

---

## Instructions for Claude Code
Read all files in this project directory first, then implement **Phase 3: Spotify Web Playback SDK integration** as described above.

The Client ID is already provided above — embed it directly as:
```js
const SPOTIFY_CLIENT_ID = "3b83bb835d39465aaa7e2e857981d7ba";
const SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8080";
```

Work only in `kpop-mp3-player.html`. Do not create new files. Do not modify `build_library.py` or `songs.json`.
