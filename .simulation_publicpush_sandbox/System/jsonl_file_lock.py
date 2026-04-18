#!/usr/bin/env python3
"""
jsonl_file_lock.py — POSIX advisory locks for shared JSONL substrates
══════════════════════════════════════════════════════════════════════

When Cursor, Antigravity, and CLI scripts touch the same append-only files,
use flock(2) so writes serialize and whole-file reads do not interleave with
a concurrent rewrite.

Windows: fcntl is unavailable — falls back to unlocked I/O (same as before).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict

try:
    import fcntl

    _HAVE_FLOCK = True
except ImportError:
    fcntl = None  # type: ignore[assignment]
    _HAVE_FLOCK = False


def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
    """Append one line (caller supplies trailing \\n if needed). Exclusive lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not _HAVE_FLOCK:
        with open(path, "a", encoding=encoding) as f:
            f.write(line)
        return
    with open(path, "a", encoding=encoding) as f:
        fd = f.fileno()
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)


def read_text_locked(
    path: Path, *, encoding: str = "utf-8", errors: str = "replace"
) -> str:
    """Read entire file under shared lock (blocks writers for the read duration)."""
    if not path.exists():
        return ""
    if not _HAVE_FLOCK:
        return path.read_text(encoding=encoding, errors=errors)
    with open(path, "r", encoding=encoding, errors=errors) as f:
        fd = f.fileno()
        fcntl.flock(fd, fcntl.LOCK_SH)
        try:
            return f.read()
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)


def rewrite_text_locked(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """
    Replace entire file contents under exclusive lock (read-modify-write paths).
    Uses r+ / a+ truncate — safe against concurrent append only if all writers
    use these helpers for the same path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if not _HAVE_FLOCK:
        path.write_text(content, encoding=encoding)
        return
    with open(path, "a+", encoding=encoding) as f:
        fd = f.fileno()
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            f.seek(0)
            f.truncate(0)
            f.write(content)
            f.flush()
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)


def read_write_json_locked(
    path: Path,
    updater: Callable[[Dict[str, Any]], Dict[str, Any]],
    *,
    encoding: str = "utf-8",
) -> Dict[str, Any]:
    """
    Single exclusive lock: load JSON object (or {}), apply updater, write back.
    Avoids read-modify-write races between Cursor / Antigravity / CLI.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if not _HAVE_FLOCK:
        data: Dict[str, Any] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding=encoding))
            except Exception:
                data = {}
        if not isinstance(data, dict):
            data = {}
        new_data = updater(dict(data))
        path.write_text(
            json.dumps(new_data, indent=2, ensure_ascii=False) + "\n",
            encoding=encoding,
        )
        return new_data
    with open(path, "a+", encoding=encoding) as f:
        fd = f.fileno()
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            f.seek(0)
            raw = f.read()
            data = {}
            if raw.strip():
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        data = parsed
                except Exception:
                    data = {}
            new_data = updater(dict(data))
            f.seek(0)
            f.truncate(0)
            f.write(json.dumps(new_data, indent=2, ensure_ascii=False))
            f.write("\n")
            f.flush()
            return new_data
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
