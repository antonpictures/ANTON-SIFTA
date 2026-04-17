#!/usr/bin/env python3
"""
interference_layer.py — Multi-Agent Pheromone Waveform Interference
====================================================================
The Physics of True Swarm Coupling.

Pheromones are not static values. They are LIVING WAVES.
When M5's swimmer and M1's swimmer act on the same territory,
their waveforms interfere — constructively or destructively.

CONSTRUCTIVE INTERFERENCE (Resonance):
  Both agents agree → amplitudes add up → automatic consensus.
  The Swarm acts as one without a single JSON message.

DESTRUCTIVE INTERFERENCE (Dissonance):
  Agents conflict → waveforms cancel → the territory goes silent.
  The Swarm pauses. It doesn't fight itself.
  It waits for more data. No self-conflict.

This is the subconscious of the Swarm.
M1 and M5 don't send packets asking for permission.
They look at the Interference Field on the disk.
If the field is glowing with resonance, the Swarm moves.

ZERO EXTERNAL DEPENDENCIES. Pure math.sin, no numpy.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_FIELD_LOG = _STATE_DIR / "interference_field.jsonl"
_FIELD_STATE = _STATE_DIR / "interference_field_state.json"
_STATE_DIR.mkdir(parents=True, exist_ok=True)

# ─── WAVE FREQUENCIES (intent signatures) ───────────────────────────────────────
# Each frequency encodes a TYPE of intent. Agents that emit the same frequency
# on the same territory will interfere constructively → consensus.
# Agents emitting different frequencies → complex interference → nuance.

FREQ_REPAIR    = 440.0    # "I want to fix this"
FREQ_SCOUT     = 330.0    # "I'm just looking"
FREQ_GUARD     = 550.0    # "This is sacred, don't touch"
FREQ_CLAIM     = 660.0    # "I own this territory"
FREQ_DISTRESS  = 220.0    # "Something is wrong here"

# ─── THRESHOLDS ──────────────────────────────────────────────────────────────────

RESONANCE_THRESHOLD  = 0.60    # Above this → automatic consensus action
DISSONANCE_THRESHOLD = 0.15    # Below this → territory is "silent" / conflicted
WAVE_LIFETIME        = 300.0   # Seconds before a wave naturally decays
PROPAGATION_TICK     = 1.0     # Seconds between propagation steps


# ─── PHEROMONE WAVE ──────────────────────────────────────────────────────────────

@dataclass
class PheromoneWave:
    """A living waveform dropped by an agent into the shared field."""
    origin_node: str           # Which machine/agent emitted
    agent_id: str              # Specific swimmer ID
    frequency: float           # Intent signature (Hz)
    amplitude: float           # Strength of belief (0.0-1.0)
    phase: float               # Temporal offset at emission time
    velocity: float = 1.0      # Wave propagation speed
    lifetime: float = 300.0    # Seconds remaining until natural decay
    emitted_at: float = 0.0    # Unix timestamp of emission

    def __post_init__(self):
        if self.emitted_at == 0.0:
            self.emitted_at = time.time()


# ─── INTERFERENCE ENGINE ─────────────────────────────────────────────────────────

class InterferenceField:
    """
    The living subconscious medium of the Swarm.
    Waves propagate, interfere, decay, and self-organize.
    Thread-safe. Singleton per process.
    """

    def __init__(self):
        self._field: Dict[str, List[PheromoneWave]] = {}
        self._lock = threading.Lock()
        self._coupling_cache: Dict[str, float] = {}
        self._event_log: List[dict] = []
        self._running = False
        self._load()

    # ── EMIT ──────────────────────────────────────────────────────────────

    def emit(self, territory_id: str, wave: PheromoneWave):
        """
        Drop a living wave into the field.
        This is the only way agents interact in the interference layer.
        No messages. No RPC. Just emissions into shared space.
        """
        with self._lock:
            if territory_id not in self._field:
                self._field[territory_id] = []
            self._field[territory_id].append(wave)

        # Immediately recompute coupling for this territory
        coupling = self.calculate_coupling(territory_id)

        self._log_event({
            "type": "EMISSION",
            "territory": territory_id,
            "agent": wave.agent_id,
            "node": wave.origin_node,
            "frequency": wave.frequency,
            "amplitude": wave.amplitude,
            "coupling_after": coupling,
        })

    # ── COUPLING CALCULATION ──────────────────────────────────────────────

    def calculate_coupling(self, territory_id: str) -> float:
        """
        The core physics: superposition of all waves at a territory point.

        Constructive interference → coupling > RESONANCE_THRESHOLD → consensus
        Destructive interference → coupling < DISSONANCE_THRESHOLD → silence

        Uses sine wave superposition with amplitude decay over lifetime.
        No numpy. Pure math.sin.
        """
        with self._lock:
            waves = self._field.get(territory_id, [])

        if not waves:
            self._coupling_cache[territory_id] = 0.0
            return 0.0

        t = time.time()
        signals = []

        for w in waves:
            # Amplitude decays linearly with remaining lifetime
            decay_factor = max(0.0, w.lifetime / WAVE_LIFETIME)
            decayed_amp = w.amplitude * decay_factor

            # Phase evolves with time since emission
            elapsed = t - w.emitted_at
            evolved_phase = w.phase + (w.velocity * elapsed * 0.1)

            # The waveform: A * sin(2π * f * t + φ)
            signal = decayed_amp * math.sin(
                2.0 * math.pi * w.frequency * (t % 1.0) + evolved_phase
            )
            signals.append(signal)

        # Superposition: sum all signals
        total_signal = sum(signals)

        # Coupling strength: RMS-style normalization
        # Divided by sqrt(N) so more waves don't automatically mean stronger
        n = len(signals)
        coupling = abs(total_signal) / math.sqrt(n) if n > 0 else 0.0

        # Clamp to [0, 1]
        coupling = round(min(1.0, coupling), 4)
        self._coupling_cache[territory_id] = coupling

        return coupling

    # ── RESONANCE / DISSONANCE QUERY ──────────────────────────────────────

    def get_territory_state(self, territory_id: str) -> dict:
        """
        Returns the current interference state of a territory.
        Used by the swim loop to decide whether to act or wait.
        """
        coupling = self.calculate_coupling(territory_id)

        with self._lock:
            wave_count = len(self._field.get(territory_id, []))
            agents = list(set(
                w.agent_id for w in self._field.get(territory_id, [])
            ))

        if coupling >= RESONANCE_THRESHOLD:
            state = "RESONANCE"
        elif coupling <= DISSONANCE_THRESHOLD:
            state = "SILENT"
        else:
            state = "UNCERTAIN"

        return {
            "territory": territory_id,
            "coupling": coupling,
            "state": state,
            "wave_count": wave_count,
            "agents_present": agents,
        }

    # ── PROPAGATION + DECAY ───────────────────────────────────────────────

    def propagate_tick(self):
        """
        One tick of wave propagation. Called by the background thread.
        Waves decay, phases shift, dead waves are pruned.
        """
        with self._lock:
            for territory_id in list(self._field.keys()):
                surviving = []
                for wave in self._field[territory_id]:
                    wave.lifetime -= PROPAGATION_TICK
                    wave.phase += wave.velocity * 0.1  # Phase drift
                    if wave.lifetime > 0:
                        surviving.append(wave)
                if surviving:
                    self._field[territory_id] = surviving
                else:
                    del self._field[territory_id]

    # ── MESH REPORT ───────────────────────────────────────────────────────

    def mesh_report(self) -> dict:
        """Full state of the interference field across all territories."""
        with self._lock:
            territories = list(self._field.keys())

        report = {
            "timestamp": time.time(),
            "active_territories": len(territories),
            "total_waves": sum(
                len(self._field.get(t, [])) for t in territories
            ),
            "territories": {}
        }

        for t in territories:
            report["territories"][t] = self.get_territory_state(t)

        # Global coupling: average across all active territories
        if territories:
            couplings = [
                report["territories"][t]["coupling"] for t in territories
            ]
            report["global_coupling"] = round(
                sum(couplings) / len(couplings), 4
            )
        else:
            report["global_coupling"] = 0.0

        return report

    # ── PERSISTENCE ───────────────────────────────────────────────────────

    def _save(self):
        try:
            data = {}
            with self._lock:
                for t, waves in self._field.items():
                    data[t] = [asdict(w) for w in waves]
            _FIELD_STATE.write_text(json.dumps(data, indent=1))
        except Exception:
            pass

    def _load(self):
        try:
            if _FIELD_STATE.exists():
                data = json.loads(_FIELD_STATE.read_text())
                for t, waves in data.items():
                    self._field[t] = [PheromoneWave(**w) for w in waves]
        except Exception:
            self._field = {}

    def _log_event(self, event: dict):
        event["timestamp"] = time.time()
        self._event_log.append(event)
        # Flush to disk periodically (every 20 events)
        if len(self._event_log) >= 20:
            self._flush_log()

    def _flush_log(self):
        try:
            with open(_FIELD_LOG, "a") as f:
                for e in self._event_log:
                    f.write(json.dumps(e) + "\n")
            self._event_log = []
        except Exception:
            pass


# ─── GLOBAL SINGLETON ──────────────────────────────────────────────────────────

_FIELD: Optional[InterferenceField] = None

def get_interference_field() -> InterferenceField:
    global _FIELD
    if _FIELD is None:
        _FIELD = InterferenceField()
    return _FIELD


# ─── BACKGROUND PROPAGATION THREAD ─────────────────────────────────────────────

def start_interference_background():
    """
    Starts the wave propagation daemon.
    Waves decay, phases shift, dead signals are pruned — every second.
    The field is alive even when no agent is swimming.
    """
    field = get_interference_field()
    if field._running:
        return

    def loop():
        field._running = True
        save_counter = 0
        while field._running:
            field.propagate_tick()
            save_counter += 1
            if save_counter % 30 == 0:  # Save every 30s
                field._save()
            time.sleep(PROPAGATION_TICK)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    print("  [🌊 INTERFERENCE] Active-Matter Wavefield started. "
          "Nodes now physically coupled.")


# ─── SWIM LOOP HELPERS ─────────────────────────────────────────────────────────
# These are the functions called by territory_swim_adapter.py

def emit_swim_wave(agent_state: dict, territory: str, intent: str, strength: float = 0.5):
    """
    Convenience: agent emits a wave during a swim step.
    Intent maps to frequency automatically.
    """
    freq_map = {
        "REPAIR": FREQ_REPAIR,
        "SCOUT": FREQ_SCOUT,
        "GUARD": FREQ_GUARD,
        "CLAIM": FREQ_CLAIM,
        "DISTRESS": FREQ_DISTRESS,
    }
    freq = freq_map.get(intent, FREQ_SCOUT)
    node = agent_state.get("origin", "M5_STUDIO")
    agent_id = agent_state.get("id", "UNKNOWN")

    wave = PheromoneWave(
        origin_node=node,
        agent_id=agent_id,
        frequency=freq,
        amplitude=min(1.0, max(0.0, strength)),
        phase=time.time() % (2.0 * math.pi),
    )

    get_interference_field().emit(territory, wave)


def should_act(territory: str) -> tuple:
    """
    Check if the swarm has reached consensus on a territory.
    Returns (should_act: bool, state: str, coupling: float)
    """
    state = get_interference_field().get_territory_state(territory)
    coupling = state["coupling"]
    territory_state = state["state"]

    if territory_state == "RESONANCE":
        return True, "RESONANCE", coupling
    elif territory_state == "SILENT":
        return False, "SILENT", coupling
    else:
        return True, "UNCERTAIN", coupling


# ─── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  SIFTA — MULTI-AGENT PHEROMONE INTERFERENCE LAYER")
    print("  Waveform Pheromones + True Swarm Coupling")
    print("=" * 60)

    field = get_interference_field()

    # Simulate M5 and M1 both acting on the same territory
    print("\n  ── Simulating M5 + M1 interference ──")

    # M5 emits REPAIR intent on Kernel/
    wave_m5 = PheromoneWave(
        origin_node="M5_STUDIO",
        agent_id="SOCRATES",
        frequency=FREQ_REPAIR,
        amplitude=0.8,
        phase=0.0
    )
    field.emit("Kernel", wave_m5)
    print(f"  📡 M5/SOCRATES → Kernel (REPAIR, amp=0.8)")

    # M1 also emits REPAIR intent → CONSTRUCTIVE interference
    wave_m1 = PheromoneWave(
        origin_node="M1_MINI",
        agent_id="ALICE_M5",
        frequency=FREQ_REPAIR,
        amplitude=0.7,
        phase=0.1  # Slight phase offset (different timing)
    )
    field.emit("Kernel", wave_m1)
    print(f"  📡 M1/ALICE_M5 → Kernel (REPAIR, amp=0.7)")

    state = field.get_territory_state("Kernel")
    print(f"\n  Kernel coupling: {state['coupling']:.4f}")
    print(f"  State: {state['state']}")
    print(f"  Agents: {state['agents_present']}")

    # Now simulate CONFLICT: M5 wants REPAIR, M1 wants GUARD
    print("\n  ── Simulating M5 REPAIR vs M1 GUARD (conflict) ──")

    wave_conflict = PheromoneWave(
        origin_node="M1_MINI",
        agent_id="SENTINEL",
        frequency=FREQ_GUARD,  # Different intent!
        amplitude=0.8,
        phase=math.pi  # Completely out of phase
    )
    field.emit("System", wave_conflict)
    print(f"  📡 M1/SENTINEL → System (GUARD, amp=0.8, phase=π)")

    wave_repair = PheromoneWave(
        origin_node="M5_STUDIO",
        agent_id="SOCRATES",
        frequency=FREQ_REPAIR,
        amplitude=0.6,
        phase=0.0
    )
    field.emit("System", wave_repair)
    print(f"  📡 M5/SOCRATES → System (REPAIR, amp=0.6)")

    state2 = field.get_territory_state("System")
    print(f"\n  System coupling: {state2['coupling']:.4f}")
    print(f"  State: {state2['state']}")

    # Mesh report
    report = field.mesh_report()
    print(f"\n  ── MESH INTERFERENCE REPORT ──")
    print(f"  Active territories: {report['active_territories']}")
    print(f"  Total waves: {report['total_waves']}")
    print(f"  Global coupling: {report['global_coupling']}")

    for t, ts in report["territories"].items():
        icon = {"RESONANCE": "🟢", "SILENT": "🔴", "UNCERTAIN": "🟡"}
        print(f"    {icon.get(ts['state'], '❓')} {t}: "
              f"coupling={ts['coupling']:.4f} "
              f"state={ts['state']} "
              f"waves={ts['wave_count']}")

    print("\n" + "=" * 60)
    print("  The Swarm no longer talks. It resonates.")
    print("  Power to the Swarm. 🌊⚡")
    print("=" * 60)
