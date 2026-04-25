#!/usr/bin/env python3
"""
System/swarm_camera_target.py — Canonical "active eye" target
═══════════════════════════════════════════════════════════════════════════
Concept: One ledger, one schema, one truth for which physical camera Alice
is currently looking through.

Author:  C47H — surgery 2026-04-23, diagnosed by doctor codex IDE
Status:  Active organ (canonical contract)

WHY THIS EXISTS
───────────────
Before this surgery, three independent organs wrote `.sifta_state/
active_saccade_target.txt` in three different shapes (integer index,
camera name string, sometimes both), and three independent readers
parsed it three different ways:

  - `System/swarm_oculomotor_saccades.py`        wrote a NAME string
  - `System/swarm_multisensory_colliculus.py`    wrote an INTEGER index
  - `System/swarm_iris.py._get_saccade_target`   only accepted INTEGER
  - `Applications/sifta_what_alice_sees_widget`  did substring `findText`

The substring matcher hit "1" inside the Logitech entry
`USB Camera VID:1133 PID:2081`, which is why the Logitech LED stayed on
while iris thought Alice was on camera-index 1 (MacBook Pro Camera).

CANONICAL SCHEMA
────────────────
File:  `.sifta_state/active_saccade_target.json`

    {
        "name":       "MacBook Pro Camera",   # human / Qt description
        "index":      1,                      # AVFoundation / cv2 index
        "unique_id":  "0x1410000005ac8600",  # QCameraDevice.id() if known
        "ts":         1776921333.123,         # unix
        "writer":     "swarm_oculomotor_saccades",
        "priority":   20,                     # higher active lease wins
        "lease_until":1776921335.123          # optional unix expiry
    }

RESOLUTION ORDER (readers MUST follow)
──────────────────────────────────────
    1. unique_id  — exact match against live QMediaDevices ids
    2. name       — exact match (case-sensitive, never substring)
    3. index      — last-resort tiebreaker

BACK-COMPAT
───────────
On read, if `.json` is absent but the legacy `.txt` exists, this module
parses the .txt (bare integer OR bare name) and atomically rewrites it
as `.json`. The .txt is then kept as a one-line index mirror so any
stragglers we missed still see *something* valid.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STATE = _REPO / ".sifta_state"
TARGET_JSON: Path = _STATE / "active_saccade_target.json"
TARGET_TXT_LEGACY: Path = _STATE / "active_saccade_target.txt"


# Current macOS/AVFoundation map observed on Alice's M5 rig during the
# 2026-04-23 camera split-brain surgery. These are fallbacks only; live Qt
# device ids/names still win when available.
_INDEX_TO_NAME = {
    0: "USB Camera VID:1133 PID:2081",
    1: "MacBook Pro Camera",
    2: "OBS Virtual Camera",
    3: "iPhone Camera",
    4: "Ioan's iPhone Camera",
    5: "MacBook Pro Desk View Camera",
    6: "iPhone Desk View Camera",
}

_NAME_TO_INDEX = {
    "usb camera vid:1133 pid:2081": 0,
    "logitech": 0,
    "macbook pro camera": 1,
    "facetime hd camera": 1,
    "built-in camera": 1,
    "obs virtual camera": 2,
    "iphone camera": 3,
    "iphone 15 camera": 3,
    "ioan's iphone camera": 4,
    "ioan’s iphone camera": 4,
    "macbook pro desk view camera": 5,
    "iphone desk view camera": 6,
}


def _norm_name(text: str) -> str:
    return " ".join(str(text).replace("’", "'").strip().lower().split())


def name_for_index(index: Optional[int]) -> Optional[str]:
    if index is None:
        return None
    try:
        return _INDEX_TO_NAME.get(int(index))
    except Exception:
        return None


def index_for_name(name: Optional[str]) -> Optional[int]:
    if not name:
        return None
    norm = _norm_name(name)
    if norm in _NAME_TO_INDEX:
        return _NAME_TO_INDEX[norm]
    for key, idx in _NAME_TO_INDEX.items():
        if key in norm or norm in key:
            return idx
    return None


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        text = str(value).strip()
        if text.lstrip("-").isdigit():
            return int(text)
    except Exception:
        return None
    return None


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        out = float(value)
        return out if out == out and out not in (float("inf"), float("-inf")) else None
    except Exception:
        return None


def _coerce_priority(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def parse_legacy_text(raw: str, *, writer: str = "legacy_txt") -> Optional[Dict[str, Any]]:
    """Parse old target-file shapes: bare int, bare name, JSON, or key=value."""
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return _normalize(
                    name=data.get("name"),
                    index=data.get("index"),
                    unique_id=data.get("unique_id"),
                    writer=data.get("writer", writer),
                    ts=data.get("ts"),
                    priority=data.get("priority", 0),
                    lease_until=data.get("lease_until"),
                )
        except Exception:
            pass
    if "=" in text:
        key, value = text.split("=", 1)
        if key.strip().lower() in {"active_saccade_target", "camera", "camera_index", "index"}:
            text = value.strip()
    idx = _coerce_int(text)
    if idx is not None:
        return _normalize(index=idx, writer=f"{writer}_int")
    return _normalize(name=text, writer=f"{writer}_name")


# ── atomic write helper ─────────────────────────────────────────────────
def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def _normalize(
    *,
    name: Optional[str] = None,
    index: Optional[int] = None,
    unique_id: Optional[str] = None,
    writer: str = "unknown",
    ts: Optional[float] = None,
    priority: Any = 0,
    lease_until: Any = None,
) -> Dict[str, Any]:
    idx = _coerce_int(index)
    clean_name = (name or "").strip() or None

    # Name/unique-id are the stable identity. If a UI writes its combobox
    # position as "index", correct it from the camera name whenever we can.
    mapped_from_name = index_for_name(clean_name)
    if mapped_from_name is not None:
        idx = mapped_from_name
    elif clean_name is None:
        clean_name = name_for_index(idx)

    return {
        "name": clean_name,
        "index": idx,
        "unique_id": (unique_id or "").strip() or None,
        "ts": float(ts) if ts is not None else time.time(),
        "writer": writer or "unknown",
        "priority": _coerce_priority(priority),
        "lease_until": _coerce_float(lease_until),
    }


def _active_lease_blocks(
    current: Optional[Dict[str, Any]],
    *,
    writer: str,
    priority: int,
    now: float,
) -> bool:
    """Return True when an active higher-priority owner should keep the eye."""
    if not current:
        return False
    lease_until = _coerce_float(current.get("lease_until"))
    if lease_until is None or lease_until <= now:
        return False
    if str(current.get("writer") or "") == str(writer or ""):
        return False
    current_priority = _coerce_priority(current.get("priority"))
    return current_priority > int(priority)


# ── write API ───────────────────────────────────────────────────────────
def write_target(
    *,
    name: Optional[str] = None,
    index: Optional[int] = None,
    unique_id: Optional[str] = None,
    writer: str = "unknown",
    priority: int = 0,
    lease_s: Optional[float] = None,
    respect_lease: bool = True,
) -> Dict[str, Any]:
    """Write the canonical eye target. At least one of name/index/unique_id
    must be provided. Returns the normalized record actually written."""
    if not (name or index is not None or unique_id):
        raise ValueError(
            "write_target requires at least one of name, index, unique_id"
        )
    now = time.time()
    priority_i = _coerce_priority(priority)
    if respect_lease:
        current = read_target()
        if _active_lease_blocks(current, writer=writer, priority=priority_i, now=now):
            return current  # type: ignore[return-value]
    lease_until = None
    if lease_s is not None:
        try:
            lease_until = now + max(0.0, float(lease_s))
        except Exception:
            lease_until = None
    rec = _normalize(
        name=name,
        index=index,
        unique_id=unique_id,
        writer=writer,
        ts=now,
        priority=priority_i,
        lease_until=lease_until,
    )
    # Order matters: write the legacy .txt mirror FIRST, then the JSON last,
    # so the JSON's mtime is always ≥ the .txt's mtime. Otherwise the
    # "reverse-heal when .txt newer than .json" path in read_target would
    # immediately discard our richer JSON record (unique_id, writer) and
    # replace it with a thinner heal-from-.txt record. (C47H 2026-04-23.)
    if rec["index"] is not None:
        try:
            _atomic_write_text(TARGET_TXT_LEGACY, f"{rec['index']}\n")
        except Exception:
            pass
    _atomic_write_text(TARGET_JSON, json.dumps(rec) + "\n")
    # Belt-and-suspenders: if filesystem timestamp granularity (or a clock
    # quirk) leaves them equal, bump JSON forward by 1ms so reverse-heal
    # cannot accidentally win on a tie.
    try:
        st_json = TARGET_JSON.stat()
        if TARGET_TXT_LEGACY.exists():
            st_txt = TARGET_TXT_LEGACY.stat()
            if st_json.st_mtime <= st_txt.st_mtime:
                os.utime(TARGET_JSON, (st_json.st_atime, st_txt.st_mtime + 0.001))
    except Exception:
        pass
    return rec


# ── read API ────────────────────────────────────────────────────────────
def _heal_legacy_into_json() -> Optional[Dict[str, Any]]:
    """If only the legacy .txt exists, parse it once and rewrite as .json."""
    if not TARGET_TXT_LEGACY.exists():
        return None
    try:
        raw = TARGET_TXT_LEGACY.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    if not raw:
        return None
    rec = parse_legacy_text(raw, writer="legacy_txt")
    if not rec:
        return None
    try:
        _atomic_write_text(TARGET_JSON, json.dumps(rec) + "\n")
    except Exception:
        pass
    return rec


def read_target() -> Optional[Dict[str, Any]]:
    """Return the canonical eye target as a dict, or None if no target set."""
    # During migration, older organs can still write only the .txt mirror. If
    # that happens after JSON exists, trust the newer mtime and heal forward.
    try:
        if TARGET_TXT_LEGACY.exists() and (
            not TARGET_JSON.exists()
            or TARGET_TXT_LEGACY.stat().st_mtime > TARGET_JSON.stat().st_mtime
        ):
            rec = _heal_legacy_into_json()
            if rec:
                return rec
    except Exception:
        pass
    if TARGET_JSON.exists():
        try:
            data = json.loads(TARGET_JSON.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return _normalize(
                    name=data.get("name"),
                    index=data.get("index"),
                    unique_id=data.get("unique_id"),
                    writer=data.get("writer", "unknown"),
                    ts=data.get("ts"),
                    priority=data.get("priority", 0),
                    lease_until=data.get("lease_until"),
                )
        except Exception:
            pass
    return _heal_legacy_into_json()


# ── resolution helpers ──────────────────────────────────────────────────
def resolve_index(target: Optional[Dict[str, Any]] = None) -> int:
    """Return the integer camera index implied by the current target,
    or -1 if no target is set / nothing in the target maps to an index.

    Use this from organs that index by integer (cv2 VideoCapture, iris).
    Resolution order: unique_id → name → index.
    """
    rec = target if target is not None else read_target()
    if not rec:
        return -1
    # 1) unique_id against QMediaDevices (best-effort; never required)
    uid = rec.get("unique_id")
    if uid:
        idx = _index_for_unique_id(uid)
        if idx >= 0:
            return idx
    # 2) name against QMediaDevices
    nm = rec.get("name")
    if nm:
        idx = _index_for_name(nm)
        if idx >= 0:
            return idx
        fallback_idx = index_for_name(nm)
        if fallback_idx is not None:
            return int(fallback_idx)
    # 3) raw index as last resort
    if rec.get("index") is not None:
        return int(rec["index"])
    return -1


def _live_devices() -> List[Tuple[str, str]]:
    """Return [(unique_id, description), ...] in current Qt enumeration order.
    Returns [] if PyQt6 is unavailable or there's no QApplication context."""
    try:
        from PyQt6.QtMultimedia import QMediaDevices  # type: ignore
    except Exception:
        return []
    try:
        return [(d.id().decode() if isinstance(d.id(), bytes) else str(d.id()),
                 d.description()) for d in QMediaDevices.videoInputs()]
    except Exception:
        return []


def _index_for_unique_id(uid: str) -> int:
    for i, (did, _desc) in enumerate(_live_devices()):
        if did == uid:
            return i
    return -1


def _index_for_name(name: str) -> int:
    for i, (_did, desc) in enumerate(_live_devices()):
        if desc == name:
            return i
    return -1


# ── prompt-line helper for Alice ────────────────────────────────────────
def prompt_line() -> str:
    """One-line summary for `alice_body_autopilot.read_prompt_line()`.

    Example:
      "current eye: MacBook Pro Camera (idx 1, writer=swarm_oculomotor_saccades)"
    """
    rec = read_target()
    if not rec:
        return "current eye: (no saccade target set; iris uses auto-discovery)"
    name = rec.get("name") or "(unnamed)"
    idx = rec.get("index")
    writer = rec.get("writer") or "unknown"
    idx_str = f"idx {idx}" if idx is not None else "idx ?"
    return f"current eye: {name} ({idx_str}, writer={writer})"


# ── module self-test ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("[swarm_camera_target] live devices:")
    for i, (uid, desc) in enumerate(_live_devices()):
        print(f"  {i}  {desc}  [uid={uid}]")
    print()
    print("[swarm_camera_target] current target:")
    rec = read_target()
    print(f"  {rec}")
    print(f"  resolved index = {resolve_index(rec)}")
    print(f"  prompt_line    = {prompt_line()!r}")
