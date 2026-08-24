"""Title/artist normalization used to join records across three APIs.

Last.fm, MusicBrainz and Spotify each spell the same track differently
("Hype Boy", "Hype Boy (feat. X)", "Hype Boy - Remastered"). Ground-truth
construction intersects Last.fm's similar-track list with the local library, so
a weak join directly deflates the measured positive-sample count. Every module
that builds a join key must use these functions, or the intersection silently
under-counts.
"""

from __future__ import annotations

import re
import unicodedata

_FEAT_PAREN = re.compile(r"\((feat|ft|with)\.?[^)]*\)")
_BRACKETED = re.compile(r"[\[\(].*?[\]\)]")
_FEAT_TRAIL = re.compile(r"\b(feat|ft)\.?\s.*$")
_PUNCT = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")


def norm(s: str) -> str:
    """Aggressively normalize a title or artist for join purposes.

    Lowercases, folds full-width characters, and strips featured-artist
    credits, bracketed suffixes and punctuation.
    """
    s = unicodedata.normalize("NFKC", str(s)).lower()
    s = _FEAT_PAREN.sub(" ", s)
    s = _BRACKETED.sub(" ", s)
    s = _FEAT_TRAIL.sub(" ", s)
    s = _PUNCT.sub(" ", s)
    return _WS.sub(" ", s).strip()


def key_of(artist: str, title: str) -> str:
    """Canonical ``"artist::title"`` join key."""
    return f"{norm(artist)}::{norm(title)}"


def song_key(song: dict) -> str:
    """``key_of`` for a song record."""
    return key_of(song.get("artist", ""), song.get("title", ""))


def normalize_tag(tag: str) -> str:
    """Lowercase, collapse whitespace, and trim edge punctuation from a tag."""
    t = _WS.sub(" ", str(tag).lower().strip())
    return t.strip(" -_/,.")


_MB_FEAT = re.compile(r"\((feat|ft)\.?[^)]*\)", re.I)
_MB_BRACKET = re.compile(r"\[[^\]]*\]")
_MB_SUFFIX = re.compile(
    r"\s*-\s*(remaster|remastered|live|inst\.?|instrumental).*$", re.I
)


def clean_for_search(s: str) -> str:
    """Lighter cleanup for outbound API queries.

    Unlike :func:`norm`, this preserves case and punctuation — MusicBrainz and
    Spotify match better on a human-readable string. It only removes the
    suffixes that reliably prevent a match.
    """
    s = _MB_FEAT.sub("", s)
    s = _MB_BRACKET.sub("", s)
    s = _MB_SUFFIX.sub("", s)
    return _WS.sub(" ", s).strip()
