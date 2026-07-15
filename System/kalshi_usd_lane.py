#!/usr/bin/env python3
"""Kalshi US $ betting lane master switch (George dual-lane law).

STGM / paper autopilot is independent and always allowed to run.
This file only stores whether George has **armed** the real-dollar lane.

Default: OFF.
Turning ON does **not** place orders by itself — any future order path must
call ``is_usd_lane_armed()`` and still respect caps / explicit size.
Production only. Never demo.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
LANE_FILE = "kalshi_usd_lane.json"
TRUTH = "KALSHI_USD_LANE_V1"


def _path(state_dir: Optional[Path | str] = None) -> Path:
    root = Path(state_dir) if state_dir else STATE
    if root.name != ".sifta_state":
        root = root / ".sifta_state"
    return root / LANE_FILE


def load_lane(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    p = _path(state_dir)
    if not p.exists():
        return {
            "armed": False,
            "truth_label": TRUTH,
            "note": "default OFF — STGM independent",
        }
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            # Fail closed on malformed truthy values such as "false" or 1.
            # Only the JSON literal true arms real-dollar execution.
            out = dict(raw)
            out["armed"] = raw.get("armed") is True
            out.setdefault("truth_label", TRUTH)
            return out
    except Exception:
        pass
    return {"armed": False, "truth_label": TRUTH}


def is_usd_lane_armed(state_dir: Optional[Path | str] = None) -> bool:
    return load_lane(state_dir).get("armed") is True


def _atomic_write_json(path: Path, row: dict[str, Any]) -> None:
    """Durably replace one state snapshot without exposing partial JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("x", encoding="utf-8") as handle:
            json.dump(row, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        try:
            dir_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            # The same-directory os.replace is still atomic if directory fsync
            # is unavailable on a particular filesystem.
            pass
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def set_usd_lane_armed(
    armed: bool,
    *,
    reason: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Persist arm state. Does not place orders."""
    p = _path(state_dir)
    armed_value = armed is True
    row = {
        "armed": armed_value,
        "ts": time.time(),
        "reason": str(reason or "")[:200],
        "truth_label": TRUTH,
        "note": (
            "US $ betting lane ARMED — still requires order path + caps; not auto-fire"
            if armed_value
            else "US $ betting lane OFF — read-only cash mirror only; STGM unaffected"
        ),
        "env": "prod",
    }
    _atomic_write_json(p, row)
    try:
        log = p.parent / "kalshi_usd_lane.jsonl"
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    except Exception:
        pass
    return row


def status_line(state_dir: Optional[Path | str] = None) -> str:
    if is_usd_lane_armed(state_dir):
        return "US $ LANE ON"
    return "US $ LANE OFF"


__all__ = [
    "is_usd_lane_armed",
    "set_usd_lane_armed",
    "load_lane",
    "status_line",
    "TRUTH",
]
