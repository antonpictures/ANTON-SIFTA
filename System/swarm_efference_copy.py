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
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.canonical_schemas import assert_payload_keys
from System.jsonl_file_lock import append_line_locked

_LEDGER = _REPO / ".sifta_state" / "efference_copy.jsonl"
_SCHEMA = "SIFTA_EFFERENCE_COPY_V1"


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
