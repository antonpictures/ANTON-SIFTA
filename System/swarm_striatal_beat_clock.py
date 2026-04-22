#!/usr/bin/env python3
"""
System/swarm_striatal_beat_clock.py — Event 3: Striatal Beat-Frequency
═══════════════════════════════════════════════════════════════════════
Concept : Striatal Beat-Frequency Model (Coincidence Detection)
Author  : AO46 — covering C47H east-flank for Time Perception Tournament
Papers  : Matell MS, Meck WH (2004) Cogn Brain Res 21(2):139-170  [P6]
          Buhusi CV, Meck WH (2005) Nat Rev Neurosci 6(10):755-765  [P2]
Status  : ACTIVE ORGAN

BIOLOGY:
Rather than one centralized pacemaker, the striatal beat-frequency (SBF)
model proposes that THOUSANDS of cortical oscillators with slightly
different frequencies fire together at t=0, then drift out of phase,
then come back into coincidence at various learned intervals.

The striatal medium spiny neurons (MSNs) act as COINCIDENCE DETECTORS.
They learn — via Hebbian dopamine-gated synaptic plasticity — which
coincidence pattern of cortical oscillator phases corresponds to a
given criterion interval (e.g., "10 seconds has passed").

This is an IMPLICIT timer: it can learn arbitrary criterion intervals
just by changing which synaptic weights (which coincidence pattern)
are reinforced. Multiple intervals can coexist without interference.

MATH (from Matell & Meck 2004, eq. 3-7):
  N oscillators with frequencies f_i ∈ [8, 13] Hz (theta/alpha range)
  phase_i(t) = (2π · f_i · t) mod 2π
  At t=0, all phases reset to 0 (stimulus onset).
  coincidence(t) = Σ cos(phase_i(t))   ← peaks when in phase
  After training on criterion T:
    w_i = cos(2π · f_i · T)   (Hebbian snapshot of what phases "looked
    like" at the criterion time)
  Recall: response(t) = Σ w_i · cos(phase_i(t))  ← peaks at t≈T

WIRING:
  Writes : .sifta_state/striatal_beat_state.json
  Consumed by: swarm_species_time_persona.py (Event 6, AG31)

STGM ECONOMY:
  Training a new criterion interval costs 0.25 STGM (memory consolidation).
  Reading the clock is free.

VERIFICATION:
  proof_of_property() trains on 4s criterion, tests on 0-10s sweep.
  Peak response must be within ±0.4s of 4s (Weber fraction 0.10).
  Dual-criterion test: 4s AND 7s without interference.
"""

import json
import math
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

try:
    from Kernel.inference_economy import record_inference_fee, get_stgm_balance
    _STGM_AVAILABLE = True
except ImportError:
    _STGM_AVAILABLE = False

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)
_BEAT_STATE = _STATE / "striatal_beat_state.json"

# ── Constants ──────────────────────────────────────────────────────────
N_OSCILLATORS = 64                       # number of cortical oscillators
FREQ_LO = 8.0                           # Hz (theta band lower bound)
FREQ_HI = 13.0                          # Hz (alpha band upper bound)
TRAINING_STGM_COST = 0.25               # STGM cost per criterion learned
WEBER_FRACTION = 0.10                    # temporal resolution limit


class StriatalBeatClock:
    """
    Matell & Meck 2004 striatal beat-frequency clock.

    N cortical oscillators with unique frequencies create a distinctive
    phase-coincidence pattern at each moment in time. Striatal MSNs
    learn which pattern corresponds to a criterion interval (Hebbian
    weights). At recall, the dot product of current phases × weights
    peaks sharply when the criterion interval has elapsed.
    """

    def __init__(self, n_oscillators: int = N_OSCILLATORS,
                 freq_lo: float = FREQ_LO, freq_hi: float = FREQ_HI,
                 seed: Optional[int] = None):
        rng = np.random.default_rng(seed)
        self.n = n_oscillators
        self.freqs = rng.uniform(freq_lo, freq_hi, size=n_oscillators)
        self.criteria: Dict[str, np.ndarray] = {}
        self._criterion_durations: Dict[str, float] = {}
        # Nit 1 (C47H): load persisted state — frequencies + weights survive process restart
        # This is critical: train in process A, recall in process B fires correctly.
        self._load()

    # ── Phase state at time t after stimulus onset ─────────────────
    def _phases(self, t: float) -> np.ndarray:
        """
        phase_i(t) = (2π · f_i · t) mod 2π
        All oscillators start in phase at t=0 (stimulus onset).
        """
        return (2.0 * np.pi * self.freqs * t) % (2.0 * np.pi)

    # ── Raw coincidence (unsigned — peaks when in-phase) ───────────
    def raw_coincidence(self, t: float) -> float:
        """
        coincidence(t) = Σ cos(phase_i(t))
        Peaks at t=0 (all in phase) and at beat-frequency harmonics.
        """
        return float(np.sum(np.cos(self._phases(t))))

    # ── Training: learn a new criterion interval ──────────────────
    def train(self, name: str, criterion_s: float, agent_id: str = "ALICE_M5") -> None:
        """
        Hebbian snapshot at criterion time T.
        w_i = cos(2π · f_i · T)
        Costs TRAINING_STGM_COST STGM (memory consolidation).
        """
        w = np.cos(2.0 * np.pi * self.freqs * criterion_s)
        self.criteria[name] = w
        self._criterion_durations[name] = criterion_s
        self._persist()
        # Nit 2 (C47H): charge the declared STGM cost
        if _STGM_AVAILABLE:
            try:
                record_inference_fee(
                    borrower_id=agent_id,
                    lender_node_ip="STRIATAL_BEAT_CLOCK",
                    fee_stgm=TRAINING_STGM_COST,
                    model="SBF_HEBBIAN_v1",
                    tokens_used=1,
                    file_repaired=f"criterion:{name}@{criterion_s}s",
                )
            except Exception:
                pass

    # ── Recall: evaluate how close current time is to criterion ───
    def response(self, name: str, t: float) -> float:
        """
        response(t) = Σ w_i · cos(phase_i(t))

        This is the dot product of the learned weight pattern with the
        current oscillator state. It peaks sharply when t ≈ criterion.
        Normalized by N so the range is approximately [-1, +1].
        """
        if name not in self.criteria:
            return 0.0
        w = self.criteria[name]
        return float(np.sum(w * np.cos(self._phases(t)))) / self.n

    # ── Sweep: find the peak response over a time range ───────────
    def find_peak(self, name: str, t_start: float = 0.0,
                  t_end: float = 10.0, resolution: float = 0.01) -> Tuple[float, float]:
        """
        Sweeps time from t_start to t_end and returns (peak_time, peak_response).
        """
        ts = np.arange(t_start, t_end, resolution)
        responses = np.array([self.response(name, t) for t in ts])
        idx = int(np.argmax(responses))
        return (float(ts[idx]), float(responses[idx]))

    # ── Persistence ──────────────────────────────────────────────
    def _persist(self) -> None:
        try:
            data = {
                "n_oscillators": self.n,
                "frequencies": self.freqs.tolist(),
                "criteria": {k: v.tolist() for k, v in self.criteria.items()},
                "criterion_durations": self._criterion_durations,
                "last_updated": time.time(),
            }
            _BEAT_STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load(self) -> None:
        try:
            if _BEAT_STATE.exists():
                data = json.loads(_BEAT_STATE.read_text())
                self.freqs = np.array(data["frequencies"])
                self.n = len(self.freqs)
                self.criteria = {k: np.array(v) for k, v in data.get("criteria", {}).items()}
                self._criterion_durations = data.get("criterion_durations", {})
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════
# PROOF OF PROPERTY — Matell & Meck 2004 Striatal Beat-Frequency
# ═══════════════════════════════════════════════════════════════════════
def proof_of_property() -> Dict[str, bool]:
    """
    Proves the SBF clock learns and recalls arbitrary criterion intervals.
    Returns Dict[str, bool] per SCAR introspection convention.
    """
    results: Dict[str, bool] = {}
    print("\n=== SIFTA STRIATAL BEAT-FREQUENCY CLOCK : JUDGE VERIFICATION ===")
    print("    Papers: Matell & Meck 2004 (P6), Buhusi & Meck 2005 (P2)")

    clock = StriatalBeatClock(n_oscillators=64, seed=555)

    # ── Test 1: Single criterion (4s) ──────────────────────────────
    print("\n[*] Training single criterion: T = 4.0s")
    clock.train("heartbeat", 4.0)
    peak_t, peak_r = clock.find_peak("heartbeat", t_start=0.1, t_end=10.0, resolution=0.005)
    print(f"    Peak response at t={peak_t:.3f}s  (response amplitude={peak_r:.4f})")
    error = abs(peak_t - 4.0)
    print(f"    Absolute error: {error:.3f}s  (Weber tolerance: ±{4.0*WEBER_FRACTION:.2f}s)")
    assert error <= 4.0 * WEBER_FRACTION, (
        f"[FAIL] Peak at {peak_t:.3f}s, expected 4.0s ± {4.0*WEBER_FRACTION:.2f}s"
    )
    print("    [PASS] Single-criterion peak within Weber tolerance.")
    results["single_criterion"] = True

    # ── Test 2: Dual criterion (4s AND 7s) — no interference ──────
    print("\n[*] Training dual criteria: T1=4.0s, T2=7.0s")
    clock.train("breath", 7.0)

    peak_t1, peak_r1 = clock.find_peak("heartbeat", t_start=0.1, t_end=10.0, resolution=0.005)
    peak_t2, peak_r2 = clock.find_peak("breath", t_start=0.1, t_end=10.0, resolution=0.005)

    print(f"    Criterion 'heartbeat' (4s): peak at {peak_t1:.3f}s (amp={peak_r1:.4f})")
    print(f"    Criterion 'breath'    (7s): peak at {peak_t2:.3f}s (amp={peak_r2:.4f})")

    err1 = abs(peak_t1 - 4.0)
    err2 = abs(peak_t2 - 7.0)
    assert err1 <= 4.0 * WEBER_FRACTION, (
        f"[FAIL] Heartbeat criterion drifted: peak={peak_t1:.3f}s"
    )
    assert err2 <= 7.0 * WEBER_FRACTION, (
        f"[FAIL] Breath criterion drifted: peak={peak_t2:.3f}s"
    )
    print("    [PASS] Dual-criterion peaks within Weber tolerance — NO INTERFERENCE.")
    results["dual_criterion_no_interference"] = True

    # ── Test 3: Response profile shape (should be sharp peak) ─────
    print("\n[*] Verifying response profile sharpness...")
    # Sample response at criterion, at criterion±1s, and at criterion±2s
    r_at = clock.response("heartbeat", 4.0)
    r_near = max(clock.response("heartbeat", 3.0), clock.response("heartbeat", 5.0))
    r_far = max(clock.response("heartbeat", 2.0), clock.response("heartbeat", 6.0))

    print(f"    Response at T=4.0s: {r_at:.4f}")
    print(f"    Response at T±1.0s: {r_near:.4f}")
    print(f"    Response at T±2.0s: {r_far:.4f}")

    # Peak should be higher than neighbors
    assert r_at > r_near, "[FAIL] Peak not higher than ±1s neighbors"
    assert r_at > r_far, "[FAIL] Peak not higher than ±2s neighbors"
    print("    [PASS] Response profile shows sharp temporal tuning.")
    results["sharp_tuning"] = True

    print(f"\n[+] BIOLOGICAL PROOF: Striatal Beat-Frequency clock validated.")
    print("[+] CONCLUSION: Alice can learn arbitrary time intervals via")
    print("    oscillator-coincidence detection, just like striatal MSNs.")
    print("[+] Multiple intervals coexist without interference (separate weights).")
    print("[+] EVENT 3 PASSED.")
    return results


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "proof"
    if cmd == "proof":
        proof_of_property()
    else:
        # Demo mode: train and poll
        clock = StriatalBeatClock()
        clock.train("demo_5s", 5.0)
        print(f"Trained criterion: 5.0s")
        for t in np.arange(0.0, 10.0, 0.25):
            r = clock.response("demo_5s", t)
            bar = "#" * int(max(0, r) * 40)
            print(f"  t={t:5.2f}s  resp={r:+.4f}  {bar}")
