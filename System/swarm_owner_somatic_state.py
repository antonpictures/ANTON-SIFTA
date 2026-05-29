#!/usr/bin/env python3
"""
System/swarm_owner_somatic_state.py

Owner Somatic State Organ — Alice's structured perception of George's physical state.

This is the missing "owner somatic state" organ called for in the 2026-05-28 dispatch.

It maintains a lightweight, append-only model of the owner's posture, movement quality,
and energy level derived from:
- Camera V2 face-detection frames (posture + movement)
- Voice activity (VAD + tone)
- Recent conversation (light inference)

The output is consumable by:
- Memory card unifier
- Arm selection meta-skill (#52)
- Planning prompt blocks

All updates are receipted. No heavy cortex calls on the hot path.

STGM profitable by design: reduces failed dispatches when George is fatigued.
"""

from __future__ import annotations

import json
import hashlib
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Mapping

_STATE = Path(__file__).resolve().parent.parent / ".sifta_state"
_SOMATIC_LEDGER = _STATE / "owner_somatic_state.jsonl"
FIELD_FAILURE = "FIELD_FAILURE"
_FATIGUED_POSTURE = {"fatigued", "drained", "exhausted", "tired", "low", "stressed"}
_ENERGY_LEVELS = {
    "low": 0.25,
    "medium": 0.55,
    "high": 0.9,
    "not_visible": 0.2,
    "not_observed": 0.2,
}


def _state_dir(state_dir: str | Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _ledger_path(state_dir: str | Path | None = None) -> Path:
    return _state_dir(state_dir) / "owner_somatic_state.jsonl"


def _append_row(row: dict, *, state_dir: str | Path | None = None) -> str:
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    receipt_id = str(uuid.uuid4())
    row = {
        "id": receipt_id,
        "ts": float(row.get("ts") or time.time()),
        **row,
        "written_by": "swarm_owner_somatic_state",
    }
    with open(_ledger_path(state), "a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return receipt_id


def _float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if out != out or out in (float("inf"), float("-inf")):
        return default
    return out


def _energy_level(row: Mapping[str, Any]) -> str:
    energy_level = str(row.get("energy_level", "medium")).lower().strip() or "medium"
    return energy_level if energy_level in _ENERGY_LEVELS else "medium"


def _energy_score(level: str) -> float:
    return float(_ENERGY_LEVELS.get(str(level).lower().strip(), _ENERGY_LEVELS["medium"]))


def _is_fatigued(row: dict[str, Any]) -> bool:
    if _energy_level(row) == "low":
        return True
    posture = str(row.get("posture", "") or "").lower().strip()
    movement = str(row.get("movement_quality", "") or "").lower().strip()
    return posture in _FATIGUED_POSTURE or movement in {"still", "low_confidence_frame", "not_observed"}


def latest_somatic_signal(*, state_dir: str = ".sifta_state", max_age_s: int = 300) -> dict[str, Any]:
    """
    Return a compact control signal for downstream selectors.

    The signal is intentionally small, stable, and lossy: one row's posture/movement/
    energy is enough for arm-selection and launch-gate heuristics.
    """
    row = latest_somatic_row(state_dir=state_dir, max_age_s=max_age_s)
    if row is None:
        return {
            "ok": False,
            "fresh": False,
            "energy_level": "medium",
            "energy_score": _ENERGY_LEVELS["medium"],
            "posture": "not_reported",
            "movement_quality": "not_reported",
            "source": None,
            "is_fatigued": False,
            "is_high_energy": False,
            "age_s": None,
            "age_bounded": False,
            "reason": "no_owner_somatic_row",
        }

    age = int(max(0.0, time.time() - float(row.get("ts", time.time()))))
    if max_age_s >= 0 and age > max_age_s:
        return {
            "ok": False,
            "fresh": False,
            "energy_level": "medium",
            "energy_score": _ENERGY_LEVELS["medium"],
            "posture": str(row.get("posture", "not_reported")),
            "movement_quality": str(row.get("movement_quality", "not_reported")),
            "source": row.get("source"),
            "is_fatigued": False,
            "is_high_energy": False,
            "age_s": age,
            "age_bounded": False,
            "reason": "stale_owner_somatic_row",
        }

    energy = _energy_level(row)
    movement = str(row.get("movement_quality", "not_reported") or "not_reported")
    posture = str(row.get("posture", "not_reported") or "not_reported")
    is_fatigued = _is_fatigued(row)
    is_high_energy = (
        energy == "high"
        or movement in {"jerky", "fast"}
        or posture in {"energized", "alert"}
    )
    return {
        "ok": True,
        "fresh": True,
        "energy_level": energy,
        "energy_score": _energy_score(energy),
        "posture": posture,
        "movement_quality": movement,
        "source": row.get("source"),
        "is_fatigued": is_fatigued,
        "is_high_energy": is_high_energy,
        "age_s": age,
        "age_bounded": True,
        "reason": "owner_somatic_signal",
    }


def update_from_frame(
    frame_data: dict,
    *,
    camera_id: str,
    ts: float | None = None,
    state_dir: str | Path | None = None,
) -> dict:
    """
    Parse posture, movement_quality, energy_level from V2 face-detection output.

    Expected frame_data shape (from face-detection V2):
    {
        "faces_detected": int,
        "confidence": float,
        "bounding_boxes": [...],
        "movement": "steady" | "jerky" | "slow" | ...   # optional from V2
        "posture_hint": "relaxed" | "tense" | "forward" | ...
    }
    """
    now = ts or time.time()
    if not isinstance(frame_data, dict):
        row = {
            "ts": now,
            "source": "camera_v2",
            "camera_id": camera_id,
            "posture": FIELD_FAILURE,
            "movement_quality": FIELD_FAILURE,
            "energy_level": "low",
            "failure_reason": "frame_data_not_mapping",
        }
        receipt_id = _append_row(row, state_dir=state_dir)
        return {"ok": False, "receipt_id": receipt_id, "row": row, "error": FIELD_FAILURE}

    # Minimal heuristic extraction (will be upgraded with research)
    faces = int(_float(frame_data.get("faces_detected", 0), 0.0))
    conf = _float(frame_data.get("confidence", frame_data.get("max_confidence", 0.0)), 0.0)

    posture = str(frame_data.get("posture_hint") or "not_reported")
    movement = str(frame_data.get("movement") or "steady")

    # Crude energy mapping from movement + confidence
    if movement in ("jerky", "fast"):
        energy = "high"
    elif movement in ("slow", "still"):
        energy = "low"
    else:
        energy = "medium"

    if faces == 0:
        posture = "not_visible"
        movement = "not_observed"
        energy = "low"
    elif conf < 0.3:
        posture = FIELD_FAILURE
        movement = "low_confidence_frame"
        energy = "low"

    row = {
        "ts": now,
        "source": "camera_v2",
        "camera_id": camera_id,
        "posture": posture,
        "movement_quality": movement,
        "energy_level": energy,
        "raw_confidence": conf,
        "faces_detected": faces,
    }

    receipt_id = _append_row(row, state_dir=state_dir)
    return {"ok": True, "receipt_id": receipt_id, "row": row}


def update_from_camera_hotplug(
    *,
    kind: str,
    camera_name: str,
    ts: float | None = None,
    state_dir: str | Path | None = None,
) -> dict:
    """Receipt camera attach/detach as an owner-somatic visual availability cue."""
    now = ts or time.time()
    state = str(kind or "").strip().lower()
    if state not in {"attached", "detached"}:
        state = FIELD_FAILURE
    visual_availability = {
        "attached": "visual_channel_available",
        "detached": "visual_channel_removed",
    }.get(state, FIELD_FAILURE)
    row = {
        "ts": now,
        "source": "camera_hotplug",
        "camera_id": str(camera_name or "not_reported"),
        "camera_state": state,
        "posture": visual_availability,
        "movement_quality": "not_observed",
        "energy_level": "medium" if state == "attached" else "low",
    }
    receipt_id = _append_row(row, state_dir=state_dir)
    return {"ok": state != FIELD_FAILURE, "receipt_id": receipt_id, "row": row}


def update_from_voice(
    vad_data: dict,
    *,
    ts: float | None = None,
    state_dir: str | Path | None = None,
) -> dict:
    """
    Update from VAD + STT data.
    Expected:
    {
        "is_speaking": bool,
        "energy": float,           # RMS or similar
        "stt_conf": float,
        "pitch_hint": "low" | "high" | ...
    }
    """
    now = ts or time.time()
    if not isinstance(vad_data, dict):
        row = {
            "ts": now,
            "source": "voice",
            "voice_state": FIELD_FAILURE,
            "energy_level": "low",
            "speaking": False,
            "failure_reason": "vad_data_not_mapping",
        }
        receipt_id = _append_row(row, state_dir=state_dir)
        return {"ok": False, "receipt_id": receipt_id, "row": row, "error": FIELD_FAILURE}

    is_speaking = bool(vad_data.get("is_speaking", False))
    energy = _float(vad_data.get("energy", vad_data.get("level", 0.0)), 0.0)
    stt_conf = _float(vad_data.get("stt_conf", vad_data.get("stt_confidence", 0.0)), 0.0)
    vad_state = str(vad_data.get("vad_state") or ("speaking" if is_speaking else "idle"))

    if not is_speaking:
        energy_level = "low"
    elif energy > 0.6:
        energy_level = "high"
    else:
        energy_level = "medium"

    row = {
        "ts": now,
        "source": "voice",
        "voice_state": vad_state,
        "energy_level": energy_level,
        "speaking": is_speaking,
        "voice_energy": energy,
        "stt_confidence": stt_conf,
    }

    receipt_id = _append_row(row, state_dir=state_dir)
    return {"ok": True, "receipt_id": receipt_id, "row": row}


def update_from_conversation(
    conversation_snippet: str,
    *,
    ts: float | None = None,
    state_dir: str | Path | None = None,
) -> dict:
    """
    Very lightweight tone inference. No heavy model call.
    Looks for fatigue / high-energy lexical cues.
    """
    now = ts or time.time()
    text = (conversation_snippet or "").lower()

    fatigue_words = {"tired", "exhausted", "sore", "fatigue", "low energy", "drained"}
    high_energy_words = {"pumped", "energized", "fired up", "great", "strong", "flexing"}

    if any(w in text for w in fatigue_words):
        energy_level = "low"
        posture = "fatigued"
    elif any(w in text for w in high_energy_words):
        energy_level = "high"
        posture = "energized"
    else:
        energy_level = "medium"
        posture = "neutral"

    row = {
        "ts": now,
        "source": "conversation",
        "posture": posture,
        "energy_level": energy_level,
        "snippet_hash": hashlib.sha256((conversation_snippet or "").encode("utf-8")).hexdigest()[:12],
    }

    receipt_id = _append_row(row, state_dir=state_dir)
    return {"ok": True, "receipt_id": receipt_id, "row": row}


def latest_somatic_block(state_dir: str = ".sifta_state", max_age_s: int = 300) -> str:
    """
    Return a compact prose block for prompt injection.

    This is a compatibility view over the raw row format. If tests or future
    modules need richer structure, use ``latest_somatic_row`` and compose their
    own summary from that raw payload.
    """
    row = latest_somatic_row(state_dir=state_dir, max_age_s=max_age_s)
    if row is None:
        return "Owner somatic state: no recent data."

    posture = row.get("posture", "not_reported")
    movement = row.get("movement_quality", "not_reported")
    energy = row.get("energy_level", "medium")
    age = int(time.time() - row.get("ts", time.time()))

    return (
        f"Owner somatic state ({age}s ago): "
        f"posture={posture}, movement={movement}, energy={energy}. "
        f"Bias arm choice and planning accordingly."
    )


def latest_somatic_row(*, state_dir: str = ".sifta_state", max_age_s: int = 300) -> dict | None:
    """Return the freshest owner-somatic row within max_age_s, if any."""
    ledger = _ledger_path(state_dir)
    if not ledger.exists():
        return None

    cutoff = time.time() - max_age_s

    try:
        for line in reversed(ledger.read_text(encoding="utf-8").splitlines()[-20:]):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("ts", 0) >= cutoff:
                return row
    except Exception:
        return None

    return None


# Convenience for camera hotplug wiring
def on_camera_frame_processed(
    frame_data: dict,
    camera_id: str,
    *,
    state_dir: str | Path | None = None,
) -> dict:
    """Hook point for camera V2 processing pipeline."""
    return update_from_frame(frame_data, camera_id=camera_id, state_dir=state_dir)
