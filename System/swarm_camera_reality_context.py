#!/usr/bin/env python3
"""
System/swarm_camera_reality_context.py
═══════════════════════════════════════════════════════════════════════════
Camera reality contract for Alice.

This organ answers one narrow question from receipts and code topology:
is Alice watching more than one raw physical camera feed at the same time?

Current SIFTA truth:
  - System.swarm_sensor_attention_director leases ONE active physical eye.
  - System.swarm_iris.webcam_frame opens ONE cv2.VideoCapture per capture.
  - Other evidence channels can run in parallel as ledgers/proxies.

Truth label: CAMERA_REALITY_CONTEXT_123
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

_ACTIVE_TARGET = "active_saccade_target.json"
_ATTENTION_STATUS = "sensory_attention_status.json"
_GAZE_LEDGER = "gaze_interest_monitor.jsonl"
_FACE_LEDGER = "face_detection_events.jsonl"

def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text("utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _tail_json_rows(path: Path, *, keep_bytes: int = 65536) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - keep_bytes))
            raw = f.read().decode("utf-8", "replace")
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _latest_jsonl(path: Path) -> dict[str, Any]:
    rows = _tail_json_rows(path)
    return rows[-1] if rows else {}


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if out == out else default


def _role_for_eye(name: str, index: Any, active_sense: str = "") -> str:
    text = f"{name} {active_sense}".casefold()
    if "room_patrol_eye" in text or "room_patrol" in text:
        return "room_patrol_eye"
    if "close_owner_eye" in text or "close_owner" in text:
        return "close_owner_eye"
    try:
        from System.swarm_camera_target import is_builtin_owner_camera

        if is_builtin_owner_camera(name):
            return "close_owner_eye"
    except Exception:
        if "macbook" in text or "facetime" in text or "built-in" in text:
            return "close_owner_eye"
    if str(name or "").strip():
        return "room_patrol_eye"
    return active_sense or "unknown_eye"


def build_camera_reality_context(
    *,
    state_dir: Path | str = _STATE,
    now: float | None = None,
) -> dict[str, Any]:
    """Return a receipt-grounded camera truth packet.

    The boolean is intentionally conservative. It can become true only when
    a future dual-capture organ writes an explicit receipt; the current visual
    path does not.
    """
    state = Path(state_dir)
    now = time.time() if now is None else float(now)
    target = _read_json(state / _ACTIVE_TARGET)
    status = _read_json(state / _ATTENTION_STATUS)
    gaze = _latest_jsonl(state / _GAZE_LEDGER)
    face = _latest_jsonl(state / _FACE_LEDGER)

    active_name = str(
        target.get("name")
        or status.get("target_name")
        or status.get("camera_name")
        or "unknown"
    )
    active_index = target.get("index", status.get("target_index"))
    active_sense = str(status.get("active_sense") or status.get("target_role") or "")
    active_role = _role_for_eye(active_name, active_index, active_sense)

    lease_until = _coerce_float(target.get("lease_until"), 0.0)
    target_ts = _coerce_float(target.get("ts"), 0.0)
    lease_status = "fresh" if lease_until and lease_until >= now else "last_known"
    if not target and not status:
        lease_status = "unknown"

    parallel_channels: list[str] = []
    if face:
        parallel_channels.append("face_detection_events")
    if gaze:
        parallel_channels.append("gaze_interest_monitor")
    if status:
        parallel_channels.append("sensory_attention_status")

    gaze_target = str(gaze.get("target") or gaze.get("focus") or "")
    faces_detected = face.get("faces_detected", face.get("face_count"))

    answer = (
        "No. In the current code I do not watch two raw physical camera feeds "
        "simultaneously. The attention director leases one active physical eye "
        f"at a time. Right now the active eye is {active_name}"
        f" ({active_role}"
        f"{', index=' + str(active_index) if active_index is not None else ''}, "
        f"{lease_status}). I can also use parallel receipts such as face, gaze, "
        "audio, app focus, and media ledgers, but those are fused context "
        "channels, not a second simultaneous raw camera feed."
    )

    return {
        "truth_label": "CAMERA_REALITY_CONTEXT_123",
        "ts": now,
        "simultaneous_raw_camera_feeds": False,
        "raw_camera_model": "single_active_eye_lease",
        "active_eye": {
            "name": active_name,
            "index": active_index,
            "role": active_role,
            "lease_status": lease_status,
            "target_ts": target_ts or None,
            "lease_until": lease_until or None,
            "writer": target.get("writer") or status.get("writer"),
        },
        "parallel_context_channels": parallel_channels,
        "gaze_target": gaze_target or None,
        "faces_detected": faces_detected,
        "answer_for_alice": answer,
    }


def answer_camera_reality_question(
    *,
    state_dir: Path | str = _STATE,
    now: float | None = None,
) -> str:
    return str(build_camera_reality_context(state_dir=state_dir, now=now)["answer_for_alice"])


def summary_for_alice(
    *,
    state_dir: Path | str = _STATE,
    now: float | None = None,
) -> str:
    ctx = build_camera_reality_context(state_dir=state_dir, now=now)
    eye = ctx["active_eye"]
    parallel = ", ".join(ctx["parallel_context_channels"]) or "none"
    return (
        "CAMERA REALITY CONTEXT:\n"
        "- simultaneous_raw_camera_feeds=false\n"
        "- raw_camera_model=single_active_eye_lease\n"
        f"- active_eye={eye.get('role')} target={eye.get('name')} "
        f"index={eye.get('index')} lease={eye.get('lease_status')}\n"
        f"- parallel_context_channels={parallel}\n"
        "- distinction=parallel ledgers can fuse face/gaze/media/audio evidence; "
        "they are not a second raw camera feed\n"
        f"- answer_if_asked={ctx['answer_for_alice']}"
    )


if __name__ == "__main__":
    print(json.dumps(build_camera_reality_context(), indent=2, sort_keys=True))
