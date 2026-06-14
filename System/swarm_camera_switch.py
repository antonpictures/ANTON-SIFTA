#!/usr/bin/env python3
"""
System/swarm_camera_switch.py — Camera switch spinal reflex (canonical eye)

Writes **only** through `swarm_camera_target.write_target` so
`active_saccade_target.json` + `.txt` mirror stay consistent with iris/Qt.

Index map matches `swarm_camera_target._INDEX_TO_NAME` (M5 rig, 2026-04-23):
  0 = USB Camera VID:1133 PID:2081 (Logitech-class)
  1 = MacBook Pro Camera
  2 = OBS Virtual Camera
  3 = iPhone Camera
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# Pattern → index. Order matters: more specific first.
_SWITCH_PATTERNS = [
    # MacBook / built-in / FaceTime
    (re.compile(r"\b(?:macbook|built[- ]?in|facetime|laptop|internal|inside)\b", re.IGNORECASE), 1),
    # Logitech / USB / external / desk
    (re.compile(r"\b(?:logitech|usb|external|desk|webcam)\b", re.IGNORECASE), 0),
    # iPhone / phone / continuity
    (re.compile(r"\b(?:iphone|phone|continuity|mobile)\b", re.IGNORECASE), 3),
    # Generic "other" / "second" / "next" — cycle from current
    (re.compile(r"\b(?:other|second|next|alternate)\b", re.IGNORECASE), None),
]

# Requires DIRECT ADDRESS to Alice:
#   "alice, switch the camera"
#   "switch the camera alice"
#   "can you switch the camera"
#   "please switch the camera"
# Blocks self-talk ("I'll switch...") and praise ("you switched...")
_INTENT_RE = re.compile(
    r"(?:"
    r"\balice\b.{0,40}\b(?:switch|change|use|swap|activate|select)\b.{0,30}\bcamera\b"
    r"|\balice\b.{0,40}\bcamera\b.{0,30}\b(?:switch|change|macbook|logitech|iphone|built[- ]?in|usb)\b"
    r"|\b(?:switch|change|swap)\b.{0,30}\bcamera\b.{0,20}\balice\b"
    r"|\b(?:please|pls|can\s+you|could\s+you)\b.{0,30}\b(?:switch|change|swap)\b.{0,20}\bcamera\b"
    r")",
    re.IGNORECASE,
)

# Block patterns — George talking about Alice switching, NOT commanding her
_SELF_TALK_RE = re.compile(
    r"\b(?:i'?ll|i\s+will|i\s+am\s+going\s+to|i\s+switched|you\s+switched|"
    r"you\s+switch\w*\s+(?:it|the\s+camera)?\s+by\s+your|good\s+job|"
    r"well\s+done|nice\s+job|thank\s+you\s+for\s+switch)\b",
    re.IGNORECASE,
)

# Minimum STT confidence for camera switch to fire (avoids 0.48 conf misfires)
MIN_SWITCH_CONF = 0.55


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


OWNER_CAMERA_LOCK_LEASE_S = max(300.0, _float_env("SIFTA_OWNER_CAMERA_LOCK_LEASE_S", 1800.0))
OWNER_CAMERA_LOCK_PRIORITY = _int_env("SIFTA_OWNER_CAMERA_LOCK_PRIORITY", 95)


def _read_index() -> Optional[int]:
    try:
        from System.swarm_camera_target import read_target

        row = read_target()
        if isinstance(row, dict) and row.get("index") is not None:
            return int(row["index"])
    except Exception:
        pass
    try:
        legacy = (_STATE / "active_saccade_target.txt").read_text(encoding="utf-8").strip()
        return int(legacy.splitlines()[0])
    except Exception:
        return None

def _read_current() -> int:
    return _read_index() or 1


def detect_camera_switch_intent(text: str, stt_conf: float = 1.0) -> Optional[int]:
    """
    Return target camera index if text is a DIRECT camera-switch command to Alice,
    or None if no intent detected or too low confidence.

    Requires explicit address to Alice or imperative phrasing.
    Blocks: self-talk ("I'll switch..."), praise ("you switched...").
    """
    clean = " ".join(str(text or "").split())
    if not clean:
        return None

    # Low confidence guard — below threshold, too risky to fire an effector
    if stt_conf < MIN_SWITCH_CONF:
        return None

    # Block self-talk and praise patterns first
    if _SELF_TALK_RE.search(clean):
        return None

    # Require direct address to Alice or imperative phrasing
    if not _INTENT_RE.search(clean):
        return None

    for pattern, idx in _SWITCH_PATTERNS:
        if pattern.search(text):
            if idx is not None:
                return idx
            cur = _read_index()
            if cur == 1:
                return 0
            if cur == 0:
                return 1
            return 0

    cur = _read_index()
    if cur == 1:
        return 0
    if cur == 0:
        return 1
    return 0


def execute_camera_switch(target_idx: int) -> Dict[str, Any]:
    """Write canonical active eye via swarm_camera_target; return receipt dict."""
    _STATE.mkdir(parents=True, exist_ok=True)
    try:
        from System.swarm_camera_target import name_for_index, write_target

        name = name_for_index(target_idx)
        if not name:
            return {"ok": False, "error": f"unknown camera index {target_idx}", "target": target_idx}
        rec = write_target(
            name=name,
            index=int(target_idx),
            writer="spinal_reflex_camera_switch",
            priority=OWNER_CAMERA_LOCK_PRIORITY,
            lease_s=OWNER_CAMERA_LOCK_LEASE_S,
            respect_lease=False,
        )
    except Exception as e:
        return {"ok": False, "error": str(e), "target": target_idx}

    try:
        from System.swarm_iris import invalidate_camera_cache

        invalidate_camera_cache()
    except Exception:
        pass

    try:
        from System.swarm_eye_registry import refresh_eye_registry

        refresh_eye_registry(write_receipt=True)
    except Exception:
        pass

    try:
        log = _STATE / "camera_hardware_probe.jsonl"
        row = {
            "ts": time.time(),
            "camera_index": int(target_idx),
            "status": "switched",
            "reason": "spinal_reflex_camera_switch → write_target",
            "name": rec.get("name"),
        }
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass

    return {
        "ok": True,
        "target": int(target_idx),
        "name": rec.get("name"),
        "record": rec,
    }


def camera_switch_reply(result: dict) -> str:
    """Plain, receipt-grounded reply. No star-actions."""
    if result.get("ok"):
        name = result.get("name", f"Camera {result.get('target')}")
        idx = result.get("target")
        return (
            f"Switched active eye to {name} (index {idx}). "
            "Receipt: active_saccade_target.json (+ .txt mirror) + camera_hardware_probe.jsonl."
        )
    return f"Camera switch failed: {result.get('error', 'unknown error')}"


__all__ = [
    "detect_camera_switch_intent",
    "execute_camera_switch",
    "camera_switch_reply",
]
