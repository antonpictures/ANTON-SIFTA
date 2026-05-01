#!/usr/bin/env python3
"""
Biology-derived plasticity organ — slow adaptation of internal drive weights.

Maps consciousness domains → plastic keys, homeostatic decay toward baselines,
Hebbian-style reinforcement from body_brain TD value, and danger/circadian priors.

Truth: OPERATIONAL toy dynamics — not a verified neuro model.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

STATE_PATH = _REPO / ".sifta_state" / "biology_drive_plasticity.json"

BASELINE_DRIVES: Dict[str, float] = {
    "curiosity": 0.35,
    "repair": 0.25,
    "rest": 0.20,
    "protect": 0.20,
    "explore": 0.30,
}

# ConsciousnessEngine domains → plastic keys (repair/protect absorb metabolic/safety).
_DOMAIN_TO_PLASTIC: Dict[str, str] = {
    "energy": "repair",
    "safety": "protect",
}


def attention_to_plastic_drive(attention: str) -> str:
    """Map body_brain attention / dominant_drive string to a plasticity key."""
    key = str(attention or "").strip().lower()
    if key in BASELINE_DRIVES:
        return key
    return _DOMAIN_TO_PLASTIC.get(key, "explore")


def plasticity_danger_token(
    metabolic_mode: str,
    now_state: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Optional danger label consumed by update_drive_plasticity.

    CIRCADIAN_SLEEP_PRESSURE is emitted on coarse night phase (hour heuristic only).
    """
    mode = str(metabolic_mode or "")
    if mode == "RED_CONSERVE":
        return "RED_CONSERVE"
    circ = (now_state or {}).get("circadian") if isinstance(now_state, dict) else None
    if isinstance(circ, dict) and circ.get("phase") == "night":
        return "CIRCADIAN_SLEEP_PRESSURE"
    return None


def _load_state() -> Dict[str, float]:
    if not STATE_PATH.exists():
        return dict(BASELINE_DRIVES)
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return dict(BASELINE_DRIVES)
    out: Dict[str, float] = {}
    for key in BASELINE_DRIVES:
        out[key] = float(data.get(key, BASELINE_DRIVES[key]))
    return out


def _save_state(state: Dict[str, float]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


def update_drive_plasticity(
    active_drive: str,
    value: float,
    danger_state: Optional[str] = None,
    learning_rate: float = 0.08,
    decay_rate: float = 0.02,
) -> Dict[str, Any]:
    """
    Update drive weights after a body_brain_tick.

    value: signed outcome (e.g. TD-style value from the loop).
    danger_state: RED_CONSERVE or CIRCADIAN_SLEEP_PRESSURE bias rest/repair.
    """
    state = _load_state()

    for drive, baseline in BASELINE_DRIVES.items():
        state[drive] += decay_rate * (baseline - state[drive])

    drive_key = attention_to_plastic_drive(active_drive)
    if drive_key in state:
        state[drive_key] += learning_rate * float(value)

    if danger_state in {"RED_CONSERVE", "CIRCADIAN_SLEEP_PRESSURE"}:
        state["rest"] = clamp(state["rest"] + 0.10)
        state["repair"] = clamp(state["repair"] + 0.06)
        state["explore"] = clamp(state["explore"] - 0.08)
        state["curiosity"] = clamp(state["curiosity"] - 0.04)

    state = {k: clamp(v) for k, v in state.items()}
    _save_state(state)

    return {
        "ts": time.time(),
        "active_drive": drive_key,
        "raw_attention": active_drive,
        "value": float(value),
        "danger_state": danger_state,
        "drive_weights": state,
    }


def bias_drives(raw_drives: Dict[str, float]) -> Dict[str, float]:
    """Scale raw drive scores by learned plasticity weights (keys intersect BASELINE)."""
    weights = _load_state()
    biased: Dict[str, float] = {}
    for drive, score in raw_drives.items():
        w = weights.get(drive, 0.25)
        biased[drive] = clamp(float(score) * (0.5 + w))
    return biased
