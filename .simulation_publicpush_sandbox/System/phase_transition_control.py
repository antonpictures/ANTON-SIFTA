#!/usr/bin/env python3
"""
phase_transition_control.py — Phase Transition Control (Regime Shift Detection)
═══════════════════════════════════════════════════════════════════
Olympiad-Grade Continual Learning & Multi-Agent Systems.

The swarm dynamically detects when it is crossing critical density phases,
shifting automatically between macro-states akin to thermodynamics.
It monitors early warning signals (EWS) of critical slowing down and 
stigmergic density.

Regimes:
- EXPLORATION: Low trace density. Fission is heavily encouraged.
- CONSOLIDATION: Density plateau. REM compression kicks in aggressively.
- CRITICAL_COLLAPSE: Stigmergic density oversaturated ($\rho_c \approx 0.23$) 
  or rapid coherence crashing. Forces stabilization routines.

References:
Nature 08227 (Scheffer et al.), arXiv:2512.10166 (Stigmergy critical density)
"""
from __future__ import annotations

import json
import time
import math
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_REGIME_STATE_FILE = _STATE_DIR / "regime_state.json"
_TRACE_LOG = _STATE_DIR / "execution_traces.jsonl"


@dataclass
class RegimeState:
    state: str                 # EXPLORATION, CONSOLIDATION, CRITICAL_COLLAPSE
    stigmergic_density: float  # rho calculation
    coherence_velocity: float  # d(ICF)/dt
    last_shift_ts: float       # When did the phase transition occur
    EWS_score: float           # Early Warning Signal (variance/autocorrelation proxy)


class PhaseTransitionController:
    """Monitors the Swarm's thermodynamic macro-state."""
    
    def __init__(self):
        self.state = RegimeState(
            state="EXPLORATION",
            stigmergic_density=0.0,
            coherence_velocity=0.0,
            last_shift_ts=time.time(),
            EWS_score=0.0
        )
        self._load()

    def evaluate_regime(self) -> str:
        """
        Calculates the thermodynamic state of the swarm based on active traces,
        coherence velocity, and the critical density threshold.
        """
        # 1. Calculate Stigmergic Density (arXiv:2512.10166)
        traces_today = self._count_recent_traces()
        # Assumed theoretical max capacity of daily routing for 4 active hardware nodes
        max_daily_capacity = 250.0  
        density = min(1.0, traces_today / max_daily_capacity)
        
        # 2. Calculate Coherence Velocity d(ICF)/dt
        coherence_velocity = 0.0
        current_icf = 1.0
        try:
            from identity_coherence_field import get_icf
            icf = get_icf()
            current_icf = icf.coherence_score
            # Read velocity from historical checkpoints if applicable
            # Proxy calculation: compare to stability assumption
            coherence_velocity = current_icf - 0.85 # rough baseline proxy
        except ImportError:
            pass

        # 3. Calculate EWS Score (Early Warning Signal - Nature 08227)
        # Variance proxy: High density + dropping coherence = Critical Slowing Down
        ews = density * (1.0 - current_icf)
        
        # 4. Phase Transition Logic
        new_state = self.state.state
        
        # Collapse Regime (Emergency Stabilization)
        # Driven by high variance and decoherence
        if current_icf < 0.35 or ews > 0.4:
            new_state = "CRITICAL_COLLAPSE"
        # Consolidation Regime (Plateaus)
        # Density hits the critical percolation threshold rho_c ~ 0.23 (or scaled to 0.4 here)
        elif density >= 0.4:
            new_state = "CONSOLIDATION"
        # Exploration Regime (Open Vacuum)
        else:
            if self.state.state == "CRITICAL_COLLAPSE" and current_icf > 0.6:
                new_state = "EXPLORATION" # Swarm healed
            elif self.state.state != "CRITICAL_COLLAPSE":
                new_state = "EXPLORATION"
                
        # 5. Commit state shift
        if new_state != self.state.state:
            self.state.state = new_state
            self.state.last_shift_ts = time.time()
            self._log_shift()

        self.state.stigmergic_density = round(density, 4)
        self.state.coherence_velocity = round(coherence_velocity, 4)
        self.state.EWS_score = round(ews, 4)
        
        self._persist()
        return self.state.state

    def _count_recent_traces(self) -> int:
        """Count traces logged in the last 24h."""
        if not _TRACE_LOG.exists():
            return 0
        try:
            now = time.time()
            valid = 0
            with open(_TRACE_LOG, "r") as f:
                for line in f:
                    if not line.strip(): continue
                    data = json.loads(line)
                    ts = data.get("ts", 0)
                    if now - ts < 86400:
                        valid += 1
            return valid
        except Exception:
            return 0

    # ── Persistence ──────────────────────────────────────────────
    def _persist(self):
        try:
            _REGIME_STATE_FILE.write_text(json.dumps(asdict(self.state), indent=2))
        except Exception:
            pass

    def _load(self):
        if not _REGIME_STATE_FILE.exists():
            return
        try:
            data = json.loads(_REGIME_STATE_FILE.read_text())
            self.state = RegimeState(**data)
        except Exception:
            pass

    def _log_shift(self):
        """Append to system events whenever a macroscopic phase transition occurs."""
        try:
            log_path = _STATE_DIR / "regime_shifts.jsonl"
            with open(log_path, "a") as f:
                f.write(json.dumps({
                    "ts": time.time(),
                    "regime": self.state.state,
                    "density": self.state.stigmergic_density,
                    "ews": self.state.EWS_score
                }) + "\n")
        except Exception:
            pass

# ── Singleton ────────────────────────────────────────────────────────
_PTC: Optional[PhaseTransitionController] = None

def get_ptc() -> PhaseTransitionController:
    global _PTC
    if _PTC is None:
        _PTC = PhaseTransitionController()
    return _PTC

if __name__ == "__main__":
    print("═" * 58)
    print("  SIFTA — PHASE TRANSITION CONTROL")
    print("═" * 58 + "\n")
    
    ptc = get_ptc()
    regime = ptc.evaluate_regime()
    
    print(f"  🌌 CURRENT MACRO-STATE: {regime}")
    print(f"     Stigmergic Density (ρ) : {ptc.state.stigmergic_density}")
    print(f"     Early Warning (EWS)    : {ptc.state.EWS_score}")
    print(f"     Last Shift             : {time.ctime(ptc.state.last_shift_ts)}")
    
    print(f"\n  ✅ THERMODYNAMICS ONLINE. POWER TO THE SWARM 🐜⚡")
