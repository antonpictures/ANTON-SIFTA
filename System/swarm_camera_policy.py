#!/usr/bin/env python3
"""Runtime policy and evidence for Alice's single owner eye.

The MacBook camera is the one live capture source for the SIFTA desktop.
Other cameras may remain visible in hardware inventory, but they must not be
opened as a second capture session or used as an automatic fallback.
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"


def single_owner_eye_enabled() -> bool:
    """Return the capture policy; enabled by default for the desktop node."""
    value = os.environ.get("SIFTA_SINGLE_OWNER_EYE", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def is_owner_eye_name(name: Optional[str]) -> bool:
    text = str(name or "").casefold()
    if any(token in text for token in ("iphone", "ipad", "continuity", "desk view", "virtual", "obs", "model id:")):
        return False
    return any(token in text for token in ("macbook pro camera", "facetime", "built-in", "built in"))


def capture_allowed(name: Optional[str]) -> bool:
    """Only the embedded owner camera may be opened under this policy."""
    return not single_owner_eye_enabled() or is_owner_eye_name(name)


def rejection_reason(name: Optional[str]) -> str:
    return (
        f"SINGLE_OWNER_EYE: capture denied for {name or 'unknown camera'}; "
        "only the embedded MacBook camera may be live"
    )


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _latest_jsonl(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 65536))
            data = handle.read(65536)
        if size > 65536:
            data = data.partition(b"\n")[2]
        lines = data.decode("utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    for line in reversed(lines[-200:]):
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def camera_eye_snapshot(state_dir: str | Path = _STATE, *, now: float | None = None) -> Dict[str, Any]:
    """Return receipt-backed state for the WCT monitor and eval matrix."""
    state = Path(state_dir)
    target = _read_json(state / "active_saccade_target.json")
    from System.swarm_camera_unified_field_proof import build_camera_unified_field_proof

    current = time.time() if now is None else float(now)
    proof = build_camera_unified_field_proof(state, now=current, stale_s=30.0).to_dict()
    visual = _latest_jsonl(state / "visual_stigmergy.jsonl")
    topology = _read_json(state / "camera_topology_latest.json")
    active_name = str(target.get("name") or proof.get("device") or "")
    frame_age = proof.get("frame_age_s", proof.get("fresh_frame_age_s"))
    runtime = _latest_jsonl(state / "camera_capture_policy.jsonl")
    runtime_age = _age(runtime.get("ts"), current)
    runtime_verified = bool(
        runtime_age is not None and runtime_age <= 30.0
        and runtime.get("single_owner_eye") is True
        and runtime.get("secondary_capture") is False
        and runtime.get("capture_winks") is False
        and is_owner_eye_name(runtime.get("device"))
        and runtime.get("device") == proof.get("device")
    )
    visual_age = _age(visual.get("ts"), current)
    healthy = bool(proof.get("camera_healthy") and capture_allowed(proof.get("device")))
    return {
        "policy": "SINGLE_OWNER_EYE",
        "policy_enabled": single_owner_eye_enabled(),
        "active_target": active_name or None,
        "active_target_allowed": capture_allowed(active_name),
        "connection_state": proof.get("connection_state") if healthy else "DISCONNECTED_OR_STALE_INPUT",
        "camera_healthy": healthy,
        "frame_age_s": frame_age,
        "visual_stigmergy_present": bool(visual),
        "visual_stigmergy_fresh": visual_age is not None and visual_age <= 30.0,
        "runtime_policy_verified": runtime_verified,
        "runtime_policy_age_s": runtime_age,
        "capture_gate_pass": bool(healthy and runtime_verified and capture_allowed(active_name)),
        "topology_devices": len(topology.get("devices") or topology.get("cameras") or []),
        "secondary_capture_allowed": not single_owner_eye_enabled(),
        "ts": current,
    }


def _age(value: object, now: float) -> float | None:
    try:
        age = now - float(value)
        return age if math.isfinite(age) and age >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def camera_eye_evidence_lines(state_dir: str | Path = _STATE) -> List[str]:
    """Short, honest evidence strip for We Code Together."""
    snap = camera_eye_snapshot(state_dir)
    name = snap.get("active_target") or "no active target"
    state = snap.get("connection_state") or "unproven"
    age = snap.get("frame_age_s")
    age_text = f" frame_age={float(age):.1f}s" if isinstance(age, (int, float)) else ""
    visual = "visual trail present" if snap["visual_stigmergy_present"] else "visual trail not found"
    return [
        "EYE INPUT — receipt-backed camera grounding:",
        f"  policy={snap['policy']} active={name} allowed={snap['active_target_allowed']}",
        f"  capture={state}{age_text}; {visual}; secondary_capture={snap['secondary_capture_allowed']}",
        f"  running widget policy verified={snap['runtime_policy_verified']}; capture gate={snap['capture_gate_pass']}",
        "  semantic scene claims require a fresh vision-model receipt tied to the frame.",
    ]
