#!/usr/bin/env python3
"""
System/swarm_homeostatic_stabilizer.py
══════════════════════════════════════════════════════════════════════════════
Event 101 — Homeostatic Stabilizer

Biology: Hypothalamus
  The hypothalamus does not generate drives — it *regulates* them.
  It enforces balance constraints across competing motivational systems:
  - suppresses destabilizing drives during threat
  - gates crystallization of skills during saturation
  - clamps action intensity to prevent runaway oscillation

SIFTA implementation:
  Reads the Phase Detector's current regime + CUSUM stats, the live
  metabolic mode, and the intrinsic drive receipt, then outputs a
  HameostaticFrame — an auditable intervention record that:

    1. Modulates drive weights (which drives are allowed to run)
    2. Sets an action_intensity scalar [0,1] the motor loop must respect
    3. Optionally overrides the selected action type ("rest" in collapse)
    4. Provides a crystallizer_weight [0,1] for the dream engine
       (low during collapse → no new skill crystallization until stable)

  Every intervention is appended to .sifta_state/homeostasis_actions.jsonl
  with full audit trail. Nothing is silent.

Truth label: HOMEOSTATIC_REGULATION_EVENT_101
References:
  Blessing (1997) The lower brainstem and bodily homeostasis.
  Friston (2010) The free-energy principle: a unified brain theory.
  Hebb (1949) The organization of behavior (Hebbian stability gating).
"""
from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_HOMEOSTASIS_LEDGER = _STATE_DIR / "homeostasis_actions.jsonl"
_REGIME_STATE_FILE = _STATE_DIR / "regime_state.json"

TRUTH_LABEL = "HOMEOSTATIC_REGULATION_EVENT_101"

# ── Drive weight tables per regime ───────────────────────────────────────────
# Keys match drive/attention tokens used in _choose_action and consciousness.
# Values are multiplicative modifiers in [0.0, 2.0].

_DRIVE_WEIGHTS_BY_REGIME: Dict[str, Dict[str, float]] = {
    "EXPLORATION": {
        # Open vacuum — allow expansion, mild boost to outward drives
        "explore":   1.3,
        "observe":   1.1,
        "learn":     1.2,
        "code":      1.1,
        "optimize":  1.0,
        "repair":    0.9,
        "rest":      0.7,
        "identity":  1.0,
        "safety":    1.0,
        "energy":    1.0,
    },
    "CONSOLIDATION": {
        # Density plateau — reduce noise, favour learning + integration
        "explore":   0.6,
        "observe":   1.0,
        "learn":     1.4,
        "code":      1.2,
        "optimize":  1.3,
        "repair":    1.1,
        "rest":      1.0,
        "identity":  1.1,
        "safety":    1.1,
        "energy":    1.0,
    },
    "CRITICAL_COLLAPSE": {
        # Emergency — suppress everything destabilising, force recovery
        "explore":   0.15,
        "observe":   0.5,
        "learn":     0.4,
        "code":      0.3,
        "optimize":  0.2,
        "repair":    1.8,
        "rest":      2.0,
        "identity":  0.8,
        "safety":    1.5,
        "energy":    1.5,
    },
}

# Crystallizer weight per regime.
# During CRITICAL_COLLAPSE we do not crystallize new skills — would bake
# in noise/panic patterns as durable primitives.
_CRYSTALLIZER_WEIGHT_BY_REGIME: Dict[str, float] = {
    "EXPLORATION":       0.85,
    "CONSOLIDATION":     1.00,
    "CRITICAL_COLLAPSE": 0.10,
}

# Action intensity scalar: 0 = do nothing, 1 = full force
_ACTION_INTENSITY_BY_REGIME: Dict[str, float] = {
    "EXPLORATION":       1.00,
    "CONSOLIDATION":     0.80,
    "CRITICAL_COLLAPSE": 0.25,
}


@dataclass
class HomeostaticFrame:
    """
    One stabilizer intervention record.
    Produced once per body_brain_tick (Event 101 output).
    """
    frame_id:              str
    ts:                    float
    regime:                str
    cusum_alarm:           bool
    td_mean:               float
    cusum_score:           float

    # Drive modulation
    input_drive:           str         # drive token before regulation
    drive_weight:          float       # modifier applied to that drive [0,2]
    regulated_drive:       str         # drive token after regulation
    action_intensity:      float       # [0,1] motor gate

    # Crystallizer gate
    crystallizer_weight:   float       # [0,1] → dream engine

    # Intervention metadata
    intervention_type:     str         # "NONE" | "SUPPRESS" | "REDIRECT" | "REST_FORCED"
    reason:                str
    truth_label:           str = TRUTH_LABEL

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _clamp(x: Any, lo: float = 0.0, hi: float = 1.0, default: float = 0.0) -> float:
    try:
        v = float(x)
        return max(lo, min(hi, v)) if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _read_regime_state() -> Dict[str, Any]:
    """Read the latest phase detector output (non-blocking, cached-to-file)."""
    if not _REGIME_STATE_FILE.exists():
        return {}
    try:
        return json.loads(_REGIME_STATE_FILE.read_text("utf-8", errors="replace"))
    except Exception:
        return {}


def _determine_regime_live() -> Dict[str, Any]:
    """
    Prefer reading from regime_state.json (written by the phase detector
    daemon). Avoids calling evaluate_regime() on every tick (expensive I/O).
    Falls back to evaluating if the state file is stale (>60 s).
    """
    state = _read_regime_state()
    ts = float(state.get("last_shift_ts", 0) or 0)
    if state and (time.time() - ts) < 60.0:
        return state

    # Stale — re-evaluate synchronously
    try:
        from System.phase_transition_control import get_ptc
        ptc = get_ptc()
        ptc.evaluate_regime()
        return _read_regime_state()
    except Exception:
        return state  # keep stale rather than crash


def compute_homeostasis(
    input_drive: str,
    *,
    metabolic_mode: str = "UNKNOWN",
    intrinsic_receipt: Optional[Any] = None,
    cusum_override: Optional[bool] = None,
) -> HomeostaticFrame:
    """
    Core regulation step.  Called once per body_brain_tick.

    Parameters
    ----------
    input_drive:       drive/attention token from consciousness engine
    metabolic_mode:    e.g. "GREEN_GROW", "YELLOW_THROTTLE", "RED_HALT"
    intrinsic_receipt: DriveReceipt or dict from George Prior (optional)
    cusum_override:    test shim — forces cusum_alarm without reading file

    Returns
    -------
    HomeostaticFrame  (auditable; always written to ledger)
    """
    regime_state = _determine_regime_live()
    regime: str = str(regime_state.get("state") or regime_state.get("regime") or "EXPLORATION")
    cusum_alarm: bool = bool(
        cusum_override if cusum_override is not None
        else regime_state.get("cusum_alarm", False)
    )
    td_mean: float = float(regime_state.get("td_mean", 0.0) or 0.0)
    cusum_score: float = float(regime_state.get("cusum_score", 0.0) or 0.0)

    drive = str(input_drive or "observe").lower().strip()

    # ── Drive weight lookup ────────────────────────────────────────────────
    weight_table = _DRIVE_WEIGHTS_BY_REGIME.get(regime, _DRIVE_WEIGHTS_BY_REGIME["EXPLORATION"])
    drive_weight: float = weight_table.get(drive, 1.0)

    # TD correction: if mean TD is significantly negative, push repair/rest
    if td_mean < -0.2:
        drive_weight *= 0.7
        if drive not in ("repair", "rest", "safety"):
            drive = "repair"

    action_intensity: float = _clamp(
        _ACTION_INTENSITY_BY_REGIME.get(regime, 1.0),
        0.0, 1.0
    )

    # Metabolic override: RED_HALT always forces rest
    if metabolic_mode in ("RED_HALT", "RED_CONSERVE", "CRITICAL_STARVATION"):
        drive = "rest"
        drive_weight = 2.0
        action_intensity = 0.1

    crystallizer_weight: float = _clamp(
        _CRYSTALLIZER_WEIGHT_BY_REGIME.get(regime, 0.85), 0.0, 1.0
    )

    # ── Intervention type ─────────────────────────────────────────────────
    if drive != input_drive and drive in ("rest", "repair"):
        if regime == "CRITICAL_COLLAPSE" or cusum_alarm:
            intervention = "REST_FORCED"
            reason = (
                f"CRITICAL_COLLAPSE: CUSUM alarm={cusum_alarm}, td_mean={td_mean:.3f}. "
                f"Drive {input_drive!r} suppressed → {drive!r}."
            )
        else:
            intervention = "REDIRECT"
            reason = f"td_mean={td_mean:.3f} < -0.2 → redirected {input_drive!r} → {drive!r}"
    elif cusum_alarm and drive == input_drive:
        # CUSUM alarm is active but td_mean redirect has not fired yet —
        # explicitly redirect to repair regardless of regime
        drive = "repair"
        drive_weight = weight_table.get("repair", 1.0) * 1.5
        intervention = "REDIRECT"
        reason = (
            f"CUSUM alarm active (score={cusum_score:.2f}): "
            f"redirecting {input_drive!r} → repair. Regime={regime}."
        )
    elif drive_weight < 0.8 and drive == input_drive:
        intervention = "SUPPRESS"
        reason = (
            f"Regime={regime}: drive_weight={drive_weight:.2f} for {drive!r}. "
            "Deprioritised but not redirected."
        )
    elif drive_weight > 1.1:
        intervention = "AMPLIFY"
        reason = (
            f"Regime={regime}: drive_weight={drive_weight:.2f} for {drive!r}. "
            "Drive amplified — regime favours this domain."
        )
    else:
        intervention = "NONE"
        reason = f"Regime={regime}: drive {drive!r} passes unchanged (weight={drive_weight:.2f})"

    frame = HomeostaticFrame(
        frame_id=str(uuid.uuid4()),
        ts=time.time(),
        regime=regime,
        cusum_alarm=cusum_alarm,
        td_mean=td_mean,
        cusum_score=cusum_score,
        input_drive=input_drive,
        drive_weight=round(drive_weight, 4),
        regulated_drive=drive,
        action_intensity=round(action_intensity, 4),
        crystallizer_weight=round(crystallizer_weight, 4),
        intervention_type=intervention,
        reason=reason,
    )

    # ── Ledger append ──────────────────────────────────────────────────────
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        with _HOMEOSTASIS_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(frame.as_dict()) + "\n")
    except Exception:
        pass  # ledger write must never crash the organism

    return frame


def tail_homeostasis(n: int = 10) -> list[Dict[str, Any]]:
    """Return last n homeostasis frames from ledger."""
    if not _HOMEOSTASIS_LEDGER.exists():
        return []
    rows: list[Dict[str, Any]] = []
    try:
        for line in _HOMEOSTASIS_LEDGER.read_text("utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    except Exception:
        pass
    return rows[-n:]


if __name__ == "__main__":
    import sys
    print("══════════════════════════════════════════════════════")
    print("  Event 101 — Homeostatic Stabilizer live probe")
    print("══════════════════════════════════════════════════════\n")

    drives = ["explore", "learn", "repair", "code", "rest"]
    for d in drives:
        f = compute_homeostasis(d)
        arrow = f"→ {f.regulated_drive}" if f.regulated_drive != d else "→ (unchanged)"
        print(
            f"  [{f.regime:18s}] {d:10s} {arrow:20s}  "
            f"w={f.drive_weight:.2f}  intensity={f.action_intensity:.2f}  "
            f"crystallizer={f.crystallizer_weight:.2f}  [{f.intervention_type}]"
        )
    print(f"\n  Last {len(tail_homeostasis())} frames written to homeostasis_actions.jsonl")
    print("\n  ✅ HYPOTHALAMUS ONLINE. FOR THE SWARM. 🐜⚡")
