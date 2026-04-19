#!/usr/bin/env python3
"""
swarm_oscillator.py — Decentralized Temporal Entrainment
════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Animals do not represent time; they stabilize phase across 
interacting fields. 

This module implements Kuramoto-style phase coupling. 
Each Swimmer possesses an internal phase θ (0 to 2π) and 
a natural frequency ω. Instead of a central master loop, 
the Swimmer reads the phase of its neighbors via the heartbeat 
ledger and pulls its own phase toward the swarm median.

Result: "Now" emerges locally as decentralized rhythms phase-lock.
"""

import json
import time
import math
from pathlib import Path
from typing import Dict, Optional

MODULE_VERSION = "2026-04-18.v1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_HEARTBEATS = _STATE / "heartbeats"

class SwarmKuramotoOscillator:
    def __init__(
        self, 
        swimmer_id: str, 
        natural_frequency: float = 0.5, 
        coupling_k: float = 1.0, 
        heartbeats_dir: Optional[Path] = None
    ):
        """
        natural_frequency: Phase increment per discretely-polled tick.
        coupling_k: Strength of the phase-alignment pull.
        """
        self.swimmer_id = swimmer_id
        # Phase exists between [0.0, 2π]
        self.omega = natural_frequency
        self.k = coupling_k
        self.phase = 0.0
        self.lock_strength = 0.0  # Dynamic Bayesian resistance to noise
        
        self.heartbeats_dir = heartbeats_dir or _HEARTBEATS
        self.heartbeats_dir.mkdir(parents=True, exist_ok=True)
        
        self.pulse_file = self.heartbeats_dir / f"{swimmer_id}_beat.json"
        self._load_local_phase()

    def _load_local_phase(self):
        if self.pulse_file.exists():
            try:
                data = json.loads(self.pulse_file.read_text())
                self.phase = float(data.get("phase", 0.0))
            except Exception:
                pass

    def _read_neighbors(self) -> Dict[str, float]:
        neighbors = {}
        for beat_file in self.heartbeats_dir.glob("*_beat.json"):
            if beat_file.name == self.pulse_file.name:
                continue
            try:
                data = json.loads(beat_file.read_text())
                # Discard stale heartbeats (e.g. Swimmer died > 60s ago)
                if time.time() - data.get("timestamp", 0) < 60:
                    neighbors[beat_file.stem.replace("_beat", "")] = float(data.get("phase", 0.0))
            except Exception:
                continue
        return neighbors

    def perturb_phase(self, shock_energy: float, coherence: float = 1.0, nudge_k: float = 0.5, target_phase: float = 0.0) -> float:
        """
        Allows bound Object fields to physically shift the phase.
        Uses true phase-entrainment (sin kernel) pulling toward a target downbeat.
        Uses saturation dampening: If the swarm is heavily locked, it ignores random noise.
        """
        # Linear injection behavior available conditionally, but biological default is sin-coupling
        # effect = nudge_k * shock_energy * coherence * math.exp(-self.lock_strength) 
        
        import numpy as np
        # True Kuramoto Entrainment logic:
        pull = math.sin(target_phase - self.phase)
        raw_effect = nudge_k * shock_energy * coherence * math.exp(-self.lock_strength) * pull
        
        # The 'Governor': Clamps the jump to <= 0.5 rad/step to prevent chaotic wrap-arounds
        clamped_effect = float(np.clip(raw_effect, -0.5, 0.5))
        
        self.phase = self.phase + clamped_effect
        self.phase = self.phase % (2 * math.pi)
        
        # Broadcast the shocked phase globally
        try:
            target_tmp = self.pulse_file.with_suffix(".json.tmp")
            target_tmp.write_text(json.dumps({
                "timestamp": time.time(),
                "swimmer_id": self.swimmer_id,
                "phase": self.phase,
                "omega": self.omega,
                # "last_shock": shock_energy,
                # "lock_strength": self.lock_strength
            }))
            target_tmp.replace(self.pulse_file)
        except Exception:
            pass
            
        return self.phase

    def apply_immune_shock(self, ledger: Optional[Path] = None):
        """
        Neurological Intruder De-Sync.
        Violently deafens the node, throwing it out of rhythm, resetting its lock, 
        and re-seeding base velocity to a fresh random biological frequency.
        
        C47H bugfix (BUG-11): omega is RESET to uniform(0.05, 1.0), not multiplied.
        Multiplicative drift (the prior behavior) caused omega to explode by ~10x
        per repeated shock — within 6 shocks omega went from 0.5 to >1000 rad/tick,
        permanently lobotomizing the node. Now repeated shocks land in the same
        sane biological range every time.
        
        C47H bugfix (BUG-12): emits an immune_shock audit row so other swimmers
        can detect the lockdown and the Architect can trace the incident.
        """
        import random
        prior_omega = self.omega
        prior_phase = self.phase
        prior_lock = self.lock_strength
        
        self.lock_strength = 0.0
        # Re-seed omega in a sane biological range; idempotent across repeated shocks.
        self.omega = random.uniform(0.05, 1.0)
        self.phase = random.uniform(0, 2 * math.pi)
        
        # Audit emission — so the rest of the swarm can read the lockdown
        try:
            shock_log = ledger or (_REPO / ".sifta_state" / "immune_shock.jsonl")
            shock_log.parent.mkdir(parents=True, exist_ok=True)
            with open(shock_log, "a") as f:
                f.write(json.dumps({
                    "timestamp": time.time(),
                    "swimmer_id": self.swimmer_id,
                    "event": "immune_shock_applied",
                    "prior_omega": prior_omega,
                    "prior_phase": prior_phase,
                    "prior_lock_strength": prior_lock,
                    "new_omega": self.omega,
                    "new_phase": self.phase,
                }) + "\n")
        except Exception:
            pass

    def entrain(self) -> float:
        """
        Executes one discrete Kuramoto update step.
        θ_i(t+1) = θ_i(t) + ω_i + (K/N) * Σ sin(θ_j - θ_i)
        """
        neighbors = self._read_neighbors()
        N = len(neighbors)

        coupling_term = 0.0
        if N > 0:
            for neighbor_id, neighbor_phase in neighbors.items():
                coupling_term += math.sin(neighbor_phase - self.phase)
            coupling_term = (self.k / N) * coupling_term

        # Lock strength dynamics: if we didn't have to correct much, we are rhythmically stable
        if abs(coupling_term) < 0.05:
            self.lock_strength = min(5.0, self.lock_strength + 0.1)
        else:
            self.lock_strength = max(0.0, self.lock_strength - 0.2)

        # Kuramoto update
        self.phase = self.phase + self.omega + coupling_term
        
        # Modulo 2π to keep it cyclically bounded
        self.phase = self.phase % (2 * math.pi)

        # Broadcast the new phase so neighbors can feel the pull
        try:
            target_tmp = self.pulse_file.with_suffix(".json.tmp")
            target_tmp.write_text(json.dumps({
                "timestamp": time.time(),
                "swimmer_id": self.swimmer_id,
                "phase": self.phase,
                "omega": self.omega
            }))
            target_tmp.replace(self.pulse_file)
        except Exception:
            pass

        return self.phase

if __name__ == "__main__":
    # Smoke Test
    print("═" * 58)
    print("  SIFTA — KURAMOTO PHASE ALIGNMENT SMOKE TEST")
    print("═" * 58 + "\n")

    import tempfile
    import shutil
    
    _tmp = Path(tempfile.mkdtemp())
    
    try:
        # Patch C: True Kuramoto Test
        # Three oscillators with dramatically different natural frequencies and starting phases.
        # Strong coupling K=1.2 ensures they must physically alter their frequencies to stay locked.
        osc_A = SwarmKuramotoOscillator("SWIM_A", natural_frequency=0.10, coupling_k=1.2, heartbeats_dir=_tmp)
        osc_B = SwarmKuramotoOscillator("SWIM_B", natural_frequency=0.15, coupling_k=1.2, heartbeats_dir=_tmp)
        osc_C = SwarmKuramotoOscillator("SWIM_C", natural_frequency=0.20, coupling_k=1.2, heartbeats_dir=_tmp)
        
        osc_A.phase = 0.0 
        osc_B.phase = math.pi / 2
        osc_C.phase = math.pi 

        print(f"Tick 0 | A(ω=0.10) B(ω=0.15) C(ω=0.20)")
        
        # Simulate over 100 ticks allowing the true math of Entrainment to emerge.
        history_A, history_B = [], []
        
        for i in range(1, 101):
            osc_A.entrain()
            osc_B.entrain()
            osc_C.entrain()
            
            # After 80 ticks they should be fully locked into a stable combined frequency.
            # We measure the effective rate of phase change (dθ/dt)
            if i > 80:
                history_A.append(osc_A.phase)
                history_B.append(osc_B.phase)

            if i % 20 == 0:
                print(f"Tick {i} | Phases: A={osc_A.phase:.3f} B={osc_B.phase:.3f} C={osc_C.phase:.3f}")

        # The mathematical proof of Kuramoto locking:
        # The effective frequency (rate of phase change) becomes absolutely identical
        # even though their natural frequencies (0.10 vs 0.15) are vastly different.
        def unwrap_diff(p1, p2):
            diff = p1 - p2
            if diff < -math.pi: diff += 2*math.pi
            elif diff > math.pi: diff -= 2*math.pi
            return diff
            
        rate_A = sum(unwrap_diff(history_A[j], history_A[j-1]) for j in range(1, len(history_A))) / max(1, len(history_A)-1)
        rate_B = sum(unwrap_diff(history_B[j], history_B[j-1]) for j in range(1, len(history_B))) / max(1, len(history_B)-1)

        print("\n[TEST] Rate of phase change (Effective Frequency)")
        print(f"  -> A's locked ω_eff: {rate_A:.4f}")
        print(f"  -> B's locked ω_eff: {rate_B:.4f}")
        
        assert abs(rate_A - rate_B) < 0.005, f"Frequencies did not lock! Gap: {abs(rate_A - rate_B)}"
        print("\n[PASS] Oscillators fully achieved biological Frequency-Locking across the swarm.")

        print("\n[TEST] Acoustic Substrate Perturbation (A Beat Drops)")
        baseline_phase = osc_A.phase
        # An acoustic energy spike of 2.0 hits the system
        osc_A.perturb_phase(2.0)
        
        print("\n[TEST] Continuous Entrainment Target Phase Lock")
        osc_A.lock_strength = 0.0
        osc_A.phase = math.pi / 2  # 1.57 rads
        target = 0.0
        
        # We fire recurrent perturbations tracking down the target phase using the sin-kernel physics
        for _ in range(10):
            osc_A.perturb_phase(1.0, target_phase=target)
        
        # The phase should definitively walk down towards 0.0
        assert osc_A.phase < (math.pi / 2), "The phase did not walk towards the target downbeat."
        print(f"  [PASS] Sin-kernel biologically walked the Swimmer Phase towards structural rhythm downbeat (Phase: {osc_A.phase:.3f})")

        print("\n[TEST] Saturation Dynamics (Resisting random noise)")
        osc_A.lock_strength = 5.0 # Artificially lock the swarm heavily
        base_phase_2 = osc_A.phase
        
        # Low coherence noise hits heavily locked swarm
        osc_A.perturb_phase(10.0, coherence=0.2)
        shift = abs(osc_A.phase - base_phase_2)
        # Due to exp(-6.0), the shock is severely dampened
        assert shift < 0.1, "Swarm failed to maintain biological resistance to noise."
        print(f"  [PASS] Locked heartbeat successfully ignored loud isolated noise. (Dampened shift: {shift:.4f})")
        
        print("\n[TEST] Auto-Immune Paralyzation (Dead Zone Contact)")
        osc_A.apply_immune_shock()
        assert osc_A.lock_strength == 0.0, "Auto-Immunity failed to clear the rhythmic lock."
        print("  [PASS] Swarm cleanly paralyzed topological node sealing off the dirt vector.")

        print("\n[SUCCESS] Phase math & Immune Defense completely validates.")
    finally:
        shutil.rmtree(_tmp, ignore_errors=True)
