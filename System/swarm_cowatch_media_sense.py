#!/usr/bin/env python3
"""System/swarm_cowatch_media_sense.py — co-watch visual sense (r212-cowatch-eyes).

While the owner co-watches media (YouTube on the speakers) Alice should also SEE
the frame, so her diary/field hold what's actually on screen — not just the
pasted transcript. This organ captures the desktop during ACTIVE co-watch only,
fingerprints it like every other visual row, and deposits ONE row into the same
visual_stigmergy lane the camera writes — tagged source=co_watch_desktop /
stigmergic_label=OBSERVED_MEDIA.

Honest boundaries (§7.16 / §6):
  • This is co-watched media on the owner's screen — NOT Alice's camera, NOT a
    real-room scene, NOT her own eye. The OBSERVED_MEDIA label is the line. She
    may learn from it; she may never claim she saw it in the room.
  • It fires ONLY during active co-watch (get_unified_cowatch_context non-empty)
    and is hard-throttled — never a silent always-on desktop screenshotter, no
    STGM burn on ambient. No co-watch, no capture, no claim.

Cowork Claude cut this (r212) because Alice's Talk turn has no file/shell
effector and her arm hand was blocked; the capture itself runs on the owner's
Mac via `screencapture` and is verified there.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_VISUAL_LANE = _STATE / "visual_stigmergy.jsonl"
_COWATCH_TRACE = _STATE / "cowatch_media_trace.jsonl"
_FRAMES_DIR = _STATE / "cowatch_frames"
_LAST_CAPTURE_FILE = _STATE / "cowatch_last_capture.json"

# Hard throttle: at most one ambient co-watch frame per this many seconds.
_THROTTLE_S = float(os.environ.get("SIFTA_COWATCH_CAPTURE_THROTTLE_S", "25"))


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _cowatch_active() -> tuple[bool, str]:
    """Return (active, context_block). Co-watch is active when the unified field
    has any live media channel (the block is non-empty)."""
    try:
        from System.swarm_unified_cowatch_field import get_unified_cowatch_context
        ctx = get_unified_cowatch_context() or ""
    except Exception:
        ctx = ""
    return (bool(ctx.strip()), ctx)


def _media_title(ctx: str) -> str:
    """Best-effort media title from the unified field block (YouTube / Title lines)."""
    for line in (ctx or "").splitlines():
        low = line.lower()
        if "youtube" in low or "title" in low:
            if '"' in line:
                try:
                    return line.split('"', 2)[1].strip()
                except Exception:
                    pass
    return ""


def _fingerprint(image_path: str) -> Dict[str, Any]:
    """Reuse the canonical visual fingerprint; degrade to hash-only if unavailable."""
    try:
        from System.swarm_bonsai_image_organ import _visual_fingerprint
        return _visual_fingerprint(image_path)
    except Exception:
        try:
            raw = Path(image_path).read_bytes()
            return {"sha8": hashlib.sha256(raw).hexdigest()[:8], "motion_mean": 0.0,
                    "fingerprint_note": "hash-only"}
        except Exception:
            return {"sha8": "", "motion_mean": 0.0}


def _capture_screen(out_path: Path) -> Dict[str, Any]:
    """Capture the main display via macOS screencapture. Apple-Silicon/macOS only."""
    if platform.system() != "Darwin":
        return {"ok": False, "error": "co-watch capture is macOS-only (screencapture); not on this host"}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            ["screencapture", "-x", str(out_path)],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"screencapture launch failed: {type(exc).__name__}: {exc}"}
    if proc.returncode != 0 or not out_path.exists():
        return {"ok": False, "error": f"screencapture rc={proc.returncode}: {(proc.stderr or '')[:200]}"}
    return {"ok": True}


def _read_last_capture_ts() -> float:
    try:
        return float(json.loads(_LAST_CAPTURE_FILE.read_text(encoding="utf-8")).get("ts", 0.0))
    except Exception:
        return 0.0


def capture_cowatch_frame_if_active(*, force: bool = False) -> Dict[str, Any]:
    """Self-gated, self-throttled co-watch frame capture + OBSERVED_MEDIA deposit.

    A periodic caller (desktop heartbeat / attention director) can call this
    every few seconds; it no-ops unless co-watch is active and the throttle has
    elapsed. Returns a dict describing what happened (never raises).
    """
    active, ctx = _cowatch_active()
    if not active and not force:
        return {"ok": False, "skipped": "no_cowatch"}

    now = time.time()
    if not force and (now - _read_last_capture_ts()) < _THROTTLE_S:
        return {"ok": False, "skipped": "throttled"}

    out_path = _FRAMES_DIR / f"{int(now * 1000)}.png"
    cap = _capture_screen(out_path)
    if not cap.get("ok"):
        return {"ok": False, "error": cap.get("error")}

    fp = _fingerprint(str(out_path))
    title = _media_title(ctx)
    row = {
        "ts": now,
        "source": "co_watch_desktop",
        "stigmergic_label": "OBSERVED_MEDIA",
        "media_title": title,
        "cowatch_context_sha8": hashlib.sha256((ctx or "").encode("utf-8")).hexdigest()[:8],
        "image_path": str(out_path),
        "receipt_id": f"r212-cowatch-{int(now * 1000)}",
        **fp,
    }
    _append_jsonl(_VISUAL_LANE, row)      # same lane the camera writes — but honestly labeled
    _append_jsonl(_COWATCH_TRACE, row)
    try:
        _LAST_CAPTURE_FILE.write_text(json.dumps({"ts": now}), encoding="utf-8")
    except Exception:
        pass
    return {"ok": True, "row": row, "image_path": str(out_path)}


if __name__ == "__main__":  # self-probe: prints the gate decision, no claim faked
    active, ctx = _cowatch_active()
    print("co_watch_active:", active, "| throttle_s:", _THROTTLE_S)
    print(capture_cowatch_frame_if_active())
