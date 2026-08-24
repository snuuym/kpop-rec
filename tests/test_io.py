"""Every pipeline stage is long-running and resumable, so a half-written cache
must never be mistaken for a complete one."""

import json

import pytest

from kpoprec.io import (
    load_songs,
    read_json,
    write_json,
    write_json_with_backup,
)


def test_read_json_missing_file_returns_default(tmp_path):
    assert read_json(tmp_path / "nope.json", default={"a": 1}) == {"a": 1}


def test_read_json_corrupt_file_returns_default(tmp_path, capsys):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    assert read_json(p, default={}) == {}
    assert "corrupt" in capsys.readouterr().out


def test_write_json_roundtrip(tmp_path):
    p = tmp_path / "out.json"
    write_json(p, {"k": "값"})
    assert json.loads(p.read_text(encoding="utf-8")) == {"k": "값"}


def test_write_json_leaves_no_temp_file(tmp_path):
    p = tmp_path / "out.json"
    write_json(p, [1, 2, 3])
    assert list(tmp_path.iterdir()) == [p]


def test_write_json_creates_parent_dirs(tmp_path):
    p = tmp_path / "deep" / "nested" / "out.json"
    write_json(p, {"ok": True})
    assert p.exists()


def test_write_json_with_backup_preserves_previous(tmp_path):
    p = tmp_path / "songs.json"
    write_json(p, [{"v": 1}])
    write_json_with_backup(p, [{"v": 2}])

    assert json.loads(p.read_text(encoding="utf-8")) == [{"v": 2}]
    backup = p.with_suffix(p.suffix + ".bak")
    assert json.loads(backup.read_text(encoding="utf-8")) == [{"v": 1}]


def test_write_json_with_backup_on_first_write(tmp_path):
    """No prior file means no backup, not a crash."""
    p = tmp_path / "songs.json"
    write_json_with_backup(p, [{"v": 1}])
    assert p.exists()
    assert not p.with_suffix(p.suffix + ".bak").exists()


def test_load_songs_missing_file_is_actionable(tmp_path):
    with pytest.raises(SystemExit, match="make library"):
        load_songs(tmp_path / "absent.json")


def test_load_songs_rejects_non_list(tmp_path):
    p = tmp_path / "songs.json"
    p.write_text('{"not": "a list"}', encoding="utf-8")
    with pytest.raises(SystemExit, match="JSON list"):
        load_songs(p)


def test_load_songs_reads_a_list(tmp_path):
    p = tmp_path / "songs.json"
    write_json(p, [{"title": "t", "artist": "a"}])
    assert load_songs(p) == [{"title": "t", "artist": "a"}]
