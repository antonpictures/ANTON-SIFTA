#!/usr/bin/env python3
"""
Append one JSON line to repair_log.jsonl under an exclusive POSIX lock (flock).
Reduces interleaved/corrupt lines when server, passive mint, and GUI write concurrently.

On platforms without fcntl, falls back to a plain append (previous behavior).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Union

JsonDict = Mapping[str, Any]


def append_ledger_line(path: Union[str, Path], event: JsonDict) -> None:
    """Serialize *event* as one JSON line and append with flock when available."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(event), ensure_ascii=False) + "\n"
    try:
        import fcntl  # type: ignore
    except ImportError:
        with open(p, "a", encoding="utf-8") as f:
            f.write(line)
        return

    with open(p, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
