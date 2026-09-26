"""Turn the owner's Spotify playlists into library records.

Everything here is pure -- no network, no files -- so the parts that decide
what enters the library can be tested against made-up payloads. The OAuth flow
and the HTTP calls live in ``scripts/import_playlists.py``.

Two design decisions carry the rest.

**A track's identity is its join key.** ``song_key`` is what ground-truth
construction, the benchmark and the annotation pool all resolve tracks by, and
a key held by two tracks resolves to the *later* one. Appending a remix of
"FAKE LOVE" to a library that already has "FAKE LOVE" would therefore take the
original's place in every label lookup and quietly change what an old seed
means. So an incoming track whose key is already taken is not added; it is
counted and reported, with its title, so the loss of a version is visible
rather than silent.

**Where a track came from is recorded, not implied.** Last.fm's tag pages built
the original library and the playlists are one person's taste; the two are not
samples of the same thing. ``source`` says which, and the analysis reports
splits on it. A record with no ``source`` is a Last.fm one, so the existing
library and the committed sample need no rewriting.
"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import urlencode

from kpoprec.normalize import key_of, song_key

SOURCE_LASTFM = "lastfm_tag"
SOURCE_PLAYLIST = "spotify_playlist"

# Scopes that let an app read the user's own and collaborative playlists.
SCOPES = "playlist-read-private playlist-read-collaborative"
AUTHORIZE_URL = "https://accounts.spotify.com/authorize"

# A release year outside this is a parse error, not a release. The same window
# enrich_metadata applies to MusicBrainz.
YEAR_RANGE = (1980, 2027)


def source_of(song: dict) -> str:
    """How a track entered the library. Absent means the Last.fm tag pull."""
    return song.get("source") or SOURCE_LASTFM


# ── Playlist ids ────────────────────────────────────────────────────────────

_ID = re.compile(r"^[A-Za-z0-9]{22}$")
_URL = re.compile(r"(?:open\.spotify\.com/(?:[a-z-]+/)?playlist/|spotify:playlist:)([A-Za-z0-9]{22})")


def parse_playlist_id(text: str) -> str:
    """A bare id, a share link (query string and all) or a ``spotify:`` URI."""
    text = text.strip()
    if _ID.match(text):
        return text
    m = _URL.search(text)
    if not m:
        raise ValueError(f"not a Spotify playlist id or link: {text!r}")
    return m.group(1)


# ── OAuth 2.0 authorization code with PKCE (RFC 7636) ───────────────────────
# No client secret: the flow proves possession of a one-off verifier instead,
# so the only credential needed is the app's public client id.

def pkce_pair() -> tuple[str, str]:
    """A fresh ``(verifier, challenge)``; the challenge is S256 of the verifier."""
    verifier = secrets.token_urlsafe(64)
    return verifier, pkce_challenge(verifier)


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def authorize_url(client_id: str, redirect_uri: str, challenge: str, state: str) -> str:
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "state": state,
    })


# ── Records ─────────────────────────────────────────────────────────────────

def release_year(album: dict | None) -> int | None:
    """Year of the album's release date (``"2022-08-01"``, ``"2022-08"``, ``"2022"``).

    This is the release of the *album this copy sits on*, so a reissue or a
    compilation reads later than the song's first release. MusicBrainz's year is
    the earliest release, and the two are kept apart (``year_spotify`` against
    ``year``) rather than one overwriting the other.
    """
    date = str((album or {}).get("release_date") or "")
    year = date[:4]
    if not year.isdigit():
        return None
    lo, hi = YEAR_RANGE
    return int(year) if lo <= int(year) <= hi else None


def track_record(entry: dict) -> tuple[dict | None, str | None]:
    """One playlist entry -> ``(library record, None)`` or ``(None, reason)``.

    The reasons are the ways an entry is not a track this project can use: a
    file from the owner's own disk has no catalogue id, a podcast episode is not
    music, and an unavailable track comes back as an empty item.
    """
    # The endpoint renamed `track` to `item`; accept either.
    item = entry.get("item", entry.get("track"))
    if not isinstance(item, dict):
        return None, "unavailable"
    if entry.get("is_local") or item.get("is_local"):
        return None, "local file"
    if item.get("type", "track") != "track":
        return None, "not a track"
    sid = item.get("id")
    artists = [a.get("name", "").strip() for a in item.get("artists") or [] if a.get("name")]
    title = str(item.get("name") or "").strip()
    if not sid or not title or not artists:
        return None, "incomplete"

    dur = round((item.get("duration_ms") or 0) / 1000)
    record = {
        "title": title,
        # The primary credit only. Last.fm files a track under one artist, and
        # the same-artist logic everywhere in the project keys on that name.
        "artist": artists[0],
        "tags": [],
        "all_tags": [],
        "dur": dur,
        "durStr": f"{dur // 60}:{dur % 60:02d}",
        "spotify_id": sid,
        "source": SOURCE_PLAYLIST,
    }
    year = release_year(item.get("album"))
    if year is not None:
        record["year_spotify"] = year
    return record, None


# ── Merge ───────────────────────────────────────────────────────────────────

# Spotify writes a version as " - Sped Up" or " - Remastered 2011"; Last.fm, and
# so the library, writes "(Sped Up)". normalize.norm drops the bracketed form as
# noise and leaves the dashed one, so the same version would get two different
# join keys -- and enter the library as a new track that is, to the ear, a copy
# of one already there. Only a dashed tail that names a version is stripped: a
# title that merely contains a dash is left alone.
_VERSION_WORDS = (
    r"remaster(?:ed)?|remix|mix|ver(?:sion|\.)?|live|inst(?:rumental|\.)?|sped up|"
    r"slowed|edit|acoustic|mono|stereo|demo|radio|extended|reverb|nightcore|speed up"
)
_DASH_VERSION = re.compile(rf"\s+[-\u2013\u2014]\s+(?=[^-\u2013\u2014]*\b(?:{_VERSION_WORDS})\b)[^-\u2013\u2014]*$", re.I)


def strip_version_suffix(title: str) -> str:
    """``"Hype Boy - Sped Up"`` -> ``"Hype Boy"``; ``"Spring - Day"`` unchanged."""
    return _DASH_VERSION.sub("", title)


def join_keys(record: dict) -> set[str]:
    """Every key a track is known by: its ``song_key``, and that key with a
    dashed version suffix removed. Two tracks are the same song if either of
    theirs meets. Both are needed because a library title can itself carry a
    dashed suffix (Last.fm sometimes writes ``HELICOPTER - English Version``):
    comparing only stripped keys would miss the exact same track."""
    return {song_key(record), key_of(record["artist"], strip_version_suffix(record["title"]))}


def same_title(a: str, b: str) -> bool:
    """Whether two titles differ only in case, spacing or the shape of a quote.

    Those are spellings of one title. Anything more -- "(feat. X)", "(Remix)",
    "- Sped Up" -- is a different version of the song, and is what the merge
    reports as a variant.
    """
    def fold(t: str) -> str:
        t = unicodedata.normalize("NFKC", t).casefold()
        t = t.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
        return " ".join(t.split())
    return fold(a) == fold(b)


IN_LIBRARY_ID = "already in the library (same Spotify id)"
IN_LIBRARY_KEY = "already in the library (same track key)"
REPEATED = "repeated within the playlists"


@dataclass
class MergeReport:
    """What happened to every incoming entry. Nothing is dropped unaccounted."""

    entries: int = 0
    skipped: Counter = field(default_factory=Counter)      # not usable at all
    duplicates: Counter = field(default_factory=Counter)   # usable, already held
    added: int = 0
    # Incoming tracks whose key an existing track already holds but whose title
    # is more than a respelling of it -- a remix, a re-recording, a "feat."
    # credit. Left out of the library, and listed here so the loss is visible.
    variants: list[tuple[str, str, str]] = field(default_factory=list)


def merge_playlist_tracks(
    songs: list[dict], entries: list[dict]
) -> tuple[list[dict], MergeReport]:
    """Append the new tracks among ``entries`` to ``songs``; return them and a report.

    ``songs`` is not modified. Tracks are compared by Spotify id first (an exact
    match) and then by join key (the project's notion of the same song); the
    first occurrence wins, in library order and then in playlist order.
    """
    report = MergeReport(entries=len(entries))
    lib_ids = {s["spotify_id"] for s in songs if s.get("spotify_id")}
    lib_keys = {k: s for s in songs for k in join_keys(s)}
    new: list[dict] = []
    new_ids: set[str] = set()
    new_keys: set[str] = set()

    for entry in entries:
        record, reason = track_record(entry)
        if record is None:
            report.skipped[reason] += 1
            continue
        keys = join_keys(record)
        # Overlap with the existing library and repetition inside the playlists
        # are different facts: the first says how far the two ways of sampling
        # coincide, the second only that a song sits in both playlists.
        if record["spotify_id"] in lib_ids:
            report.duplicates[IN_LIBRARY_ID] += 1
        elif keys & lib_keys.keys():
            report.duplicates[IN_LIBRARY_KEY] += 1
            held = lib_keys[next(iter(keys & lib_keys.keys()))]
            if not same_title(held["title"], record["title"]):
                report.variants.append((record["artist"], record["title"], held["title"]))
        elif record["spotify_id"] in new_ids or keys & new_keys:
            report.duplicates[REPEATED] += 1
        else:
            new_ids.add(record["spotify_id"])
            new_keys |= keys
            new.append(record)

    report.added = len(new)
    return new, report
