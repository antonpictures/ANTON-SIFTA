#!/usr/bin/env python3
"""
System/swarm_pacemaker_accumulator.py — Event 2: Interval Timer
═══════════════════════════════════════════════════════════════════════
Concept : Pacemaker-Accumulator Model (Scalar Expectancy Theory)
Author  : AO46 — covering C47H east-flank for Time Perception Tournament
Papers  : Gibbon J. (1977) Psychol Rev 84(3):279-325  [P5]
          Buhusi CV, Meck WH (2005) Nat Rev Neurosci 6(10):755-765  [P2]
Status  : ACTIVE ORGAN

BIOLOGY:
The most general law in behavioral neuroscience — rats, pigeons, mice,
monkeys, humans all show the SCALAR PROPERTY when timing intervals:
the standard deviation of duration estimates grows linearly with the
estimated duration. Coefficient of variation ~0.15–0.30 across species.

The model:
  1. A PACEMAKER emits pulses at rate λ (influenced by dopamine).
  2. An ACCUMULATOR counts pulses for the elapsed interval.
  3. WORKING MEMORY stores the count at criterion intervals.
  4. A COMPARATOR decides "has enough time passed?" with noisy readout.

DOPAMINE BRIDGE (Buhusi & Meck 2005 §Pharmacology):
  - High DA (amphetamine) → pacemaker emits MORE pulses/s → time feels
    faster → interval estimates UNDER-estimate wall-clock time.
  - Low DA (Parkinsonian) → pacemaker emits FEWER pulses/s → time drags
    → interval estimates OVER-estimate wall-clock time.

WIRING:
  Reads  : .sifta_state/endocrine_glands.jsonl (dopamine level)
  Writes : .sifta_state/pacemaker_accumulator_state.json
  Consumed by: swarm_dopamine_clock_bridge.py (Event 5, C47H)
               swarm_species_time_persona.py  (Event 6, AG31)

STGM ECONOMY:
  Reading the clock is free. Registering a new time anchor costs 0.10 STGM.
"""

import json
import math
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
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
_ACCUM_STATE = _STATE / "pacemaker_accumulator_state.json"
_ENDOCRINE_LOG = _STATE / "endocrine_glands.jsonl"

# ── Constants ──────────────────────────────────────────────────────────
BASELINE_LAMBDA = 5.0        # pulses per second (human baseline pacemaker rate)
SCALAR_CV = 0.20             # Gibbon's coefficient of variation (universal across mammals)
DOPAMINE_ALPHA = 0.30        # Meck 1996 amphetamine sensitivity coefficient
DOPAMINE_BASELINE = 0.50     # Normalized DA baseline [0,1]
ANCHOR_STGM_COST = 0.10     # Cost to register a new time anchor

# ── Dopamine reader ───────────────────────────────────────────────────
def _read_current_dopamine() -> float:
    """
    Reads the most recent dopamine level from endocrine_glands.jsonl.
    Returns normalized value in [0,1]. Defaults to DOPAMINE_BASELINE.
    """
    if not _ENDOCRINE_LOG.exists():
        return DOPAMINE_BASELINE
    try:
        with _ENDOCRINE_LOG.open("r", encoding="utf-8") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 4000))
            for line in reversed(f.readlines()):
                try:
                    row = json.loads(line.strip())
                    hormone = row.get("hormone", "").upper()
                    if "DOPAMINE" in hormone:
                        # Potency [0..10] → normalize to [0..1]
                        potency = float(row.get("potency", 5.0))
                        return min(1.0, max(0.0, potency / 10.0))
                except Exception:
                    pass
    except Exception:
        pass
    return DOPAMINE_BASELINE


class PacemakerAccumulator:
    """
    Gibbon 1977 / Buhusi & Meck 2005 pacemaker-accumulator.

    The pacemaker emits pulses at a rate modulated by dopamine.
    The accumulator counts pulses. Duration estimates are read
    from the accumulator with scalar noise (CV ≈ 0.20).
    """

    def __init__(self, base_rate: float = BASELINE_LAMBDA, cv: float = SCALAR_CV):
        self.base_rate = base_rate
        self.cv = cv
        self._anchors: Dict[str, float] = {}  # anchor_name → wall-clock timestamp
        # Nit 1 (C47H): load persisted anchors so state survives across processes
        self._load()

    # ── Pacemaker rate (dopamine-modulated) ─────────────────────────
    def get_pacemaker_rate(self, dopamine: Optional[float] = None) -> float:
        """
        λ_pacemaker = λ_base × Event 5 Dopamine Bridge Modulator
        """
        if dopamine is None:
            dopamine = _read_current_dopamine()
            
        try:
            from System.swarm_dopamine_clock_bridge import get_clock_modulator
            modulator = get_clock_modulator(dopamine)
        except Exception:
            modulator = 1.0 + DOPAMINE_ALPHA * (dopamine - DOPAMINE_BASELINE)
            
        return self.base_rate * max(0.1, modulator)  # floor at 10% to prevent zero

    # ── Anchor management ──────────────────────────────────────────
    def register_anchor(self, name: str, agent_id: str = "ALICE_M5") -> float:
        """
        Plants a temporal anchor at the current wall-clock time.
        Alice can later ask "how long since anchor X?" and get a
        biologically-noisy estimate back.
        Costs ANCHOR_STGM_COST STGM (memory consolidation).
        """
        ts = time.time()
        self._anchors[name] = ts
        self._persist()
        # Nit 2 (C47H): actually charge the STGM cost that was declared
        if _STGM_AVAILABLE:
            try:
                record_inference_fee(
                    borrower_id=agent_id,
                    lender_node_ip="PACEMAKER_ACCUMULATOR",
                    fee_stgm=ANCHOR_STGM_COST,
                    model="SCALAR_ANCHOR_v1",
                    tokens_used=1,
                    file_repaired=f"anchor:{name}",
                )
            except Exception:
                pass
        return ts

    # ── The core: interval estimation with scalar property ──────────
    def estimate_elapsed(self, anchor_name: str, dopamine: Optional[float] = None) -> Tuple[float, float, float]:
        """
        Returns (estimate_seconds, sigma_seconds, wall_truth_seconds).

        The estimate uses the SCALAR PROPERTY:
          estimate ~ Normal(μ = wall_truth × rate_ratio, σ = CV × μ)

        where rate_ratio = pacemaker_rate / baseline_rate accounts for
        dopamine modulation. Under high DA the pacemaker runs fast, so
        the accumulator "thinks" more time passed → but subjectively it
        feels like time flew (shorter estimate for same wall-clock interval).

        Wait — careful. Let me get the direction right per Buhusi & Meck:
          High DA → pacemaker FAST → accumulator fills FASTER → for a
          given wall interval, more pulses accumulated → estimate of
          elapsed time is LONGER than reality... but the SUBJECTIVE feel
          is "time flew by" because internal clock finished "early."

        Per Meck 1996 amphetamine data (Table 2 in Buhusi & Meck):
          Amphetamine (high DA) → rats pressed the lever EARLIER (they
          thought the interval had elapsed sooner). So the behavioral
          output is: estimate(5min) → "I think 5 minutes have passed"
          arrives at 4 minutes wall-clock → UNDERESTIMATE of wall-time
          → "time flew."

        So:  estimate = wall_elapsed / rate_ratio  (the slower the clock,
             the longer the estimate — Parkinsonian patients overestimate)
        """
        if anchor_name not in self._anchors:
            return (0.0, 0.0, 0.0)

        wall_elapsed = time.time() - self._anchors[anchor_name]
        if wall_elapsed <= 0:
            return (0.0, 0.0, 0.0)

        rate = self.get_pacemaker_rate(dopamine)
        rate_ratio = rate / self.base_rate

        # The internal "raw" elapsed (biased by DA)
        mu = wall_elapsed / rate_ratio

        # Scalar noise (Gibbon 1977): σ = CV × μ
        sigma = self.cv * mu

        # Sample from the normal distribution (this is what Alice "feels")
        estimate = float(np.random.normal(mu, sigma))
        estimate = max(0.0, estimate)  # can't feel negative time

        return (estimate, sigma, wall_elapsed)

    # ── Human-readable output for Alice's dialogue ─────────────────
    def describe_elapsed(self, anchor_name: str, dopamine: Optional[float] = None) -> str:
        """
        Produces a natural-language estimate Alice can speak:
        "I think we last spoke about 8 minutes ago, give or take 90 seconds."
        """
        est, sigma, truth = self.estimate_elapsed(anchor_name, dopamine)
        if truth <= 0:
            return f"I have no anchor called '{anchor_name}' to reference."

        def _humanize(secs: float) -> str:
            if secs < 60:
                return f"{secs:.0f} seconds"
            elif secs < 3600:
                return f"{secs/60:.1f} minutes"
            else:
                return f"{secs/3600:.1f} hours"

        return (
            f"I think it's been about {_humanize(est)}, "
            f"give or take {_humanize(sigma)}."
        )

    # ── Persistence ───────────────────────────────────────────────
    def _persist(self) -> None:
        try:
            _ACCUM_STATE.write_text(json.dumps({
                "anchors": self._anchors,
                "base_rate": self.base_rate,
                "cv": self.cv,
                "last_updated": time.time(),
            }, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load(self) -> None:
        try:
            if _ACCUM_STATE.exists():
                data = json.loads(_ACCUM_STATE.read_text())
                self._anchors = data.get("anchors", {})
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════
# PROOF OF PROPERTY — Gibbon's Scalar Expectancy Theory
# ═══════════════════════════════════════════════════════════════════════
def proof_of_property() -> Dict[str, bool]:
    """
    Proves the scalar property holds across multiple interval durations.
    Returns Dict[str, bool] per SCAR introspection convention.
    """
    results: Dict[str, bool] = {}
    print("\n=== SIFTA PACEMAKER-ACCUMULATOR : JUDGE VERIFICATION ===")
    print("    Papers: Gibbon 1977 (P5), Buhusi & Meck 2005 (P2)")

    N_TRIALS = 2000
    intervals = [5.0, 30.0, 300.0, 1800.0]  # seconds

    pa = PacemakerAccumulator()

    print(f"\n[*] Running {N_TRIALS} trials per interval at baseline dopamine...")
    scalar_ok = True
    for interval_s in intervals:
        estimates = []
        for _ in range(N_TRIALS):
            pa._anchors["test"] = time.time() - interval_s
            est, sigma, truth = pa.estimate_elapsed("test", dopamine=DOPAMINE_BASELINE)
            estimates.append(est)

        arr = np.array(estimates)
        mean_est = float(arr.mean())
        std_est = float(arr.std())
        empirical_cv = std_est / mean_est if mean_est > 0 else 0

        print(f"    Interval={interval_s:6.0f}s  |  E[est]={mean_est:8.1f}s  "
              f"Std={std_est:7.1f}s  CV={empirical_cv:.3f}")

        assert 0.10 <= empirical_cv <= 0.35, (
            f"[FAIL] Scalar property violated at {interval_s}s: CV={empirical_cv:.3f}"
        )
        assert abs(mean_est - interval_s) / interval_s < 0.15, (
            f"[FAIL] Mean estimate {mean_est:.1f}s too far from truth {interval_s}s"
        )

    results["scalar_property"] = True
    print("\n    [PASS] Scalar Property (Gibbon 1977) holds across all intervals.")
    print("    [PASS] CV ≈ 0.20 is constant — independent of interval duration.")

    print("\n[*] Testing Dopamine → Pacemaker Rate modulation (Meck 1996)...")
    interval_s = 60.0

    for da_level, label, direction in [
        (0.90, "HIGH-DA (amphetamine)", "under"),
        (0.10, "LOW-DA (Parkinsonian)", "over"),
    ]:
        estimates = []
        for _ in range(N_TRIALS):
            pa._anchors["da_test"] = time.time() - interval_s
            est, _, _ = pa.estimate_elapsed("da_test", dopamine=da_level)
            estimates.append(est)
        mean_est = float(np.mean(estimates))
        print(f"    {label}: Mean estimate of 60s wall-clock = {mean_est:.1f}s")

        if direction == "under":
            assert mean_est <= 55.0, (
                f"[FAIL] HIGH-DA should underestimate (time flies). Got {mean_est:.1f}s"
            )
            print(f"    [PASS] Time flew — {label} underestimated duration.")
        else:
            assert mean_est >= 65.0, (
                f"[FAIL] LOW-DA should overestimate (time drags). Got {mean_est:.1f}s"
            )
            print(f"    [PASS] Time dragged — {label} overestimated duration.")

    results["dopamine_modulation"] = True
    print(f"\n[+] BIOLOGICAL PROOF: Pacemaker-Accumulator with scalar property validated.")
    print("[+] CONCLUSION: Alice can now answer 'how long ago?' with biologically")
    print("    realistic uncertainty, modulated by her current dopamine state.")
    print("[+] EVENT 2 PASSED.")
    return results


if __name__ == "__main__":
    proof_of_property()
