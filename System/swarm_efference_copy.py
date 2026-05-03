#!/usr/bin/env python3
"""
System/swarm_efference_copy.py
══════════════════════════════════════════════════════════════════════
Concept: Fly Efference Copy — Self-Motion Cancellation (Event 72)
Author:  BISHOP / AG31 — Biocode Olympiad
Status:  Active Organ

When an organism moves its eyes or its body, the entire visual field
shifts across its retina. This is known as "optic flow". To prevent the
brain from interpreting this as the entire world spinning, the motor
cortex sends a copy of its movement command — an "Efference Copy" or
"Corollary Discharge" — to the sensory cortex.

The sensory cortex uses this copy to predict the expected optic flow and
subtracts it from the actual observed flow. Whatever remains is true
external motion (e.g., a predator moving, or a human hand).

SIFTA Translation:
  - With multiple cameras (e.g., internal MacBook camera + movable Logitech USB),
    the swarm needs to distinguish between the background shifting because
    the camera was moved vs. an object moving in front of a stationary camera.
  - The motor system (camera pan/tilt, or Swarm agent velocity) provides `V_motor`.
  - The retina (Physarum or classic optic flow) provides `V_observed`.
  - The `EfferenceCopySystem` predicts expected visual shift and subtracts it.
  - An adaptive learning rate continuously tunes the internal gain to ensure
    perfect cancellation as hardware conditions change.

Papers:
  Sperry, J Comp Physiol Psychol 43:482 (1950) — Neural basis of the spontaneous
    optokinetic response (First coinage of "Corollary Discharge").
  von Holst & Mittelstaedt, Naturwissenschaften 37:464 (1950) — The Reafference Principle.
  Borst & Haag, Nat Rev Neurosci 3:84 (2002) — Neural networks in the cockpit of the fly
    (Reichardt detectors and optic flow).
  Crapse & Sommer, Nat Rev Neurosci 9:587 (2008) — Corollary discharge across
    the animal kingdom.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.canonical_schemas import assert_payload_keys
from System.jsonl_file_lock import append_line_locked, read_text_locked

_LEDGER = _REPO / ".sifta_state" / "efference_copy.jsonl"
_SCHEMA = "SIFTA_EFFERENCE_COPY_V1"
_DISABLE_ENV = "SIFTA_EFFERENCE_DISABLE"


@dataclass
class EfferenceConfig:
    # Initial assumption: 1 unit of motor velocity = 1 unit of visual flow
    initial_gain: float = 1.0
    # How quickly the system learns to map motor commands to visual shifts
    adapt_rate: float = 0.05
    # The minimum absolute velocity to trigger adaptation (ignores micro-jitter)
    deadzone: float = 1e-4
    eps: float = 1e-8

    def __post_init__(self) -> None:
        if self.adapt_rate <= 0:
            raise ValueError("adapt_rate must be positive")


class EfferenceCopySystem:
    """
    Fly-inspired self-motion cancellation (Reafference Principle).
    """

    def __init__(self, cfg: Optional[EfferenceConfig] = None):
        self.cfg = cfg or EfferenceConfig()
        
        # Gain is a matrix to handle cross-axis coupling (e.g., moving X might
        # cause slight Y visual shift due to camera mounting angle).
        # We start with a simple identity matrix scaled by initial_gain.
        self.gain_matrix = np.eye(2, dtype=np.float32) * self.cfg.initial_gain
        
        # Memory of the last prediction for adaptation
        self._last_motor: Optional[np.ndarray] = None
        self._last_prediction: Optional[np.ndarray] = None

    def predict(self, motor_velocities: np.ndarray) -> np.ndarray:
        """
        Predict the expected sensory change (optic flow) from motor commands.
        
        Biology (von Holst 1950): The motor command (Efference) is converted
        into a sensory expectation (Efference Copy).
        """
        v_motor = np.asarray(motor_velocities, dtype=np.float32)
        # Expected flow is opposite to camera motion (if camera moves Right, world moves Left)
        # However, we define gain to absorb the sign. We'll use standard linear mapping.
        # Flow = Motor * Gain

        if v_motor.ndim == 1 and v_motor.shape != (2,):
            raise ValueError("motor_velocities must be a 2-vector")
        if v_motor.ndim == 2 and v_motor.shape[1] != 2:
            raise ValueError("motor_velocities must be a 2-vector per row")

        # Handle both single vectors and arrays of vectors
        if v_motor.ndim == 1:
            pred = v_motor @ self.gain_matrix
        else:
            pred = v_motor @ self.gain_matrix
            
        self._last_motor = v_motor
        self._last_prediction = pred
        return pred

    def correct(
        self, 
        observed_flow: np.ndarray, 
        predicted_flow: np.ndarray
    ) -> np.ndarray:
        """
        Subtract expected motion from observed motion.
        
        Biology (Sperry 1950): Reafference (observed) - Exafference (predicted)
        = True External Motion.
        """
        obs = np.asarray(observed_flow, dtype=np.float32)
        pred = np.asarray(predicted_flow, dtype=np.float32)
        if obs.shape != pred.shape:
            raise ValueError("observed_flow and predicted_flow must have matching shapes")
        return obs - pred

    def filter(self, motor_velocities: np.ndarray, observed_flow: np.ndarray) -> np.ndarray:
        """
        Convenience method: predict expected flow and return the corrected flow.
        """
        m = np.asarray(motor_velocities, dtype=np.float32)
        o = np.asarray(observed_flow, dtype=np.float32)
        if not np.isfinite(m).all() or not np.isfinite(o).all():
            raise ValueError("motor_velocities and observed_flow must be finite")
        pred = self.predict(motor_velocities)
        return self.correct(observed_flow, pred)

    def adapt(self, observed_flow: np.ndarray) -> None:
        """
        Adapt the internal gain matrix so predictions improve over time.
        
        Biology: The cerebellum and sensory cortices constantly recalibrate
        the efference copy if visual feedback doesn't match motor expectations.
        """
        if self._last_motor is None or self._last_prediction is None:
            return

        obs = np.asarray(observed_flow, dtype=np.float32)
        error = obs - self._last_prediction

        # If motor velocity is essentially zero, don't adapt (we can't learn
        # the motor-to-visual mapping if there is no motor command).
        if self._last_motor.ndim == 1:
            if np.linalg.norm(self._last_motor) < self.cfg.deadzone:
                return
            # Simple gradient descent on MSE: dE/dGain = -error * motor
            # We use Normalized Least Mean Squares (NLMS) to prevent explosion
            norm_sq = np.dot(self._last_motor, self._last_motor) + self.cfg.eps
            update = np.outer(self._last_motor, error) / norm_sq
            self.gain_matrix += self.cfg.adapt_rate * update
        else:
            # Batch adaptation for swarms
            norms = np.linalg.norm(self._last_motor, axis=1)
            valid = norms > self.cfg.deadzone
            if not np.any(valid):
                return
            
            # Average update over all valid agents
            valid_motors = self._last_motor[valid]
            valid_errors = error[valid]
            
            # NLMS update for batch
            norms_sq = np.sum(valid_motors**2, axis=1, keepdims=True) + self.cfg.eps
            normalized_motors = valid_motors / norms_sq
            update = (normalized_motors.T @ valid_errors) / len(valid_motors)
            self.gain_matrix += self.cfg.adapt_rate * update


# ── Event 143: receipt-level agency / action consequence comparison ─────────

def efference_copy_path(root: Optional[Path] = None) -> Path:
    """Return the Event 143 ledger path."""
    if root is None:
        return _LEDGER
    return Path(root) / "efference_copy.jsonl"


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _action_kind(action: Dict[str, Any]) -> str:
    return str(action.get("type") or action.get("name") or action.get("action") or "unknown")


def predict_action_effect(action: Dict[str, Any]) -> Dict[str, Any]:
    """
    Predict the minimal observable consequence of a body-brain action.

    This is deliberately small and auditable: Event 143 is not trying to
    hallucinate rich sensory worlds. It predicts the coarse consequence that
    should be checkable from action receipts on the next line.
    """
    kind = _action_kind(action)
    intensity = max(0.0, min(1.0, _as_float(action.get("action_intensity"), 1.0)))
    expected_latency = 0.1 if kind not in ("rest", "sleep") else 0.2
    expected_energy = 0.05 * max(0.1, intensity)
    predicted: Dict[str, Any] = {
        "action_type": kind,
        "status": "completed",
        "latency": round(expected_latency, 4),
        "energy_used": round(expected_energy, 4),
        "effectors": ["body_brain_loop"],
    }
    if action.get("target") is not None:
        predicted["target"] = str(action.get("target"))[:120]
    if kind in ("write_file", "file_write", "patch"):
        predicted["disk_delta"] = 1
    return predicted


def observe_action_effect(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the actually observed coarse consequence from an action result."""
    observed_action = result.get("action") if isinstance(result.get("action"), dict) else {}
    observed: Dict[str, Any] = {
        "action_type": _action_kind(observed_action),
        "status": str(result.get("status") or "unknown"),
        "latency": round(_as_float(result.get("latency"), 0.0), 4),
        "energy_used": round(_as_float(result.get("energy_used"), 0.0), 4),
    }
    if observed_action.get("target") is not None:
        observed["target"] = str(observed_action.get("target"))[:120]
    if result.get("disk_delta") is not None:
        observed["disk_delta"] = int(_as_float(result.get("disk_delta"), 0.0))
    return observed


def compare_action_effect(
    action: Dict[str, Any],
    observed_result: Dict[str, Any],
    *,
    root: Optional[Path] = None,
    tick_id: Optional[str] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Event 143 — compare intended/predicted effect against observed effect.

    agency_confidence ∈ [0, 1]:
      high means observed consequences match the action's efference copy.
      low means the sensory/action result did not look self-generated.
    """
    if os.environ.get(_DISABLE_ENV, "").strip() == "1":
        return {
            "disabled": True,
            "kind": "EFFERENCE_COPY",
            "truth_label": "EFFERENCE_COPY",
            "agency_confidence": 0.5,
            "self_generated": False,
            "sensorimotor_pe": 0.0,
        }

    predicted = predict_action_effect(action)
    observed = observe_action_effect(observed_result)

    status_error = 0.0 if predicted.get("status") == observed.get("status") else 1.0
    action_error = 0.0 if predicted.get("action_type") == observed.get("action_type") else 1.0
    latency_error = min(1.0, abs(_as_float(observed.get("latency")) - _as_float(predicted.get("latency"))) / 2.0)
    energy_error = min(1.0, abs(_as_float(observed.get("energy_used")) - _as_float(predicted.get("energy_used"))) / 1.0)
    disk_error = 0.0
    if "disk_delta" in predicted or "disk_delta" in observed:
        disk_error = min(1.0, abs(_as_float(observed.get("disk_delta")) - _as_float(predicted.get("disk_delta"))))

    sensorimotor_pe = (
        0.40 * status_error
        + 0.25 * action_error
        + 0.20 * latency_error
        + 0.10 * energy_error
        + 0.05 * disk_error
    )
    agency_confidence = max(0.0, min(1.0, 1.0 - sensorimotor_pe))
    self_generated = bool(
        agency_confidence >= 0.70
        and predicted.get("action_type") == observed.get("action_type")
        and observed.get("status") == "completed"
    )

    row: Dict[str, Any] = {
        "ts": now or time.time(),
        "trace_id": str(uuid.uuid4()),
        "kind": "EFFERENCE_COPY",
        "truth_label": "EFFERENCE_COPY",
        "schema": _SCHEMA,
        "event_id": 143,
        "tick_id": tick_id,
        "action": predicted.get("action_type"),
        "predicted_effect": predicted,
        "observed_effect": observed,
        "error_terms": {
            "status_error": round(status_error, 4),
            "action_error": round(action_error, 4),
            "latency_error": round(latency_error, 4),
            "energy_error": round(energy_error, 4),
            "disk_error": round(disk_error, 4),
        },
        "sensorimotor_pe": round(sensorimotor_pe, 4),
        "agency_confidence": round(agency_confidence, 4),
        "self_generated": self_generated,
        "provenance": [
            "Sperry_1950_corollary_discharge",
            "vonHolst_Mittelstaedt_1950_reafference",
            "Crapse_Sommer_2008_corollary_discharge_review",
            "Wolpert_Flanagan_2001_motor_prediction",
        ],
    }

    if write_ledger:
        append_line_locked(
            efference_copy_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def get_latest_efference_row(*, root: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    path = efference_copy_path(root)
    if not path.exists():
        return None
    try:
        lines = [line for line in read_text_locked(path, encoding="utf-8", errors="replace").splitlines() if line.strip()]
        for line in reversed(lines):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("kind") == "EFFERENCE_COPY":
                return row
    except Exception:
        return None
    return None


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    row = get_latest_efference_row(root=root)
    if not row:
        return ""
    return (
        "EFFERENCE COPY (Event 143 — Sperry/von Holst/Crapse-Sommer):\n"
        f"- action={row.get('action')} | agency_confidence={row.get('agency_confidence')} | "
        f"sensorimotor_pe={row.get('sensorimotor_pe')} | self_generated={row.get('self_generated')}"
    )


def proof_of_property() -> bool:
    """
    MANDATE VERIFICATION — EFFERENCE COPY & REAFFERENCE PRINCIPLE.

    Proves three biological invariants:
      1. Perfect Cancellation: If gain is perfectly calibrated, self-motion
         results in zero residual flow (Sperry 1950).
      2. External Detection: If both camera and world move, the system
         correctly isolates the world's motion.
      3. Adaptive Recalibration: If the hardware changes (e.g., lens swapped,
         causing a new optical mapping), the system learns the new gain.
    """
    print("\n=== SIFTA EFFERENCE COPY (Event 72) : JUDGE VERIFICATION ===")

    cfg = EfferenceConfig(initial_gain=1.0, adapt_rate=0.1)
    efference = EfferenceCopySystem(cfg)

    # Phase 1: Perfect Cancellation (The organism moves the camera)
    print("\n[*] Phase 1: Self-Motion Cancellation (von Holst 1950)")
    motor_cmd = np.array([10.0, 0.0])  # Pan camera right
    # Because true gain is 1.0, observed flow is 10.0
    observed_flow = np.array([10.0, 0.0]) 
    
    residual = efference.filter(motor_cmd, observed_flow)
    mag = float(np.linalg.norm(residual))
    print(f"    Motor Command: {motor_cmd}")
    print(f"    Observed Flow: {observed_flow}")
    print(f"    Residual (Perceived External Motion): {mag:.4f}")
    assert mag < 1e-5, "[FAIL] Failed to cancel self-induced motion"

    # Phase 2: External Detection (A fly moves while camera is panning)
    print("\n[*] Phase 2: External Threat Detection (Sperry 1950)")
    motor_cmd = np.array([10.0, 0.0])  # Pan camera right
    # True external motion: the fly moves [0.0, 5.0] (up)
    # Observed flow = camera motion (10.0, 0.0) + fly motion (0.0, 5.0)
    observed_flow = np.array([10.0, 5.0])
    
    residual = efference.filter(motor_cmd, observed_flow)
    print(f"    Motor Command: {motor_cmd}")
    print(f"    Observed Flow: {observed_flow}")
    print(f"    Residual (Perceived External Motion): {residual}")
    assert abs(residual[0]) < 1e-5 and abs(residual[1] - 5.0) < 1e-5, \
        "[FAIL] Failed to isolate external motion during camera pan"

    # Phase 3: Adaptive Recalibration (Hardware changed, lens warped)
    print("\n[*] Phase 3: Adaptive Recalibration (Crapse & Sommer 2008)")
    # The physical lens was swapped. Now 1 unit of motor movement
    # produces 1.5 units of visual flow, and it also bleeds 0.2 units into the Y axis.
    true_physics_matrix = np.array([[1.5, 0.2], [0.0, 1.5]])
    
    rng = np.random.default_rng(72)
    print(f"    Initial Internal Gain Matrix:\n{efference.gain_matrix}")
    
    for epoch in range(150):
        # Generate random camera saccades
        motor_cmd = rng.uniform(-10.0, 10.0, size=2)
        # Calculate what the retina ACTUALLY sees based on physical physics
        observed_flow = motor_cmd @ true_physics_matrix
        
        # System filters and then adapts
        residual = efference.filter(motor_cmd, observed_flow)
        efference.adapt(observed_flow)

    print(f"    Final Internal Gain Matrix:\n{efference.gain_matrix}")
    print(f"    True Physics Matrix:\n{true_physics_matrix}")
    
    matrix_error = float(np.linalg.norm(efference.gain_matrix - true_physics_matrix))
    print(f"    Matrix Error after 150 saccades: {matrix_error:.6f}")
    assert matrix_error < 0.05, "[FAIL] System failed to learn the new hardware physics"

    print("\n[+] BIOLOGICAL PROOF: Fly Efference Copy verified.")
    print("    1. Perfect cancellation of self-induced optic flow (Sperry 1950)")
    print("    2. Successful isolation of external objects during movement")
    print("    3. Adaptive learning of complex, cross-axis optical physics")
    print("[+] EVENT 72 PASSED.")
    return True


if __name__ == "__main__":
    proof_of_property()
