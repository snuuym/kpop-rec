"""What enters the library from a playlist decides every downstream number, and
none of it can be exercised against the real API without credentials. So the
decisions are pinned here against made-up payloads: who counts as a duplicate,
what is refused, that the OAuth pieces follow the RFC, and that the browser
callback and paging behave."""

import importlib.util
import socket
import threading
import urllib.request
from urllib.parse import parse_qs, urlparse

import pytest

from kpoprec import config, db, playlist
from kpoprec.normalize import song_key

from test_recommend import song

ROOT = config.ROOT


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def entry(title, artist="NewJeans", sid=None, *, release="2022-08-01", ms=180_000, **over):
    """A playlist entry as the /items endpoint returns it."""
    item = {
        "id": sid or f"{abs(hash((title, artist))) % 10**22:022d}",
        "name": title,
        "type": "track",
        "is_local": False,
        "duration_ms": ms,
        "artists": [{"name": artist}, {"name": "Someone Else"}],
        "album": {"release_date": release},
    }
    item.update(over)
    return {"added_at": "2025-01-01T00:00:00Z", "is_local": False, "item": item}


# ── Playlist ids ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "ABCDEFGHIJKLMNOPQRSTUV",
    "https://open.spotify.com/playlist/ABCDEFGHIJKLMNOPQRSTUV?si=0123456789abcdef",
    "open.spotify.com/playlist/ABCDEFGHIJKLMNOPQRSTUV",
    "https://open.spotify.com/intl-ko/playlist/ABCDEFGHIJKLMNOPQRSTUV",
    "spotify:playlist:ABCDEFGHIJKLMNOPQRSTUV",
    "  ABCDEFGHIJKLMNOPQRSTUV\n",
])
def test_playlist_id_from_any_way_of_writing_it(text):
    assert playlist.parse_playlist_id(text) == "ABCDEFGHIJKLMNOPQRSTUV"


@pytest.mark.parametrize("text", ["", "not an id", "https://open.spotify.com/track/ABCDEFGHIJKLMNOPQRSTUV"])
def test_something_that_is_not_a_playlist_is_refused(text):
    with pytest.raises(ValueError):
        playlist.parse_playlist_id(text)


# ── OAuth pieces ────────────────────────────────────────────────────────────

def test_pkce_challenge_matches_the_rfc_7636_example():
    """The RFC's own worked example. A wrong encoding here would fail only at
    Spotify's end, as an unexplained 400 after the user has already approved."""
    assert playlist.pkce_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == \
        "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_a_fresh_verifier_is_long_enough_and_unrepeated():
    (v1, c1), (v2, c2) = playlist.pkce_pair(), playlist.pkce_pair()
    assert 43 <= len(v1) <= 128 and v1 != v2 and c1 != c2
    assert playlist.pkce_challenge(v1) == c1


def test_the_authorize_url_asks_for_playlist_read_access_and_nothing_else():
    url = playlist.authorize_url("cid", "http://127.0.0.1:8080/kpop-mp3-player.html", "chal", "st")
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    assert q["response_type"] == "code" and q["code_challenge_method"] == "S256"
    assert q["redirect_uri"] == "http://127.0.0.1:8080/kpop-mp3-player.html"
    assert set(q["scope"].split()) == {"playlist-read-private", "playlist-read-collaborative"}
    assert (q["client_id"], q["code_challenge"], q["state"]) == ("cid", "chal", "st")


# ── One entry -> one record ─────────────────────────────────────────────────

def test_a_track_becomes_a_record_with_its_source_and_primary_artist():
    rec, why = playlist.track_record(entry("Hype Boy", ms=179_600))
    assert why is None
    assert rec["artist"] == "NewJeans"          # the first credit, not "Someone Else"
    assert rec["source"] == "spotify_playlist"
    assert (rec["dur"], rec["durStr"]) == (180, "3:00")
    assert rec["year_spotify"] == 2022
    assert rec["tags"] == [] and rec["all_tags"] == []   # the pipeline stages fill these
    assert "listeners" not in rec and "features" not in rec and "year" not in rec


def test_every_record_field_is_one_the_schema_knows():
    """An import that adds a field the database rejects would only be found out
    on the next `make db`."""
    rec, _ = playlist.track_record(entry("Hype Boy"))
    assert set(rec) <= db.SONG_FIELDS


@pytest.mark.parametrize("bad, reason", [
    (dict(entry("x"), item=None), "unavailable"),
    (dict(entry("x"), is_local=True), "local file"),
    (entry("x", is_local=True), "local file"),
    (entry("x", type="episode"), "not a track"),
    (entry("x", id=None), "incomplete"),
    (entry("", ), "incomplete"),
    (entry("x", artists=[]), "incomplete"),
])
def test_entries_that_are_not_usable_tracks_say_why(bad, reason):
    assert playlist.track_record(bad) == (None, reason)


def test_the_old_field_name_is_still_read():
    """The endpoint renamed `track` to `item`; a snapshot from before, or a
    playlist served by the old shape, must not silently read as empty."""
    e = entry("Ditto")
    old = {"added_at": e["added_at"], "is_local": False, "track": e["item"]}
    assert playlist.track_record(old)[0]["title"] == "Ditto"


@pytest.mark.parametrize("release, year", [
    ("2022-08-01", 2022), ("2022-08", 2022), ("2022", 2022),
    ("", None), (None, None), ("0000", None), ("1970-01-01", None), ("9999", None), ("abcd", None),
])
def test_release_year_from_spotifys_three_date_precisions(release, year):
    assert playlist.release_year({"release_date": release}) == year


def test_a_track_with_no_usable_date_simply_has_no_spotify_year():
    rec, _ = playlist.track_record(entry("x", release=""))
    assert "year_spotify" not in rec


# ── Merging into the library ────────────────────────────────────────────────

def test_a_new_track_is_appended_and_the_library_is_not_touched():
    lib = [song("Old", "IVE")]
    before = [dict(s) for s in lib]
    new, rep = playlist.merge_playlist_tracks(lib, [entry("Hype Boy")])
    assert [n["title"] for n in new] == ["Hype Boy"] and rep.added == 1
    assert lib == before


def test_a_track_already_in_the_library_is_not_added_twice():
    lib = [song("Hype Boy", "NewJeans")]
    new, rep = playlist.merge_playlist_tracks(lib, [entry("Hype Boy")])
    assert new == [] and rep.duplicates[playlist.IN_LIBRARY_KEY] == 1 and rep.variants == []


def test_the_same_spotify_id_is_caught_even_when_the_title_is_spelled_differently():
    lib = [dict(song("Hype Boy", "NewJeans"), spotify_id="A" * 22)]
    new, rep = playlist.merge_playlist_tracks(lib, [entry("HYPE BOY (Korean ver.)", sid="A" * 22)])
    assert new == [] and rep.duplicates[playlist.IN_LIBRARY_ID] == 1


def test_a_remix_that_shares_the_join_key_is_left_out_and_reported():
    """It cannot be added: two tracks holding one key resolve to the later one,
    so the remix would take the original's place in every label lookup and
    change what an old seed means. But it must not vanish silently either."""
    lib = [song("FAKE LOVE", "BTS")]
    remix = entry("FAKE LOVE (Rocking Vibe Mix)", "BTS")
    assert song_key(playlist.track_record(remix)[0]) == song_key(lib[0])
    new, rep = playlist.merge_playlist_tracks(lib, [remix])
    assert new == []
    assert rep.variants == [("BTS", "FAKE LOVE (Rocking Vibe Mix)", "FAKE LOVE")]


@pytest.mark.parametrize("held, incoming", [
    ("Hype Boy", "HYPE BOY"),
    ("THAT'S A NO NO", "THAT\u2019S A NO NO"),      # the curly-quote pair in the real library
    ("Hype  Boy", "hype boy"),
])
def test_a_respelling_of_the_same_title_is_not_a_variant(held, incoming):
    _, rep = playlist.merge_playlist_tracks([song(held, "NewJeans")], [entry(incoming)])
    assert rep.variants == [] and rep.duplicates[playlist.IN_LIBRARY_KEY] == 1


@pytest.mark.parametrize("incoming", [
    "Hype Boy (Sped Up)", "Hype Boy (feat. X)",
    "Hype Boy - English Ver.", "Hype Boy - Sped Up", "Hype Boy - Remastered 2011",
    "Hype Boy \u2013 Instrumental",
])
def test_a_different_version_is_a_variant(incoming):
    """Spotify spells a version with a dash, Last.fm with brackets. Either way
    it must not enter as a new track that sounds like one already there."""
    new, rep = playlist.merge_playlist_tracks([song("Hype Boy", "NewJeans")], [entry(incoming)])
    assert new == [] and [v[1] for v in rep.variants] == [incoming]


@pytest.mark.parametrize("title", ["Spring - Day", "Ditto - Part 2", "Cool - Down"])
def test_a_dash_that_is_not_a_version_is_left_alone(title):
    """Stripping every dashed tail would merge distinct songs whose titles
    happen to contain one."""
    assert playlist.strip_version_suffix(title) == title
    new, _ = playlist.merge_playlist_tracks([song("Spring", "BTS")], [entry(title, "BTS")])
    assert len(new) == 1


def test_a_library_title_that_itself_carries_a_dashed_suffix_matches_itself():
    """The real library has `HELICOPTER - English Version`. Offering that very
    track back must be a duplicate: comparing only suffix-stripped keys would
    turn the library's own copy into a stranger."""
    lib = [song("HELICOPTER - English Version", "CLC")]
    new, rep = playlist.merge_playlist_tracks(lib, [entry("HELICOPTER - English Version", "CLC")])
    assert new == [] and rep.variants == []
    # and the plain title is recognised as the same song, from the other side
    new, rep = playlist.merge_playlist_tracks(lib, [entry("HELICOPTER", "CLC")])
    assert new == [] and len(rep.variants) == 1


def test_a_version_of_a_song_that_is_itself_new_is_still_dropped_as_repeated():
    new, rep = playlist.merge_playlist_tracks([], [entry("OMG"), entry("OMG - Sped Up")])
    assert [n["title"] for n in new] == ["OMG"] and rep.duplicates[playlist.REPEATED] == 1


def test_a_song_in_both_playlists_is_added_once_and_counted_as_repeated():
    e = entry("Ditto")
    new, rep = playlist.merge_playlist_tracks([], [e, e, entry("OMG")])
    assert [n["title"] for n in new] == ["Ditto", "OMG"]
    assert rep.duplicates[playlist.REPEATED] == 1


def test_overlap_with_the_library_is_not_confused_with_repetition():
    """The first says how far the two ways of sampling coincide; the second only
    that a song sits in two playlists. They answer different questions."""
    lib = [song("Ditto", "NewJeans")]
    _, rep = playlist.merge_playlist_tracks(lib, [entry("Ditto"), entry("OMG"), entry("OMG")])
    assert rep.duplicates == {playlist.IN_LIBRARY_KEY: 1, playlist.REPEATED: 1}


def test_every_entry_is_accounted_for():
    entries = [entry("A"), entry("A"), entry("B"), dict(entry("x"), item=None), entry("y", type="episode")]
    lib = [song("B", "NewJeans")]
    new, rep = playlist.merge_playlist_tracks(lib, entries)
    assert rep.entries == 5
    assert rep.added + sum(rep.skipped.values()) + sum(rep.duplicates.values()) == rep.entries


def test_merging_the_same_snapshot_twice_adds_nothing_the_second_time():
    entries = [entry("A"), entry("B")]
    first, _ = playlist.merge_playlist_tracks([], entries)
    second, rep = playlist.merge_playlist_tracks(first, entries)
    assert second == [] and rep.duplicates[playlist.IN_LIBRARY_ID] == 2


def test_the_source_of_an_old_record_is_the_lastfm_pull():
    assert playlist.source_of(song("Old")) == "lastfm_tag"
    assert playlist.source_of({"source": "spotify_playlist"}) == "spotify_playlist"


# ── build_features keeps what the import supplied ───────────────────────────

feat = load_script("build_features")
F = {"danceability": 0.5}


def cache_with(**kw):
    return {"spotify_id": {}, "recco_uuid": {}, "features": {}, **kw}


def test_a_supplied_id_is_seeded_so_it_is_not_searched_for():
    rec = dict(playlist.track_record(entry("Ditto"))[0])
    cache = cache_with()
    assert feat.seed_supplied_ids([rec], cache) == 1
    assert cache["spotify_id"][feat.cache_key(rec)] == rec["spotify_id"]


def test_seeding_never_overrides_what_the_cache_already_holds():
    rec = dict(song("Ditto", "NewJeans"), spotify_id="B" * 22)
    cache = cache_with(spotify_id={feat.cache_key(rec): "C" * 22})
    assert feat.seed_supplied_ids([rec], cache) == 0
    assert cache["spotify_id"][feat.cache_key(rec)] == "C" * 22


def test_a_playlist_id_survives_when_reccobeats_has_no_features_for_it():
    """The merge has always stripped the id along with the features. For a
    search result that is right; for an id Spotify itself supplied it throws
    away the one thing the demo needs to play the track."""
    rec = dict(playlist.track_record(entry("Ditto"))[0])
    cache = cache_with()
    feat.seed_supplied_ids([rec], cache)
    assert feat.merge_features([rec], cache) == 0
    assert rec["spotify_id"]


def test_a_lastfm_track_with_no_features_still_loses_its_searched_id():
    """Unchanged behaviour: it keeps the existing library's data as it was."""
    rec = dict(song("Old", "IVE"), spotify_id="D" * 22)
    assert feat.merge_features([rec], cache_with(spotify_id={feat.cache_key(rec): "D" * 22})) == 0
    assert "spotify_id" not in rec


def test_features_are_attached_when_reccobeats_has_them():
    rec = dict(playlist.track_record(entry("Ditto"))[0])
    cache = cache_with(recco_uuid={rec["spotify_id"]: "u"}, features={"u": F})
    feat.seed_supplied_ids([rec], cache)
    assert feat.merge_features([rec], cache) == 1
    assert rec["features"] == F and rec["spotify_id"]


# ── The browser callback ────────────────────────────────────────────────────

imp = load_script("import_playlists")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def browser(uri, query, delay=0.2):
    """Play the browser: land on the redirect URI a moment after it is listening."""
    def go():
        import time
        time.sleep(delay)
        try:
            urllib.request.urlopen(f"{uri}?{query}", timeout=5).read()
        except Exception:
            pass
    threading.Thread(target=go, daemon=True).start()


def test_the_callback_hands_back_the_code():
    uri = f"http://127.0.0.1:{free_port()}/kpop-mp3-player.html"
    browser(uri, "code=abc123&state=S")
    assert imp.wait_for_code(uri, "S", timeout=10) == "abc123"


def test_a_response_with_the_wrong_state_is_refused():
    """The state ties the answer to the request we made. Taking a code from a
    response that does not carry it is how a forged callback gets accepted."""
    uri = f"http://127.0.0.1:{free_port()}/kpop-mp3-player.html"
    browser(uri, "code=abc123&state=FORGED")
    with pytest.raises(SystemExit, match="state"):
        imp.wait_for_code(uri, "S", timeout=10)


def test_the_user_declining_is_reported_as_such():
    uri = f"http://127.0.0.1:{free_port()}/kpop-mp3-player.html"
    browser(uri, "error=access_denied&state=S")
    with pytest.raises(SystemExit, match="access_denied"):
        imp.wait_for_code(uri, "S", timeout=10)


def test_silence_times_out_instead_of_hanging():
    uri = f"http://127.0.0.1:{free_port()}/kpop-mp3-player.html"
    with pytest.raises(SystemExit, match="no answer"):
        imp.wait_for_code(uri, "S", timeout=0.5)


def test_a_request_for_another_path_does_not_end_the_wait():
    """A browser asks for /favicon.ico. That must not be mistaken for the
    redirect and cut the wait short."""
    port = free_port()
    uri = f"http://127.0.0.1:{port}/kpop-mp3-player.html"
    browser(f"http://127.0.0.1:{port}/favicon.ico", "", delay=0.1)
    browser(uri, "code=late&state=S", delay=0.5)
    assert imp.wait_for_code(uri, "S", timeout=10) == "late"


# ── Paging ──────────────────────────────────────────────────────────────────

class Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body, self.text = status, body or {}, str(body)

    def json(self):
        return self._body


def test_every_page_is_followed_and_slimmed(monkeypatch):
    pages = {
        "meta": Resp(200, {"name": "My mix"}),
        1: Resp(200, {"items": [entry("A"), entry("B")], "next": "https://api/next"}),
        2: Resp(200, {"items": [entry("C")], "next": None}),
    }
    calls = []

    def fake_get(url, token, **params):
        calls.append((url, params))
        if url.endswith("/playlists/PID"):
            return pages["meta"]
        return pages[1] if url.endswith("/items") else pages[2]

    monkeypatch.setattr(imp, "get", fake_get)
    got = imp.fetch_playlist("PID", "tok")
    assert got["name"] == "My mix"
    assert [e["item"]["name"] for e in got["entries"]] == ["A", "B", "C"]
    assert calls[1][1] == {"limit": 50, "offset": 0}
    assert calls[2] == ("https://api/next", {})     # `next` carries its own query
    # Only what track_record reads is kept -- not the album art and markets.
    assert set(got["entries"][0]["item"]) == {"id", "name", "type", "is_local", "duration_ms", "artists", "album"}
    assert playlist.track_record(got["entries"][0])[0]["title"] == "A"


def test_a_playlist_that_is_not_the_users_explains_the_403(monkeypatch):
    def fake_get(url, token, **params):
        return Resp(200, {"name": "Theirs"}) if url.endswith("/playlists/PID") else Resp(403)

    monkeypatch.setattr(imp, "get", fake_get)
    with pytest.raises(SystemExit, match="own or collaborate"):
        imp.fetch_playlist("PID", "tok")
