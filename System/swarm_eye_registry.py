#!/usr/bin/env python3
"""Two-eye role registry for Alice's camera body.

r1027: camera indices renumber on hotplug, especially through the Fresco/USB
adapter. This organ binds eyes by device identity (AVFoundation/Qt uniqueID or
VID/PID + name), assigns stable roles, and records health without creating a
rival capture stack.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]
    read_text_locked = None  # type: ignore[assignment]

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "SIFTA_EYE_REGISTRY_V1"
EVENT_TRUTH_LABEL = "SIFTA_EYE_REGISTRY_EVENT_V1"
SNAPSHOT_NAME = "eye_registry.json"
LEDGER_NAME = "eye_registry.jsonl"
EVENT_LEDGER_NAME = "eye_registry_events.jsonl"

OWNER_ROLE = "owner_eye"
WORLD_ROLE = "world_eye"
AUX_ROLE = "aux_eye"

_VID_PID_RE = re.compile(r"\bVID:([0-9A-Fa-f]+)\s+PID:([0-9A-Fa-f]+)\b")


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(row), ensure_ascii=False, sort_keys=True, default=str) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line, encoding="utf-8")
    else:  # pragma: no cover
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        text = read_text_locked(path, encoding="utf-8", errors="replace") if read_text_locked else path.read_text(encoding="utf-8", errors="replace")
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _norm(text: Any) -> str:
    return " ".join(str(text or "").replace("’", "'").strip().lower().split())


def _short_hash(text: str, n: int = 10) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def _vid_pid(name: str) -> tuple[str, str]:
    m = _VID_PID_RE.search(name or "")
    return (m.group(1).lower(), m.group(2).lower()) if m else ("", "")


def normalize_device(device: Mapping[str, Any] | tuple[Any, Any] | tuple[Any, Any, Any], index: int = 0) -> dict[str, Any]:
    """Normalize camera device rows from Qt/AVFoundation/test fixtures."""
    if isinstance(device, Mapping):
        uid = str(device.get("unique_id") or device.get("uid") or device.get("id") or "").strip()
        name = str(device.get("name") or device.get("desc") or device.get("description") or "").strip()
        idx_raw = device.get("index", index)
    elif isinstance(device, tuple):
        if len(device) >= 3:
            idx_raw, uid, name = device[0], device[1], device[2]
        else:
            uid, name = device[0], device[1]
            idx_raw = index
        uid = str(uid or "").strip()
        name = str(name or "").strip()
    else:
        uid, name, idx_raw = "", str(device or "").strip(), index
    try:
        idx = int(idx_raw)
    except Exception:
        idx = int(index)
    vid, pid = _vid_pid(name)
    name_key = _norm(name)
    identity_key = uid or (f"vid:{vid}:pid:{pid}:name:{name_key}" if vid or pid else f"name:{name_key}")
    return {
        "index": idx,
        "unique_id": uid or None,
        "name": name or "unknown camera",
        "name_key": name_key,
        "vid": vid or None,
        "pid": pid or None,
        "device_identity_key": identity_key,
        "device_path": uid or name or identity_key,
    }


def classify_eye_role(device: Mapping[str, Any]) -> str:
    name = _norm(device.get("name") or device.get("name_key") or "")
    uid = _norm(device.get("unique_id") or "")
    hay = f"{name} {uid}"
    if any(token in hay for token in ("macbook pro camera", "facetime", "built-in", "built in", "laptop", "internal")):
        return OWNER_ROLE
    if any(token in hay for token in ("logitech", "usb", "vid:1133", "external", "webcam", "fresco")):
        return WORLD_ROLE
    if "desk view" in hay:
        return AUX_ROLE
    if "iphone" in hay or "continuity" in hay:
        return AUX_ROLE
    return AUX_ROLE


def eye_id_for_device(device: Mapping[str, Any], role: str | None = None) -> str:
    role_name = role or classify_eye_role(device)
    if role_name in {OWNER_ROLE, WORLD_ROLE}:
        return role_name
    key = str(device.get("device_identity_key") or device.get("unique_id") or device.get("name") or "unknown")
    return f"{AUX_ROLE}_{_short_hash(key, 8)}"


def _previous_by_identity(snapshot: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    eyes = snapshot.get("eyes") if isinstance(snapshot.get("eyes"), list) else []
    for eye in eyes:
        if not isinstance(eye, dict):
            continue
        key = str((eye.get("device_identity") or {}).get("key") or "")
        if key:
            out[key] = eye
    return out


def _latest_visual_age_by_eye(state: Path, now: float) -> dict[str, float]:
    path = state / "saccadic_blink_vision.jsonl"
    out: dict[str, float] = {}
    if not path.exists():
        return out
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
    except Exception:
        return out
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        eye_id = str(row.get("eye_id") or "")
        if not eye_id or eye_id in out:
            continue
        try:
            ts = float(row.get("ts") or 0.0)
            out[eye_id] = max(0.0, now - ts)
        except Exception:
            continue
    return out


def _live_devices(devices: Optional[Iterable[Mapping[str, Any] | tuple[Any, ...]]] = None) -> list[dict[str, Any]]:
    if devices is None:
        try:
            from System.swarm_camera_target import live_devices

            devices = live_devices()
        except Exception:
            devices = []
    return [normalize_device(dev, index=i) for i, dev in enumerate(devices or [])]


def build_eye_registry(
    *,
    state_dir: Path | str | None = None,
    devices: Optional[Iterable[Mapping[str, Any] | tuple[Any, ...]]] = None,
    now: float | None = None,
    previous: Optional[Mapping[str, Any]] = None,
    frame_age_by_eye: Optional[Mapping[str, float]] = None,
) -> dict[str, Any]:
    """Build a registry snapshot. Missing prior eyes become STALE, not swapped."""
    state = _state_dir(state_dir)
    ts = float(now if now is not None else time.time())
    previous_snapshot = dict(previous) if previous is not None else _read_json(state / SNAPSHOT_NAME)
    previous_by_key = _previous_by_identity(previous_snapshot)
    visual_age = dict(frame_age_by_eye or _latest_visual_age_by_eye(state, ts))

    live = _live_devices(devices)
    eyes: list[dict[str, Any]] = []
    live_keys: set[str] = set()
    for dev in live:
        key = str(dev["device_identity_key"])
        live_keys.add(key)
        prior = previous_by_key.get(key, {})
        role = str(prior.get("role") or classify_eye_role(dev))
        eye_id = str(prior.get("eye_id") or eye_id_for_device(dev, role))
        age = visual_age.get(eye_id)
        eyes.append({
            "eye_id": eye_id,
            "role": role,
            "health": "GREEN",
            "connection_state": "LIVE",
            "device_name": dev["name"],
            "device_path": dev["device_path"],
            "current_index": dev["index"],
            "index_observation_only": True,
            "device_identity": {
                "key": key,
                "unique_id": dev.get("unique_id"),
                "vid": dev.get("vid"),
                "pid": dev.get("pid"),
                "name_key": dev.get("name_key"),
            },
            "last_frame_age_s": age,
            "last_seen_ts": ts,
            "adapter_note": "identity-bound; index is observation-only",
        })

    for key, prior in previous_by_key.items():
        if key in live_keys:
            continue
        stale = dict(prior)
        stale["health"] = "STALE"
        stale["connection_state"] = "STALE_OR_DETACHED"
        stale["current_index"] = None
        stale["index_observation_only"] = True
        stale["last_frame_age_s"] = visual_age.get(str(stale.get("eye_id") or ""), stale.get("last_frame_age_s"))
        stale["stale_since_ts"] = ts
        stale["adapter_note"] = "device absent; role preserved by identity, not reassigned to another index"
        eyes.append(stale)

    role_order = {OWNER_ROLE: 0, WORLD_ROLE: 1, AUX_ROLE: 2}
    eyes.sort(key=lambda e: (role_order.get(str(e.get("role")), 9), str(e.get("eye_id") or "")))
    return {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "schema": TRUTH_LABEL,
        "device_binding": "unique_id_or_vid_pid_name_never_index",
        "eyes": eyes,
        "live_eye_count": sum(1 for e in eyes if e.get("connection_state") == "LIVE"),
        "stale_eye_count": sum(1 for e in eyes if e.get("connection_state") != "LIVE"),
        "roles": {str(e.get("role")): str(e.get("eye_id")) for e in eyes if e.get("connection_state") == "LIVE"},
    }


def read_eye_registry(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    return _read_json(_state_dir(state_dir) / SNAPSHOT_NAME)


def refresh_eye_registry(
    *,
    state_dir: Path | str | None = None,
    devices: Optional[Iterable[Mapping[str, Any] | tuple[Any, ...]]] = None,
    now: float | None = None,
    write_receipt: bool = True,
) -> dict[str, Any]:
    state = _state_dir(state_dir)
    previous = _read_json(state / SNAPSHOT_NAME)
    snapshot = build_eye_registry(state_dir=state, devices=devices, now=now, previous=previous)
    if write_receipt:
        state.mkdir(parents=True, exist_ok=True)
        (state / SNAPSHOT_NAME).write_text(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8")
        _append_jsonl(state / LEDGER_NAME, snapshot)

        prev_by_key = _previous_by_identity(previous)
        next_by_key = _previous_by_identity(snapshot)
        prev_keys = set(prev_by_key)
        next_live_keys = {
            key for key, eye in next_by_key.items()
            if eye.get("connection_state") == "LIVE"
        }
        prev_live_keys = {
            key for key, eye in prev_by_key.items()
            if eye.get("connection_state") == "LIVE"
        }
        events: list[dict[str, Any]] = []
        for key in sorted(next_live_keys - prev_live_keys):
            eye = next_by_key[key]
            events.append({
                "ts": snapshot["ts"],
                "truth_label": EVENT_TRUTH_LABEL,
                "event": "EYE_ATTACHED",
                "eye_id": eye.get("eye_id"),
                "role": eye.get("role"),
                "device_name": eye.get("device_name"),
                "device_identity_key": key,
            })
        for key in sorted(prev_live_keys - next_live_keys):
            eye = next_by_key.get(key) or prev_by_key[key]
            events.append({
                "ts": snapshot["ts"],
                "truth_label": EVENT_TRUTH_LABEL,
                "event": "EYE_STALE",
                "eye_id": eye.get("eye_id"),
                "role": eye.get("role"),
                "device_name": eye.get("device_name"),
                "device_identity_key": key,
            })
        for event in events:
            _append_jsonl(state / EVENT_LEDGER_NAME, event)
    return snapshot


def eye_for_role(role: str, *, state_dir: Path | str | None = None, include_stale: bool = False) -> dict[str, Any]:
    snapshot = read_eye_registry(state_dir=state_dir)
    eyes = snapshot.get("eyes") if isinstance(snapshot.get("eyes"), list) else []
    for eye in eyes:
        if not isinstance(eye, dict):
            continue
        if eye.get("role") != role:
            continue
        if include_stale or eye.get("connection_state") == "LIVE":
            return eye
    return {}


def default_eye_id(*, role: str = OWNER_ROLE, state_dir: Path | str | None = None) -> str:
    eye = eye_for_role(role, state_dir=state_dir, include_stale=True)
    if eye.get("eye_id"):
        return str(eye["eye_id"])
    return role if role in {OWNER_ROLE, WORLD_ROLE} else AUX_ROLE


def format_eye_registry(snapshot: Mapping[str, Any]) -> str:
    eyes = snapshot.get("eyes") if isinstance(snapshot.get("eyes"), list) else []
    if not eyes:
        return "Eye registry: no live camera devices observed."
    lines = ["Eye registry:"]
    for eye in eyes:
        lines.append(
            f"- {eye.get('eye_id')} role={eye.get('role')} health={eye.get('health')} "
            f"name={eye.get('device_name')} idx={eye.get('current_index')}"
        )
    return "\n".join(lines)


__all__ = [
    "AUX_ROLE",
    "EVENT_LEDGER_NAME",
    "LEDGER_NAME",
    "OWNER_ROLE",
    "SNAPSHOT_NAME",
    "TRUTH_LABEL",
    "WORLD_ROLE",
    "build_eye_registry",
    "classify_eye_role",
    "default_eye_id",
    "eye_for_role",
    "eye_id_for_device",
    "format_eye_registry",
    "normalize_device",
    "read_eye_registry",
    "refresh_eye_registry",
]


if __name__ == "__main__":  # pragma: no cover
    print(format_eye_registry(refresh_eye_registry(write_receipt=True)))
