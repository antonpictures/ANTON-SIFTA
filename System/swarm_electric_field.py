#!/usr/bin/env python3
"""
System/swarm_electric_field.py
══════════════════════════════════════════════════════════════════════
Concept: Weakly Electric Fish — Field Communication & Identity (Event 69)
Author:  BISHOP / AG31 — Biocode Olympiad
Status:  Active Organ

Weakly electric fish (Eigenmannia virescens, Apteronotus leptorhynchus)
generate a weak oscillating electric field via their Electric Organ
Discharge (EOD). Each individual has a UNIQUE frequency — this is their
identity signature. They sense distortions in their own field to detect
objects (electrolocation) and shift their frequency to avoid jamming
when another fish emits a similar frequency (Jamming Avoidance Response).

SIFTA Translation:
  - Each agent emits a complex-valued signal at its unique PHASE (identity).
  - The signal propagates through the shared field via diffusion.
  - Agents sense the local field to detect other agents without vision.
  - When two agents have similar phases (frequency collision), the
    Jamming Avoidance Response forces them apart in phase space.
  - The result: agents self-organize into non-overlapping communication
    channels, enabling robust identity signaling without substrate overwrite.

Papers:
  Heiligenberg, "Neural Nets in Electric Fish", MIT Press (1991)
    — Jamming Avoidance Response neural computation
  Hopkins, Annu Rev Neurosci 11:497 (1988)
    — Neuroethology of electric communication
  Watanabe & Takeda, J Exp Biol 40:57 (1963)
    — Discovery of the Jamming Avoidance Response
  Bullock, Hopkins, Popper & Fay, "Electroreception", Springer (2005)
    — Comprehensive review of electrosensory systems
  Carlson & Kawasaki, J Exp Biol 210:1041 (2007)
    — Electrosensory processing and frequency discrimination
  Fortune, Trends Neurosci 29:361 (2006)
    — Computational models of electrosensory processing
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.canonical_schemas import assert_payload_keys
from System.jsonl_file_lock import append_line_locked

_LEDGER = _REPO / ".sifta_state" / "electric_field_identity.jsonl"
_SCHEMA = "SIFTA_ELECTRIC_FIELD_V1"


@dataclass
class ElectricFieldConfig:
    grid_size: int = 64
    decay: float = 0.94           # field decay (electric field dissipation)
    diffusion: float = 0.06       # lateral spread of the electric field
    emit_strength: float = 1.0    # EOD amplitude
    sense_gain: float = 0.5       # amplification of sensed signal
    jamming_penalty: float = 0.6  # penalty for phase collision (JAR strength)
    jar_shift_rate: float = 0.08  # how fast agents shift phase to avoid jamming
    identity_threshold: float = 0.3  # phase difference below this = "same identity"
    eps: float = 1e-8


class ElectricAgent:
    """
    One weakly electric fish agent.
    Biology (Hopkins 1988): Each individual's EOD has a unique
    frequency that serves as an identity marker for species and
    individual recognition.
    """

    def __init__(self, agent_id: int, position: np.ndarray, phase: float):
        self.agent_id = agent_id
        self.position = np.asarray(position, dtype=np.float32)[:2]
        self.phase = float(phase)  # unique identity frequency (radians)
        self.sensed_magnitude: float = 0.0
        self.sensed_phase: float = 0.0
        self.jar_active: bool = False  # is the Jamming Avoidance Response firing?

    def __repr__(self) -> str:
        return f"ElectricAgent(id={self.agent_id}, phase={self.phase:.3f})"


class SwarmElectricField:
    """
    The electric field substrate.

    Biology (Heiligenberg 1991): The electric field is a complex-valued
    quantity with both amplitude and phase. Each fish's EOD contributes
    a sinusoidal component at its characteristic frequency. The fish
    senses the VECTOR SUM of all fields at its location.

    Implementation: We use a 2D complex field (real + imaginary components)
    where each agent's emission is a unit vector at its identity phase.
    """

    def __init__(self, cfg: Optional[ElectricFieldConfig] = None):
        self.cfg = cfg or ElectricFieldConfig()
        g = self.cfg.grid_size

        # Complex electric field: real and imaginary components
        self.field_real = np.zeros((g, g), dtype=np.float32)
        self.field_imag = np.zeros((g, g), dtype=np.float32)

    def _idx(self, pos: np.ndarray) -> Tuple[int, int]:
        xy = np.clip(np.asarray(pos, dtype=np.float32)[:2], 0.0, 1.0)
        g = self.cfg.grid_size - 1
        return int(xy[0] * g), int(xy[1] * g)

    def _diffuse(self, f: np.ndarray) -> np.ndarray:
        if self.cfg.diffusion == 0.0:
            return f
        lap = (
            np.roll(f, 1, 0) + np.roll(f, -1, 0) +
            np.roll(f, 1, 1) + np.roll(f, -1, 1) - 4.0 * f
        )
        return (f + self.cfg.diffusion * lap).astype(np.float32)

    def step(self) -> None:
        """One timestep: decay + diffusion of the electric field."""
        self.field_real *= self.cfg.decay
        self.field_imag *= self.cfg.decay
        self.field_real = self._diffuse(self.field_real)
        self.field_imag = self._diffuse(self.field_imag)

    def emit(self, agent: ElectricAgent) -> None:
        """
        Agent emits its EOD into the field.
        Biology (Hopkins 1988): The EOD is a periodic signal whose
        frequency encodes species and individual identity.
        """
        i, j = self._idx(agent.position)
        self.field_real[i, j] += self.cfg.emit_strength * float(np.cos(agent.phase))
        self.field_imag[i, j] += self.cfg.emit_strength * float(np.sin(agent.phase))

    def sense(self, agent: ElectricAgent) -> Tuple[float, float]:
        """
        Agent senses the local electric field.
        Biology (Carlson & Kawasaki 2007): Electroreceptors on the
        body surface detect the amplitude and phase of the local field.
        """
        i, j = self._idx(agent.position)
        r = float(self.field_real[i, j])
        im = float(self.field_imag[i, j])
        magnitude = float(np.sqrt(r * r + im * im))
        phase = float(np.arctan2(im, r))
        agent.sensed_magnitude = magnitude
        agent.sensed_phase = phase
        return magnitude, phase

    def interaction_reward(self, agent: ElectricAgent) -> float:
        """
        Compute the reward/penalty for this agent based on field sensing.
        Biology (Heiligenberg 1991): The JAR is triggered when two fish
        have similar frequencies. The fish with the lower frequency
        shifts DOWN, the fish with the higher frequency shifts UP.
        """
        phase_diff = float(np.sin(agent.phase - agent.sensed_phase))
        alignment = float(np.cos(agent.phase - agent.sensed_phase))
        jamming = abs(phase_diff)

        signal_reward = self.cfg.sense_gain * agent.sensed_magnitude * alignment
        penalty = self.cfg.jamming_penalty * jamming

        return signal_reward - penalty

    def jamming_avoidance_response(self, agent: ElectricAgent) -> float:
        """
        The Jamming Avoidance Response (JAR).
        Biology (Watanabe & Takeda 1963, Heiligenberg 1991):
        When two fish emit at similar frequencies, each fish shifts
        its own frequency AWAY from the other to restore clear
        communication channels.

        Returns the phase shift applied.
        """
        phase_diff = agent.phase - agent.sensed_phase
        # Normalize to [-pi, pi]
        phase_diff = float(np.arctan2(np.sin(phase_diff), np.cos(phase_diff)))

        # If phases are too close → JAR fires
        if abs(phase_diff) < self.cfg.identity_threshold:
            # Shift away: positive diff → shift more positive, negative → more negative
            if abs(phase_diff) < self.cfg.eps:
                shift = self.cfg.jar_shift_rate  # arbitrary direction to break symmetry
            else:
                shift = self.cfg.jar_shift_rate * float(np.sign(phase_diff))
            agent.phase += shift
            agent.jar_active = True
            return shift
        else:
            agent.jar_active = False
            return 0.0

    def magnitude_field(self) -> np.ndarray:
        """Return the scalar magnitude of the electric field."""
        return np.sqrt(
            self.field_real ** 2 + self.field_imag ** 2
        ).astype(np.float32)

    def phase_field(self) -> np.ndarray:
        """Return the phase angle of the electric field."""
        return np.arctan2(self.field_imag, self.field_real).astype(np.float32)


def proof_of_property() -> bool:
    """
    MANDATE VERIFICATION — ELECTRIC FISH IDENTITY & JAR TEST.

    Proves four biological invariants:
      1. Agents can broadcast identity via unique phase emission
      2. Agents can sense others without vision (electrolocation)
      3. Jamming Avoidance Response separates colliding frequencies
      4. Agents self-organize into distinct communication channels
    """
    print("\n=== SIFTA ELECTRIC FIELD IDENTITY (Event 69) : JUDGE VERIFICATION ===")

    cfg = ElectricFieldConfig(grid_size=32)
    field = SwarmElectricField(cfg)

    # Phase 1: Identity emission & sensing
    print("\n[*] Phase 1: Identity Emission (Hopkins 1988)")
    agent_a = ElectricAgent(0, np.array([0.3, 0.3]), phase=0.0)
    agent_b = ElectricAgent(1, np.array([0.7, 0.7]), phase=np.pi / 2)

    field.emit(agent_a)
    field.emit(agent_b)
    field.step()

    mag_a, phase_a = field.sense(agent_a)
    mag_b, phase_b = field.sense(agent_b)

    print(f"    Agent A (phase=0.000): sensed mag={mag_a:.3f}, phase={phase_a:.3f}")
    print(f"    Agent B (phase=1.571): sensed mag={mag_b:.3f}, phase={phase_b:.3f}")
    assert mag_a > 0.0, "[FAIL] Agent A could not sense the field"
    assert mag_b > 0.0, "[FAIL] Agent B could not sense the field"

    # Phase 2: Electrolocation — sensing at distance
    print("\n[*] Phase 2: Electrolocation (Heiligenberg 1991)")
    field2 = SwarmElectricField(cfg)
    emitter = ElectricAgent(0, np.array([0.5, 0.5]), phase=1.0)
    field2.emit(emitter)
    for _ in range(5):
        field2.step()  # let the field diffuse

    sensor_near = ElectricAgent(1, np.array([0.55, 0.55]), phase=0.0)
    sensor_far = ElectricAgent(2, np.array([0.9, 0.9]), phase=0.0)
    mag_near, _ = field2.sense(sensor_near)
    mag_far, _ = field2.sense(sensor_far)

    print(f"    Near sensor (d=0.07): mag={mag_near:.4f}")
    print(f"    Far sensor  (d=0.57): mag={mag_far:.4f}")
    assert mag_near > mag_far, "[FAIL] Near sensor should detect stronger field"

    # Phase 3: Jamming Avoidance Response
    print("\n[*] Phase 3: Jamming Avoidance Response (Watanabe & Takeda 1963)")
    field3 = SwarmElectricField(cfg)
    jammer_a = ElectricAgent(0, np.array([0.5, 0.5]), phase=1.00)
    jammer_b = ElectricAgent(1, np.array([0.5, 0.5]), phase=1.05)  # very close phase!

    initial_diff = abs(jammer_a.phase - jammer_b.phase)
    print(f"    Initial phase difference: {initial_diff:.4f} rad")

    for _ in range(20):
        field3.field_real[:] = 0.0
        field3.field_imag[:] = 0.0
        field3.emit(jammer_a)
        field3.emit(jammer_b)
        field3.step()
        field3.sense(jammer_a)
        field3.sense(jammer_b)
        field3.jamming_avoidance_response(jammer_a)
        field3.jamming_avoidance_response(jammer_b)

    final_diff = abs(jammer_a.phase - jammer_b.phase)
    print(f"    Final phase difference:   {final_diff:.4f} rad")
    assert final_diff > initial_diff, "[FAIL] JAR did not separate colliding frequencies"

    # Phase 4: Self-organization of frequency bands
    print("\n[*] Phase 4: Self-Organization (Carlson & Kawasaki 2007)")
    field4 = SwarmElectricField(cfg)
    rng = np.random.default_rng(69)
    agents = [
        ElectricAgent(
            i,
            rng.uniform(0.2, 0.8, size=2).astype(np.float32),
            phase=float(rng.uniform(0.0, 0.3))  # all start clustered in [0, 0.3]
        )
        for i in range(6)
    ]

    initial_phases = [a.phase for a in agents]
    initial_spread = float(np.std(initial_phases))

    for _ in range(40):
        field4.field_real[:] = 0.0
        field4.field_imag[:] = 0.0
        for a in agents:
            field4.emit(a)
        field4.step()
        for a in agents:
            field4.sense(a)
            field4.jamming_avoidance_response(a)

    final_phases = [a.phase for a in agents]
    final_spread = float(np.std(final_phases))

    print(f"    Initial phase spread (std): {initial_spread:.4f}")
    print(f"    Final phase spread (std):   {final_spread:.4f}")
    assert final_spread > initial_spread, "[FAIL] Agents did not spread in phase space"

    print("\n[+] BIOLOGICAL PROOF: Electric field identity verified.")
    print("    1. Agents broadcast identity via unique phase emission (Hopkins 1988)")
    print("    2. Electrolocation: near sensor detects stronger field (Heiligenberg 1991)")
    print("    3. JAR separated colliding frequencies (Watanabe & Takeda 1963)")
    print("    4. Agents self-organized into distinct channels (Carlson & Kawasaki 2007)")
    print("[+] EVENT 69 PASSED.")
    return True


if __name__ == "__main__":
    proof_of_property()
