#!/usr/bin/env python3
"""
System/swarm_sensor_attention_director.py
═══════════════════════════════════════════════════════════════════════════
Resident sensor attention policy for Alice.

This organ does not own camera hardware directly. It reads the existing
sensory ledgers, chooses the sense that should currently receive attention,
then leases the canonical active eye through System.swarm_camera_target.

Pipeline:
    Sensor Registry -> World State -> Attention Policy
    -> Active Sense Lease -> Evidence Ledger
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STATE = _REPO / ".sifta_state"
_LEDGER = "sensory_attention_ledger.jsonl"

_CLOSE_EYE_NAME = "MacBook Pro Camera"
_CLOSE_EYE_INDEX = 1
_ROOM_EYE_NAME = "USB Camera VID:1133 PID:2081"
_ROOM_EYE_INDEX = 0

_FRESH_WINDOW_S = 6.0
_IDE_FRESH_WINDOW_S = 15.0
_AUDIO_SPIKE_RMS = 0.075
_MOTION_SPIKE = 0.18
_LOW_ENTROPY_BITS = 4.0


@dataclass(frozen=True)
class SenseCandidate:
    role: str
    name: str
    index: int
    purpose: str
    priority: int = 35


@dataclass(frozen=True)
class WorldState:
    now: float
    visual_ts: Optional[float] = None
    visual_entropy_bits: Optional[float] = None
    visual_motion_mean: Optional[float] = None
    visual_face_locked: Optional[bool] = None
    audio_ts: Optional[float] = None
    audio_rms: Optional[float] = None
    faces_ts: Optional[float] = None
    faces_detected: int = 0
    owner_visible: bool = False
    unknown_faces: int = 0
    face_center_x: Optional[float] = None
    ide_ts: Optional[float] = None
    ide_x: Optional[int] = None
    ide_name: Optional[str] = None
    current_target_name: Optional[str] = None
    current_target_index: Optional[int] = None
    current_target_writer: Optional[str] = None
    current_target_priority: int = 0
    current_target_lease_until: Optional[float] = None


@dataclass(frozen=True)
class AttentionDecision:
    target_role: str
    target_name: str
    target_index: int
    priority: int
    lease_s: float
    reason: str
    evidence: dict[str, Any]
    write_hardware: bool = True


def _state_path(state_dir: Path | str, name: str) -> Path:
    return Path(state_dir) / name


def _coerce_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
        return out if out == out and out not in (float("inf"), float("-inf")) else None
    except Exception:
        return None


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _event_ts(row: dict[str, Any]) -> Optional[float]:
    for key in ("ts", "timestamp", "time", "ts_captured", "created_at"):
        ts = _coerce_float(row.get(key))
        if ts is not None:
            return ts
    return None


def _fresh(ts: Optional[float], now: float, window_s: float = _FRESH_WINDOW_S) -> bool:
    return ts is not None and 0 <= now - ts <= window_s


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
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _latest_json(path: Path) -> Optional[dict[str, Any]]:
    rows = _tail_json_rows(path)
    return rows[-1] if rows else None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "owner", "architect", "ioan"}


def _owner_name_seen(row: dict[str, Any]) -> bool:
    haystack_parts: list[str] = []
    for key in (
        "audience",
        "identity",
        "person",
        "speaker",
        "label",
        "matched_identity",
        "recognized_as",
    ):
        value = row.get(key)
        if isinstance(value, str):
            haystack_parts.append(value)
        elif isinstance(value, Iterable) and not isinstance(value, (bytes, dict)):
            haystack_parts.extend(str(v) for v in value)
    haystack = " ".join(haystack_parts).lower()
    return any(token in haystack for token in ("architect", "owner", "ioan", "george anton"))


def _face_count(row: dict[str, Any]) -> int:
    for key in ("faces_detected", "face_count", "faces", "num_faces"):
        value = row.get(key)
        if isinstance(value, list):
            return len(value)
        if value is not None:
            return _coerce_int(value, 0)
    boxes = row.get("bounding_boxes") or row.get("bboxes")
    if isinstance(boxes, list):
        return len(boxes)
    return 0


def _face_center_x(row: dict[str, Any]) -> Optional[float]:
    for key in ("face_center_x", "center_x", "cx"):
        value = _coerce_float(row.get(key))
        if value is not None:
            return value
    boxes = row.get("bounding_boxes") or row.get("bboxes")
    if isinstance(boxes, list) and boxes:
        box = boxes[0]
        if isinstance(box, dict):
            x = _coerce_float(box.get("x"))
            w = _coerce_float(box.get("w") or box.get("width"))
            if x is not None and w is not None:
                return x + w / 2.0
        elif isinstance(box, (list, tuple)) and len(box) >= 4:
            x = _coerce_float(box[0])
            w = _coerce_float(box[2])
            if x is not None and w is not None:
                return x + w / 2.0
    return None


def _latest_active_ide(rows: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    for row in reversed(rows):
        windows = row.get("windows")
        if isinstance(windows, list):
            for win in windows:
                if isinstance(win, dict) and win.get("is_active"):
                    out = dict(win)
                    out["_ledger_ts"] = _event_ts(row)
                    return out
        if row.get("is_active") or row.get("active_ide"):
            return row
    return None


def collect_world_state(
    *,
    state_dir: Path | str = _STATE,
    now: Optional[float] = None,
) -> WorldState:
    """Read the current sensory ledgers into one policy-ready state."""
    state = Path(state_dir)
    now_f = float(now if now is not None else time.time())

    visual = _latest_json(_state_path(state, "visual_stigmergy.jsonl")) or {}
    audio = _latest_json(_state_path(state, "audio_ingress_log.jsonl")) or {}
    faces = _latest_json(_state_path(state, "face_detection_events.jsonl")) or {}
    ide = _latest_active_ide(_tail_json_rows(_state_path(state, "ide_screen_swimmers.jsonl"))) or {}

    visual_ts = _event_ts(visual)
    audio_ts = _event_ts(audio)
    faces_ts = _event_ts(faces)
    ide_ts = _coerce_float(ide.get("_ledger_ts")) or _event_ts(ide)

    faces_detected = _face_count(faces)
    visual_face_locked = visual.get("face_locked")
    owner_visible = (
        _truthy(faces.get("owner_visible"))
        or _truthy(faces.get("architect_visible"))
        or _owner_name_seen(faces)
        or (
            _fresh(visual_ts, now_f)
            and _truthy(visual_face_locked)
            and faces_detected <= 1
        )
    )
    unknown_faces = max(0, faces_detected - (1 if owner_visible else 0))

    current = None
    try:
        from System.swarm_camera_target import read_target

        current = read_target()
    except Exception:
        current = None

    return WorldState(
        now=now_f,
        visual_ts=visual_ts,
        visual_entropy_bits=_coerce_float(visual.get("entropy_bits")),
        visual_motion_mean=_coerce_float(
            visual.get("motion_mean")
            if "motion_mean" in visual
            else visual.get("motion_score")
        ),
        visual_face_locked=_truthy(visual_face_locked) if visual_face_locked is not None else None,
        audio_ts=audio_ts,
        audio_rms=_coerce_float(audio.get("rms_amplitude") if "rms_amplitude" in audio else audio.get("rms")),
        faces_ts=faces_ts,
        faces_detected=faces_detected,
        owner_visible=bool(owner_visible and (_fresh(faces_ts, now_f) or _fresh(visual_ts, now_f))),
        unknown_faces=unknown_faces if _fresh(faces_ts, now_f) else 0,
        face_center_x=_face_center_x(faces),
        ide_ts=ide_ts,
        ide_x=_coerce_int(ide.get("x"), 0) if ide else None,
        ide_name=str(ide.get("name") or ide.get("active_ide") or "") or None,
        current_target_name=current.get("name") if isinstance(current, dict) else None,
        current_target_index=current.get("index") if isinstance(current, dict) else None,
        current_target_writer=current.get("writer") if isinstance(current, dict) else None,
        current_target_priority=_coerce_int(current.get("priority"), 0) if isinstance(current, dict) else 0,
        current_target_lease_until=_coerce_float(current.get("lease_until")) if isinstance(current, dict) else None,
    )


def default_sensor_registry() -> dict[str, SenseCandidate]:
    return {
        "close_owner_eye": SenseCandidate(
            role="close_owner_eye",
            name=_CLOSE_EYE_NAME,
            index=_CLOSE_EYE_INDEX,
            purpose="Near-field owner face, laptop desk, conversation focus.",
            priority=35,
        ),
        "room_patrol_eye": SenseCandidate(
            role="room_patrol_eye",
            name=_ROOM_EYE_NAME,
            index=_ROOM_EYE_INDEX,
            purpose="Wide room patrol: motion, distance, owner search, unknown events.",
            priority=35,
        ),
    }


def _evidence(world: WorldState) -> dict[str, Any]:
    return {
        "visual_entropy_bits": world.visual_entropy_bits,
        "visual_motion_mean": world.visual_motion_mean,
        "visual_face_locked": world.visual_face_locked,
        "audio_rms": world.audio_rms,
        "faces_detected": world.faces_detected,
        "owner_visible": world.owner_visible,
        "unknown_faces": world.unknown_faces,
        "ide_x": world.ide_x,
        "ide_name": world.ide_name,
        "current_target_name": world.current_target_name,
        "current_target_writer": world.current_target_writer,
    }


def _decision(candidate: SenseCandidate, world: WorldState, reason: str) -> AttentionDecision:
    return AttentionDecision(
        target_role=candidate.role,
        target_name=candidate.name,
        target_index=candidate.index,
        priority=candidate.priority,
        lease_s=4.0,
        reason=reason,
        evidence=_evidence(world),
    )


def decide_attention(
    world: WorldState,
    *,
    registry: Optional[dict[str, SenseCandidate]] = None,
) -> AttentionDecision:
    """Choose the next active eye from world state and policy thresholds."""
    reg = registry or default_sensor_registry()
    close_eye = reg["close_owner_eye"]
    room_eye = reg["room_patrol_eye"]

    ide_fresh = _fresh(world.ide_ts, world.now, _IDE_FRESH_WINDOW_S)
    visual_fresh = _fresh(world.visual_ts, world.now)
    audio_fresh = _fresh(world.audio_ts, world.now)
    faces_fresh = _fresh(world.faces_ts, world.now)

    if ide_fresh and world.ide_x is not None and world.ide_x >= 1728:
        return _decision(room_eye, world, "external_ide_focus_room_eye")

    if faces_fresh and world.owner_visible:
        return _decision(close_eye, world, "owner_face_locked_close_eye")

    audio_spike = audio_fresh and (world.audio_rms or 0.0) >= _AUDIO_SPIKE_RMS
    motion_spike = visual_fresh and (world.visual_motion_mean or 0.0) >= _MOTION_SPIKE
    low_entropy = visual_fresh and world.visual_entropy_bits is not None and world.visual_entropy_bits <= _LOW_ENTROPY_BITS
    face_lost = faces_fresh and world.faces_detected == 0 and not world.owner_visible
    unknown_face = faces_fresh and world.unknown_faces > 0

    if audio_spike or motion_spike or low_entropy or face_lost or unknown_face:
        reasons = []
        if audio_spike:
            reasons.append("audio_spike")
        if motion_spike:
            reasons.append("motion_spike")
        if low_entropy:
            reasons.append("low_visual_entropy")
        if face_lost:
            reasons.append("owner_lost")
        if unknown_face:
            reasons.append("unknown_face")
        return _decision(room_eye, world, "room_patrol_" + "+".join(reasons))

    if ide_fresh and world.ide_x is not None and world.ide_x < 1728:
        return _decision(close_eye, world, "primary_ide_focus_close_eye")

    if world.current_target_name:
        role = "room_patrol_eye" if world.current_target_index == _ROOM_EYE_INDEX else "close_owner_eye"
        candidate = room_eye if role == "room_patrol_eye" else close_eye
        return _decision(candidate, world, "hold_current_eye")

    return _decision(close_eye, world, "default_owner_survival_eye")


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")


def apply_attention_decision(
    decision: AttentionDecision,
    *,
    state_dir: Path | str = _STATE,
    write_hardware: bool = True,
) -> dict[str, Any]:
    """Write the active camera lease and append a reasoned evidence row."""
    written: Optional[dict[str, Any]] = None
    if write_hardware and decision.write_hardware:
        try:
            from System.swarm_camera_target import write_target

            written = write_target(
                name=decision.target_name,
                index=decision.target_index,
                writer="swarm_sensor_attention_director",
                priority=decision.priority,
                lease_s=decision.lease_s,
                respect_lease=True,
            )
        except Exception as exc:
            written = {"error": repr(exc)}

    row = {
        "ts": time.time(),
        "organ": "swarm_sensor_attention_director",
        "decision": asdict(decision),
        "camera_target": written,
    }
    _append_jsonl(_state_path(Path(state_dir), _LEDGER), row)
    return row


def tick(
    *,
    state_dir: Path | str = _STATE,
    write_hardware: bool = True,
    now: Optional[float] = None,
) -> AttentionDecision:
    world = collect_world_state(state_dir=state_dir, now=now)
    decision = decide_attention(world)
    apply_attention_decision(decision, state_dir=state_dir, write_hardware=write_hardware)
    return decision


def _format_decision(decision: AttentionDecision) -> str:
    return (
        f"{decision.target_role}: {decision.target_name} "
        f"(index={decision.target_index}, reason={decision.reason})"
    )


def summary_for_alice(
    *,
    state_dir: Path | str = _STATE,
    max_age_s: float = 30.0,
) -> str:
    """Return Alice's current attention lease as a compact prompt block."""
    state = Path(state_dir)
    rows = _tail_json_rows(_state_path(state, _LEDGER))
    if not rows:
        return ""
    row = rows[-1]
    ts = _event_ts(row)
    now = time.time()
    if ts is None or now - ts > max_age_s:
        return ""
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    camera_target = row.get("camera_target") if isinstance(row.get("camera_target"), dict) else {}
    reason = str(decision.get("reason") or "unknown")
    role = str(decision.get("target_role") or "unknown_sense")
    name = str(decision.get("target_name") or camera_target.get("name") or "unknown")
    evidence = decision.get("evidence") if isinstance(decision.get("evidence"), dict) else {}
    bits = []
    for key in ("owner_visible", "unknown_faces", "audio_rms", "visual_motion_mean", "visual_entropy_bits", "ide_name"):
        value = evidence.get(key)
        if value not in (None, "", False):
            bits.append(f"{key}={value}")
    evidence_text = ", ".join(bits[:5]) if bits else "no fresh high-salience evidence"
    return (
        "SENSORIMOTOR ATTENTION:\n"
        f"- active_sense={role} target={name}\n"
        f"- reason={reason}\n"
        f"- evidence={evidence_text}\n"
        "- policy=choose the sense that best reduces uncertainty; every shift is ledgered"
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Alice resident sensor attention director")
    parser.add_argument("--once", action="store_true", help="Run one attention tick and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=float, default=2.0, help="Daemon tick interval seconds")
    parser.add_argument("--dry-run", action="store_true", help="Do not write the active camera target")
    args = parser.parse_args(argv)

    if args.daemon:
        print("[attention_director] online")
        while True:
            decision = tick(write_hardware=not args.dry_run)
            print("[attention_director]", _format_decision(decision), flush=True)
            time.sleep(max(0.25, args.interval))
    decision = tick(write_hardware=not args.dry_run)
    print(_format_decision(decision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
