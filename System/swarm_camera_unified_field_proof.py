#!/usr/bin/env python3
"""Unified-field camera proof.

This organ does not open the camera. It reads existing SIFTA field receipts and
answers one narrow question: do current ledgers prove the desktop eye is alive,
and did it see the owner, an unknown user, nobody, or nothing fresh enough to
trust?
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"
TRUTH_LABEL = "CAMERA_UNIFIED_FIELD_PROOF_V1"


@dataclass(frozen=True)
class CameraUnifiedFieldProof:
    truth_label: str
    status: str
    ok: bool
    camera_healthy: bool
    recognition: str
    summary: str
    face_age_s: float | None
    frame_age_s: float | None
    visual_age_s: float | None
    vision_health: float | None
    vision_heartbeat_age_s: float | None
    frame_fresh: bool
    visual_fresh: bool
    vision_fresh: bool
    connection_state: str
    disconnect_reasons: list[str]
    device: str
    frame_sha8: str
    face_confidence: float | None
    face_audience: str
    receipt_id: str
    ts: float
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tail_jsonl(path: Path, max_bytes: int = 16384) -> dict[str, Any]:
    """Return the newest parseable JSON row without loading huge ledgers."""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            handle.seek(max(0, size - max_bytes))
            text = handle.read().decode("utf-8", errors="ignore")
        for line in reversed(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except Exception:
                continue
    except Exception:
        return {}
    return {}


def _load_kernel_vision(state_dir: Path, now: float) -> tuple[float | None, float | None, str]:
    try:
        data = json.loads((state_dir / "kernel_process_table.json").read_text(encoding="utf-8"))
    except Exception:
        return None, None, ""
    for pid, proc in (data.get("processes") or {}).items():
        if any(token in str(pid).lower() for token in ("vision", "eye", "camera", "e35")):
            try:
                health = float(proc.get("health"))
            except Exception:
                health = None
            try:
                hb_age = max(0.0, now - float(proc.get("last_heartbeat_ts") or 0.0))
            except Exception:
                hb_age = None
            return health, hb_age, str(pid)
    return None, None, ""


def _age(now: float, row: dict[str, Any]) -> float | None:
    try:
        ts = float(row.get("ts") or 0.0)
    except Exception:
        return None
    if ts <= 0:
        return None
    return max(0.0, now - ts)


def _owner_name() -> str:
    try:
        from System.swarm_kernel_identity import owner_display_name

        return owner_display_name() or "owner"
    except Exception:
        return "owner"


def _receipt_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "camera_proof_" + hashlib.sha256(raw).hexdigest()[:16]


def build_camera_unified_field_proof(
    state_dir: str | Path | None = None,
    *,
    now: float | None = None,
    stale_s: float = 300.0,
    write_receipt: bool = False,
) -> CameraUnifiedFieldProof:
    """Build an OBSERVED camera proof from existing unified-field receipts."""
    state = Path(state_dir) if state_dir is not None else _DEFAULT_STATE
    t = float(now if now is not None else time.time())

    face = _tail_jsonl(state / "face_detection_events.jsonl")
    frame = _tail_jsonl(state / "active_eye_identity_frames.jsonl")
    visual = _tail_jsonl(state / "visual_stigmergy.jsonl")
    vision_health, vision_hb_age_s, vision_pid = _load_kernel_vision(state, t)

    face_age = _age(t, face)
    frame_age = _age(t, frame)
    visual_age = _age(t, visual)

    # r1026/r1027: blink freshness (heartbeat-driven visual via canonical saccadic bridge).
    # visual_stigmergy / saccadic_blink_vision rows keep age fresh. Per-eye in r1027.
    blink_age = visual_age
    blink_fresh = blink_age is not None and blink_age <= 2.0
    camera_heartbeat_blink_ok = blink_fresh

    frame_fresh = frame_age is not None and frame_age <= stale_s
    visual_fresh = visual_age is not None and visual_age <= stale_s
    vision_fresh = vision_hb_age_s is not None and vision_hb_age_s <= stale_s
    vision_ok = bool(vision_health is not None and vision_health >= 0.5 and vision_fresh)
    # `active_eye_identity_frames.jsonl` is a saved-PNG support path. It can be
    # stale while the live visual field and face detector are still fresh. The
    # health gate is the live photon-derived visual field plus a healthy/fresh
    # vision organ; the saved frame strengthens the proof but must not veto it.
    visual_has_frame_shape = bool(
        (visual.get("w") and visual.get("h"))
        or (frame_fresh and frame.get("w") and frame.get("h"))
    )
    effective_frame_age = visual_age if (visual_age is not None and visual_has_frame_shape) else frame_age
    camera_healthy = bool(
        visual_fresh
        and visual_has_frame_shape
        and vision_ok
    )
    disconnect_reasons: list[str] = []
    if not visual_fresh and frame_age is None:
        disconnect_reasons.append("missing_frame_receipt")
    elif not visual_fresh and not frame_fresh:
        disconnect_reasons.append("stale_frame")
    if visual_age is None:
        disconnect_reasons.append("missing_visual_stigmergy")
    elif not visual_fresh:
        disconnect_reasons.append("stale_visual_stigmergy")
    elif not visual_has_frame_shape:
        disconnect_reasons.append("missing_visual_frame_shape")
    if vision_health is None:
        disconnect_reasons.append("missing_vision_process_health")
    elif vision_health < 0.5:
        disconnect_reasons.append("low_vision_health")
    if vision_hb_age_s is None:
        disconnect_reasons.append("missing_vision_heartbeat")
    elif not vision_fresh:
        disconnect_reasons.append("stale_vision_heartbeat")
    if vision_health is not None and vision_health >= 0.5 and not vision_fresh:
        disconnect_reasons.append("health_value_stale_without_fresh_heartbeat")
    connection_state = "LIVE_CAPTURE_VERIFIED" if camera_healthy else "DISCONNECTED_OR_STALE_INPUT"

    audience = str(face.get("audience") or "").strip().lower()
    try:
        faces_detected = int(face.get("faces_detected") or 0)
    except Exception:
        faces_detected = 0
    try:
        conf = float(face.get("confidence")) if face.get("confidence") is not None else None
    except Exception:
        conf = None

    face_fresh = face_age is not None and face_age <= stale_s
    owner_tokens = {"architect", "owner", "owner_self", "primary_operator", "george", "ioan"}
    if face_fresh and faces_detected > 0 and audience in owner_tokens:
        recognition = "owner"
        status = "OWNER_RECOGNIZED" if camera_healthy else "OWNER_SEEN_CAMERA_UNPROVEN"
    elif face_fresh and faces_detected > 0:
        recognition = "unknown_user"
        status = "UNKNOWN_USER_PRESENT" if camera_healthy else "UNKNOWN_USER_CAMERA_UNPROVEN"
    elif face_fresh and (faces_detected == 0 or audience in {"nobody", "no_face"}):
        recognition = "no_face"
        status = "CAMERA_HEALTHY_NO_FACE" if camera_healthy else "NO_FACE_CAMERA_UNPROVEN"
    else:
        recognition = "no_fresh_face_receipt"
        status = "CAMERA_HEALTHY_NO_FACE_PROOF" if camera_healthy else "NOT_PROVEN"

    ok = status in {"OWNER_RECOGNIZED", "UNKNOWN_USER_PRESENT", "CAMERA_HEALTHY_NO_FACE", "CAMERA_HEALTHY_NO_FACE_PROOF"}

    device = str(frame.get("device") or "") if frame_fresh else ""
    sha8 = str((frame.get("sha8") if frame_fresh else None) or visual.get("sha8") or "")
    if status == "OWNER_RECOGNIZED":
        pct = int(round((conf or 0.0) * 100))
        summary = f"✓ unified field: eye saw {_owner_name()} {int(face_age or 0)}s ago ({pct}%)"
    elif status == "UNKNOWN_USER_PRESENT":
        summary = f"✓ unified field: eye saw an unknown user {int(face_age or 0)}s ago"
    elif status == "CAMERA_HEALTHY_NO_FACE":
        summary = f"✓ unified field: camera healthy, no face in view {int(face_age or 0)}s ago"
    elif status == "CAMERA_HEALTHY_NO_FACE_PROOF":
        summary = "✓ unified field: camera frames fresh; no fresh face receipt"
    else:
        missing = disconnect_reasons or ["fresh proof"]
        summary = "✗ unified field: not proven; input disconnected/stale (" + ", ".join(missing[:4]) + ")"

    evidence = {
        "face": {
            "event": face.get("event"),
            "age_s": face_age,
            "faces_detected": faces_detected,
            "audience": audience,
            "confidence": conf,
        },
        "frame": {
            "event": frame.get("event"),
            "age_s": effective_frame_age,
            "saved_identity_frame_age_s": frame_age,
            "fresh": frame_fresh,
            "device": device,
            "w": frame.get("w"),
            "h": frame.get("h"),
            "sha8": sha8,
        },
        "visual": {
            "age_s": visual_age,
            "fresh": visual_fresh,
            "sha8": visual.get("sha8"),
            "motion_mean": visual.get("motion_mean"),
            "saliency_peak": visual.get("saliency_peak"),
            "has_frame_shape": visual_has_frame_shape,
        },
        "kernel": {
            "pid": vision_pid,
            "health": vision_health,
            "health_ok": vision_ok,
            "fresh": vision_fresh,
            "heartbeat_age_s": vision_hb_age_s,
        },
        "connection_state": connection_state,
        "disconnect_reasons": disconnect_reasons,
    }
    payload = {
        "truth_label": TRUTH_LABEL,
        "status": status,
        "ok": ok,
        "camera_healthy": camera_healthy,
        "recognition": recognition,
        "connection_state": connection_state,
        "disconnect_reasons": disconnect_reasons,
        "device": device,
        "frame_sha8": sha8,
        "ts": t,
        "evidence": evidence,
    }
    rid = _receipt_id(payload)
    proof = CameraUnifiedFieldProof(
        truth_label=TRUTH_LABEL,
        status=status,
        ok=ok,
        camera_healthy=camera_healthy,
        recognition=recognition,
        summary=summary,
        face_age_s=face_age,
        frame_age_s=effective_frame_age,
        visual_age_s=visual_age,
        vision_health=vision_health,
        vision_heartbeat_age_s=vision_hb_age_s,
        frame_fresh=frame_fresh,
        visual_fresh=visual_fresh,
        vision_fresh=vision_fresh,
        connection_state=connection_state,
        disconnect_reasons=disconnect_reasons,
        device=device,
        frame_sha8=sha8,
        face_confidence=conf,
        face_audience=audience,
        receipt_id=rid,
        ts=t,
        evidence=evidence,
    )
    if write_receipt:
        state.mkdir(parents=True, exist_ok=True)
        row = proof.to_dict()
        row["kind"] = "CAMERA_UNIFIED_FIELD_PROOF"
        with (state / "camera_unified_field_proof.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    return proof


def proof_text(state_dir: str | Path | None = None, *, stale_s: float = 300.0) -> str:
    """Small helper for labels and diagnostics."""
    return build_camera_unified_field_proof(state_dir, stale_s=stale_s).summary
