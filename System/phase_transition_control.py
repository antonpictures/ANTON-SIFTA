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
_MEMORY_LOG = _STATE_DIR / "body_brain_memory.jsonl"  # Event 100 TD values

# CUSUM parameters (tuned for 10-tick window, 10s cadence)
_CUSUM_K = 0.3      # allowance parameter (half of expected shift)
_CUSUM_H = 2.0      # alarm threshold (decision interval)
_CUSUM_WINDOW = 40  # how many recent ticks to analyse


class PhaseDetectorStats:
    """
    CUSUM-based regime shift detector reading TD values from body_brain_memory.jsonl.

    CUSUM (CUmulative SUM) is Page's test (1954) for detecting a change in the
    mean of a sequential process.  We apply it to Alice's temporal-difference
    value stream: a sudden drop in TD mean signals drive saturation or
    anti-correlation (the physiology is learning nothing new).

    References:
        Page, E.S. (1954). Continuous inspection schemes. Biometrika 41, 100-115.
        Scheffer et al. (2009). Early-warning signals for critical transitions.
        Nature 461, 53-59.  doi:10.1038/nature08227
    """

    def __init__(self, memory_log: Path | None = None) -> None:
        self._log = memory_log or _MEMORY_LOG

    def _read_td_values(self) -> list[float]:
        if not self._log.exists():
            return []
        tds: list[float] = []
        try:
            lines = self._log.read_text("utf-8", errors="replace").splitlines()
            for line in lines[-_CUSUM_WINDOW:]:
                try:
                    row = json.loads(line)
                    if row.get("event") == "body_brain_tick":
                        td = float(row.get("td_value", 0) or 0)
                        tds.append(td)
                except Exception:
                    pass
        except Exception:
            pass
        return tds

    def compute(self) -> dict:
        """Return CUSUM stats dict with cusum_alarm bool."""
        tds = self._read_td_values()
        if len(tds) < 4:
            return {
                "td_mean": 0.0, "td_variance": 0.0,
                "cusum_score": 0.0, "cusum_alarm": False,
                "n_ticks": len(tds),
            }

        n = len(tds)
        mean = sum(tds) / n
        variance = sum((x - mean) ** 2 for x in tds) / max(n - 1, 1)

        # One-sided CUSUM for downward shift (drive saturation)
        # S_n = max(0, S_{n-1} + (mu_0 - x_n) - K)
        # where mu_0 = mean of first-half window (baseline)
        baseline = sum(tds[:n // 2]) / (n // 2) if n >= 4 else mean
        cusum = 0.0
        cusum_scores = []
        for td in tds[n // 2:]:
            cusum = max(0.0, cusum + (baseline - td) - _CUSUM_K)
            cusum_scores.append(cusum)

        alarm = cusum > _CUSUM_H
        # EWS proxy: normalised variance of full window
        ews_from_variance = min(1.0, math.sqrt(variance) / max(abs(mean), 0.01))

        return {
            "td_mean":     round(mean, 6),
            "td_variance": round(variance, 6),
            "cusum_score": round(cusum, 4),
            "cusum_alarm": alarm,
            "ews_td":      round(ews_from_variance, 4),
            "n_ticks":     n,
            "baseline":    round(baseline, 6),
        }


@dataclass
class RegimeState:
    state: str                 # EXPLORATION, CONSOLIDATION, CRITICAL_COLLAPSE
    stigmergic_density: float  # rho calculation
    coherence_velocity: float  # d(ICF)/dt
    last_shift_ts: float       # When did the phase transition occur
    EWS_score: float           # Early Warning Signal (variance/autocorrelation proxy)
    cusum_alarm: bool = False  # CUSUM alarm from TD value stream
    td_mean: float = 0.0       # mean TD value in last window
    td_variance: float = 0.0   # variance of TD stream
    cusum_score: float = 0.0   # raw CUSUM statistic


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
        coherence velocity, critical density threshold, AND CUSUM on TD values.
        """
        # 1. Calculate Stigmergic Density (arXiv:2512.10166)
        traces_today = self._count_recent_traces()
        max_daily_capacity = 250.0  
        density = min(1.0, traces_today / max_daily_capacity)
        
        # 2. Calculate Coherence Velocity d(ICF)/dt
        coherence_velocity = 0.0
        current_icf = 1.0
        try:
            from identity_coherence_field import get_icf
            icf = get_icf()
            current_icf = icf.coherence_score
            coherence_velocity = current_icf - 0.85
        except ImportError:
            pass

        # 3. EWS Score from density + ICF
        ews_density = density * (1.0 - current_icf)

        # 4. CUSUM on body_brain TD values — detects drive saturation
        cusum_stats = PhaseDetectorStats().compute()
        ews_combined = max(ews_density, cusum_stats.get("ews_td", 0.0) * 0.5)
        cusum_alarm = cusum_stats.get("cusum_alarm", False)
        
        # 5. Phase Transition Logic
        new_state = self.state.state
        
        # Collapse: ICF decoherence OR CUSUM alarm (drive saturation)
        if current_icf < 0.35 or ews_combined > 0.4 or cusum_alarm:
            new_state = "CRITICAL_COLLAPSE"
        # Consolidation: percolation threshold reached
        elif density >= 0.4:
            new_state = "CONSOLIDATION"
        # Exploration: open vacuum
        else:
            if self.state.state == "CRITICAL_COLLAPSE" and current_icf > 0.6 and not cusum_alarm:
                new_state = "EXPLORATION"  # Swarm healed
            elif self.state.state != "CRITICAL_COLLAPSE":
                new_state = "EXPLORATION"
                
        # 6. Commit state shift
        if new_state != self.state.state:
            self.state.state = new_state
            self.state.last_shift_ts = time.time()
            self._log_shift(cusum_stats)

        self.state.stigmergic_density = round(density, 4)
        self.state.coherence_velocity = round(coherence_velocity, 4)
        self.state.EWS_score = round(ews_combined, 4)
        self.state.cusum_alarm = cusum_alarm
        self.state.td_mean = cusum_stats.get("td_mean", 0.0)
        self.state.td_variance = cusum_stats.get("td_variance", 0.0)
        self.state.cusum_score = cusum_stats.get("cusum_score", 0.0)
        
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

    def _log_shift(self, cusum_stats: dict | None = None):
        """Append to system events whenever a macroscopic phase transition occurs."""
        try:
            log_path = _STATE_DIR / "regime_shifts.jsonl"
            row: dict = {
                "ts": time.time(),
                "regime": self.state.state,
                "density": self.state.stigmergic_density,
                "ews": self.state.EWS_score,
                "cusum_alarm": self.state.cusum_alarm,
                "td_mean": self.state.td_mean,
                "cusum_score": self.state.cusum_score,
            }
            if cusum_stats:
                row["cusum_n_ticks"] = cusum_stats.get("n_ticks", 0)
            with open(log_path, "a") as f:
                f.write(json.dumps(row) + "\n")
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
    print("  SIFTA — PHASE TRANSITION CONTROL + CUSUM DETECTOR")
    print("═" * 58 + "\n")
    
    # CUSUM probe
    stats = PhaseDetectorStats().compute()
    print(f"  CUSUM stats from body_brain_memory.jsonl:")
    print(f"     TD mean:       {stats['td_mean']:.4f}")
    print(f"     TD variance:   {stats['td_variance']:.6f}")
    print(f"     CUSUM score:   {stats['cusum_score']:.4f}  (alarm thresh={_CUSUM_H})")
    print(f"     CUSUM alarm:   {stats['cusum_alarm']}")
    print(f"     EWS (TD):      {stats.get('ews_td', 0):.4f}")
    print(f"     N ticks:       {stats['n_ticks']}")
    print()

    ptc = get_ptc()
    regime = ptc.evaluate_regime()
    
    print(f"  🌌 CURRENT MACRO-STATE: {regime}")
    print(f"     Stigmergic Density (ρ) : {ptc.state.stigmergic_density}")
    print(f"     Early Warning (EWS)    : {ptc.state.EWS_score}")
    print(f"     CUSUM Alarm            : {ptc.state.cusum_alarm}")
    print(f"     Last Shift             : {time.ctime(ptc.state.last_shift_ts)}")
    
    print(f"\n  ✅ THERMODYNAMICS + CUSUM ONLINE. POWER TO THE SWARM 🐜⚡")
