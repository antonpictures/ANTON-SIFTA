#!/usr/bin/env python3
"""
agentic_calibrator.py — Autonomous Swarm Parameter Tuning
═════════════════════════════════════════════════════════════
Inspired by NVIDIA Ising (Quantum Day 2025): AI-driven calibration
of volatile quantum processors, translated to Stigmergic Swarm physics.

Architecture:
  The Calibrator reads a telemetry snapshot (noise level, coherence %,
  pheromone entropy, agent scatter) and computes optimal physics params
  (evaporation rate, sensory threshold, cohesion strength) using a
  proportional-derivative controller with clamped output.

  It writes the result to .sifta_state/swarm_physics.json which any
  running simulation can hot-read every tick.

  Can run as a standalone daemon (if __name__ == "__main__") or be
  imported and called per-tick from the visual calibrator widget.

Theory:
  - High noise + low coherence → increase evaporation (purge bad trails),
    boost cohesion (pull agents back), raise density multiplier.
  - Low noise + low coherence → decrease evaporation (preserve bridges),
    raise sensory threshold (be more selective), hold density.
  - High coherence → gentle relaxation toward defaults.

  This mirrors how NVIDIA's Ising model detects qubit decoherence and
  re-tunes gate voltages in milliseconds.

Run standalone:
  python3 System/agentic_calibrator.py          # daemon mode, polls every 2s
  python3 System/agentic_calibrator.py --once    # single calibration pass
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
STATE_DIR = REPO / ".sifta_state"
TELEMETRY_FILE = STATE_DIR / "telemetry_bus.json"
PHYSICS_FILE = STATE_DIR / "swarm_physics.json"

# ── Default physics ──────────────────────────────────────────────

DEFAULT_EVAPORATION = 0.98       # per-tick multiplier on pheromone grid
DEFAULT_COHESION = 0.60          # agent-to-swarm attraction strength [0,1]
DEFAULT_SENSORY = 0.50           # min pheromone gradient to follow [0,1]
DEFAULT_DENSITY_MULT = 1.0       # agent spawn density multiplier


@dataclass
class SwarmTelemetry:
    """Snapshot of swarm health — written by simulations, read by calibrator."""
    noise_level: float = 0.0         # 0.0 = calm, 1.0 = max chaos
    coherence_pct: float = 100.0     # % of agents on-target
    pheromone_entropy: float = 0.0   # uniformity of pheromone field
    agent_scatter: float = 0.0       # mean distance of agents from centroid
    timestamp: float = 0.0


@dataclass
class SwarmPhysics:
    """Live physics config — written by calibrator, read by simulations."""
    evaporation_rate: float = DEFAULT_EVAPORATION
    cohesion_strength: float = DEFAULT_COHESION
    sensory_threshold: float = DEFAULT_SENSORY
    density_multiplier: float = DEFAULT_DENSITY_MULT
    last_calibration: float = 0.0
    calibration_count: int = 0
    mode: str = "IDLE"  # IDLE, STABILIZING, RECOVERING, LOCKED


def read_telemetry() -> SwarmTelemetry:
    """Read latest telemetry from shared state."""
    try:
        raw = json.loads(TELEMETRY_FILE.read_text())
        return SwarmTelemetry(**{k: raw[k] for k in SwarmTelemetry.__dataclass_fields__ if k in raw})
    except Exception:
        return SwarmTelemetry()


def read_physics() -> SwarmPhysics:
    """Read current physics config."""
    try:
        raw = json.loads(PHYSICS_FILE.read_text())
        return SwarmPhysics(**{k: raw[k] for k in SwarmPhysics.__dataclass_fields__ if k in raw})
    except Exception:
        return SwarmPhysics()


def write_physics(phys: SwarmPhysics) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PHYSICS_FILE.write_text(json.dumps(asdict(phys), indent=2))


def write_telemetry(tel: SwarmTelemetry) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    TELEMETRY_FILE.write_text(json.dumps(asdict(tel), indent=2))


# ── Calibration logic ────────────────────────────────────────────

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass
class CalibratorState:
    """Internal state for the PD controller."""
    prev_coherence: float = 100.0
    prev_noise: float = 0.0
    adjustments_total: int = 0
    adjustments_window: list = field(default_factory=list)

    def record_adjustment(self) -> None:
        now = time.time()
        self.adjustments_total += 1
        self.adjustments_window.append(now)
        cutoff = now - 1.0
        self.adjustments_window = [t for t in self.adjustments_window if t > cutoff]

    @property
    def adjustments_per_sec(self) -> float:
        if not self.adjustments_window:
            return 0.0
        now = time.time()
        cutoff = now - 1.0
        recent = [t for t in self.adjustments_window if t > cutoff]
        return float(len(recent))


def calibrate_once(
    tel: SwarmTelemetry,
    phys: SwarmPhysics,
    state: CalibratorState,
    kp: float = 0.4,
    kd: float = 0.15,
) -> SwarmPhysics:
    """
    Single calibration pass.  Returns updated SwarmPhysics.

    kp: proportional gain (how hard we correct)
    kd: derivative gain (how much we react to rate of change)
    """
    noise = tel.noise_level
    coherence = tel.coherence_pct / 100.0

    coherence_error = 1.0 - coherence
    d_coherence = coherence - state.prev_coherence / 100.0
    d_noise = noise - state.prev_noise

    state.prev_coherence = tel.coherence_pct
    state.prev_noise = noise

    if coherence > 0.85 and noise < 0.2:
        phys.mode = "LOCKED"
        phys.evaporation_rate += (DEFAULT_EVAPORATION - phys.evaporation_rate) * 0.05
        phys.cohesion_strength += (DEFAULT_COHESION - phys.cohesion_strength) * 0.05
        phys.sensory_threshold += (DEFAULT_SENSORY - phys.sensory_threshold) * 0.05
    elif noise > 0.4:
        phys.mode = "STABILIZING"
        # High noise: increase evaporation to kill chaotic trails
        evap_push = kp * noise + kd * max(0, d_noise)
        phys.evaporation_rate = _clamp(phys.evaporation_rate - evap_push * 0.08, 0.85, 0.995)
        # Boost cohesion to pull agents back
        coh_push = kp * coherence_error + kd * max(0, -d_coherence)
        phys.cohesion_strength = _clamp(phys.cohesion_strength + coh_push * 0.15, 0.1, 0.98)
        # Lower sensory threshold so agents respond to weaker correct trails
        phys.sensory_threshold = _clamp(phys.sensory_threshold - noise * 0.1, 0.05, 0.9)
        phys.density_multiplier = _clamp(1.0 + noise * 0.5, 1.0, 2.0)
        state.record_adjustment()
    else:
        phys.mode = "RECOVERING"
        # Low noise but low coherence → swarm stuck in local min
        phys.evaporation_rate = _clamp(phys.evaporation_rate + 0.003, 0.85, 0.995)
        phys.cohesion_strength = _clamp(phys.cohesion_strength - 0.01, 0.1, 0.98)
        phys.sensory_threshold = _clamp(phys.sensory_threshold + 0.02, 0.05, 0.9)
        phys.density_multiplier = _clamp(phys.density_multiplier - 0.01, 1.0, 2.0)
        state.record_adjustment()

    phys.last_calibration = time.time()
    phys.calibration_count += 1
    return phys


# ── Daemon mode ──────────────────────────────────────────────────

def daemon_loop(interval: float = 2.0) -> None:
    """Run calibrator as a standalone polling daemon."""
    print("SWARM CALIBRATOR ONLINE — monitoring .sifta_state/telemetry_bus.json")
    cs = CalibratorState()
    phys = read_physics()

    while True:
        tel = read_telemetry()
        phys = calibrate_once(tel, phys, cs)
        write_physics(phys)
        print(f"[CAL] mode={phys.mode} evap={phys.evaporation_rate:.3f} "
              f"coh={phys.cohesion_strength:.3f} sens={phys.sensory_threshold:.3f} "
              f"noise={tel.noise_level:.2f} coher={tel.coherence_pct:.1f}%")
        time.sleep(interval)


if __name__ == "__main__":
    import sys
    if "--once" in sys.argv:
        tel = read_telemetry()
        phys = read_physics()
        cs = CalibratorState()
        phys = calibrate_once(tel, phys, cs)
        write_physics(phys)
        print(json.dumps(asdict(phys), indent=2))
    else:
        daemon_loop()
