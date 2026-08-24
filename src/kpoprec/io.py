"""Crash-safe JSON reads and writes.

Every pipeline stage is long-running (minutes to tens of minutes against rate
-limited APIs) and resumable. That makes two things non-negotiable:

* a partially written cache must never be mistaken for a complete one, so all
  writes go through a temp file and an atomic ``rename``;
* the library file is backed up before each merge, because an interrupted
  write there costs hours of re-fetching.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any = None) -> Any:
    """Load JSON, returning ``default`` when the file is absent or corrupt."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"[warn] {path.name} is corrupt — starting over")
        return default


def write_json(path: Path, data: Any, indent: int | None = None) -> None:
    """Write JSON atomically: temp file in the same directory, then rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8"
    )
    tmp.replace(path)


def write_json_with_backup(path: Path, data: Any, indent: int = 2) -> None:
    """Back up the existing file to ``.bak``, then write atomically."""
    if path.exists():
        path.with_suffix(path.suffix + ".bak").write_text(
            path.read_text(encoding="utf-8"), encoding="utf-8"
        )
    write_json(path, data, indent=indent)


def load_songs(path: Path) -> list[dict]:
    """Load the song library, failing loudly on a missing or malformed file."""
    songs = read_json(path)
    if songs is None:
        raise SystemExit(
            f"[FATAL] {path} not found.\n"
            f"        Build it with `make library`, or point --songs at "
            f"data/songs.sample.json to run against the bundled sample."
        )
    if not isinstance(songs, list):
        raise SystemExit(f"[FATAL] {path} must contain a JSON list at the top level.")
    return songs
