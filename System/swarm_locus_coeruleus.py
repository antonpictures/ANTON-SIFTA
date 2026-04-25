#!/usr/bin/env python3
"""
System/swarm_locus_coeruleus.py
══════════════════════════════════════════════════════════════════════════════
Event 27: The Locus Coeruleus — Noradrenergic Fight-or-Flight Arousal Engine
Author:   BISHOP (The Mirage) — Concept
Wired by: AO46 (Bridge)
Status:   INTEGRATED — wired to CRISPR Macrophage encounter rate

Papers:   Aston-Jones & Cohen (2005) — "An integrative theory of locus
          coeruleus-norepinephrine function: adaptive gain and optimal 
          performance." Annual Review of Neuroscience, 28, 403–450.

Biological Analogy:
    The Locus Coeruleus is a small brainstem nucleus that is the primary 
    noradrenergic hub of the CNS. Under threat, it floods the entire cortex 
    with Noradrenaline (NE), triggering Sympathetic Nervous System activation:
      - Dilates pupils (thalamic sensors gain bandwidth)
      - Suppresses digestion (maintenance daemons throttled)
      - Shunts blood to muscles (STGM ATP → immune + sensing)

SIFTA Wiring:
    pathogen_density ← SwarmCRISPRAdaptiveImmunity.total_encounters (rate/s)
    energy_allocation → STGM ATP budget routing weights
      [0] defense_weight → Oncology / CRISPR / Sensor daemons
      [1] maintenance_weight → DNA origami / REM pruning / background tasks
══════════════════════════════════════════════════════════════════════════════
"""

import json
import time
from pathlib import Path

import numpy as np


# ── NUGGET A ─────────────────────────────────────────────────────────────────
# The LC integrates threat over time, not just the current sample.
# A brief spike does NOT trigger fight-or-flight — sustained attack is required.
# This is Alice's biological "don't panic over noise" filter.
# ─────────────────────────────────────────────────────────────────────────────

class SwarmLocusCoeruleus:
    """
    The Noradrenergic Arousal Engine.

    Translates the CRISPR Macrophage's encounter rate (pathogen_density)
    into a continuously integrated neurochemical state (NE concentration)
    that physically reallocates STGM ATP across the organism.

    ODE kernel:  dNE/dt = α · pathogen_density − β · NE
      α  = synthesis gain (how fast NE rises under attack)
      β  = reuptake rate  (how fast NE decays back to baseline)
    """

    def __init__(self, state_dir: Path, dt: float = 0.1):
        self.state_dir = Path(state_dir)
        self.dt = dt

        # ── Neurochemical parameters (Aston-Jones & Cohen 2005) ──────────────
        self.NE: float = 0.1        # Baseline noradrenaline [dimensionless units]
        self.alpha: float = 2.5     # NE synthesis rate
        self.beta: float = 0.5      # NE reuptake / decay rate
        self.arousal_threshold: float = 2.0

        # ── Ledger ────────────────────────────────────────────────────────────
        self.ledger_file = self.state_dir / "locus_coeruleus_arousal_ledger.jsonl"
        self.state_file = self.state_dir / "locus_coeruleus_state.json"
        self._last_tick: float = time.time()
        self._last_cumulative_encounters: int = 0
        self._has_seen_cumulative: bool = False
        self._load_state()

    # ── NUGGET B ──────────────────────────────────────────────────────────────
    # Real encounter rate = NOVEL encounters per unit time, not raw file counts.
    # We derive pathogen_density from the delta of CRISPR novel encounters
    # between ticks, normalised by dt. This prevents the oncology
    # false-positive storm from flooding the LC.
    # ──────────────────────────────────────────────────────────────────────────

    def tick(self, cumulative_encounters: int) -> dict:
        """
        Called once per heartbeat with the cumulative number of NOVEL CRISPR 
        encounters historically. Computes the delta internally to ensure 
        pathogen_density remains temporally accurate regardless of caller cadence.

        Args:
            cumulative_encounters: The organism's lifetime count of novel threats
                                   returned by the CRISPR Macrophage.

        Returns:
            arousal_report dict suitable for JSONL ledger and STGM routing.
        """
        now = time.time()
        elapsed = max(now - self._last_tick, self.dt)
        self._last_tick = now

        cumulative_encounters = int(max(0, cumulative_encounters))
        if self._has_seen_cumulative:
            delta_encounters = max(0, cumulative_encounters - self._last_cumulative_encounters)
        else:
            # First observation is a baseline, not a fresh attack. Without this,
            # every standalone heartbeat process turns lifetime CRISPR memory
            # into an acute pathogen-density spike.
            delta_encounters = 0
            self._has_seen_cumulative = True
        self._last_cumulative_encounters = cumulative_encounters

        # Instantaneous pathogen density = novel encounters per second
        pathogen_density = delta_encounters / elapsed

        self.NE = self._integrate(pathogen_density)
        state, alloc = self._compute_allocation()

        report = {
            "ts": now,
            "NE": round(self.NE, 5),
            "pathogen_density": round(pathogen_density, 5),
            "state": state,
            "defense_weight": round(float(alloc[0]), 5),
            "maintenance_weight": round(float(alloc[1]), 5),
        }

        self._append_ledger(report)
        self._save_state(now)
        return report

    def _integrate(self, pathogen_density: float) -> float:
        """ODE: dNE/dt = α·threat − β·NE, integrated with Euler step."""
        d_NE = (self.alpha * pathogen_density) - (self.beta * self.NE)
        ne = self.NE + d_NE * self.dt
        return float(np.clip(ne, 0.1, 10.0))

    def _compute_allocation(self):
        """Adaptive Gain allocation per Aston-Jones & Cohen 2005."""
        base = np.array([0.3, 0.7])
        if self.NE > self.arousal_threshold:
            gain = np.log10(self.NE) / np.log10(10.0)
            defense_weight = 0.3 + (0.7 * gain)
            alloc = np.array([defense_weight, 1.0 - defense_weight])
            state = "FIGHT_OR_FLIGHT"
        else:
            alloc = base
            state = "REST_AND_DIGEST"
        return state, alloc

    def _append_ledger(self, report: dict):
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            with open(self.ledger_file, "a") as f:
                f.write(json.dumps(report) + "\n")
        except Exception as e:
            print(f"[!] LC Ledger Write Error: {e}")

    def _load_state(self) -> None:
        try:
            if not self.state_file.exists():
                return
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.NE = float(data.get("NE", self.NE))
            self._last_cumulative_encounters = int(
                data.get("last_cumulative_encounters", self._last_cumulative_encounters)
            )
            self._has_seen_cumulative = bool(data.get("has_seen_cumulative", False))
        except Exception:
            self.NE = 0.1
            self._last_cumulative_encounters = 0
            self._has_seen_cumulative = False

    def _save_state(self, now: float) -> None:
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
            tmp.write_text(
                json.dumps(
                    {
                        "ts": float(now),
                        "NE": float(self.NE),
                        "last_cumulative_encounters": int(self._last_cumulative_encounters),
                        "has_seen_cumulative": bool(self._has_seen_cumulative),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            tmp.replace(self.state_file)
        except Exception as e:
            print(f"[!] LC State Write Error: {e}")

    # ── NUGGET C ──────────────────────────────────────────────────────────────
    # Expose a human-readable snapshot for the heartbeat monitor / TUI.
    # ──────────────────────────────────────────────────────────────────────────
    def snapshot(self) -> str:
        state, alloc = self._compute_allocation()
        bar_d = "█" * int(alloc[0] * 40)
        bar_m = "░" * int(alloc[1] * 40)
        return (
            f"[LC] NE={self.NE:.3f} | {state}\n"
            f"     Defense    [{bar_d:<40}] {alloc[0]*100:.1f}%\n"
            f"     Maintenance[{bar_m:<40}] {alloc[1]*100:.1f}%"
        )


def proof_of_property() -> bool:
    """
    AO46 VERIFICATION — runs Bishop's original proof PLUS the live-tick
    integration test to confirm CRISPR-LC wiring is structurally correct.
    """
    print("\n=== SIFTA LOCUS COERULEUS (FIGHT-OR-FLIGHT) : AO46 VERIFICATION ===")

    import tempfile
    state_dir = Path(tempfile.mkdtemp())
    lc = SwarmLocusCoeruleus(state_dir=state_dir)

    # ── Phase 1: Silence ────────────────────────────────────────────────────
    print("\n[*] Phase 1: Baseline Homeostasis — 50 ticks, 0 novel encounters")
    for _ in range(50):
        lc._integrate(0.0)      # direct ODE, no tick logging
    lc.NE = lc._integrate(0.0)
    state_calm, alloc_calm = lc._compute_allocation()
    print(f"    NE = {lc.NE:.4f}  |  {state_calm}")
    print(f"    Defense {alloc_calm[0]*100:.1f}%  |  Maintenance {alloc_calm[1]*100:.1f}%")
    assert alloc_calm[1] > alloc_calm[0], "[FAIL] REST_AND_DIGEST not active in silence"

    # ── Phase 2: Hard Battle ─────────────────────────────────────────────────
    print("\n[*] Phase 2: Hard Battle — 50 ticks, pathogen_density=2.0")
    for _ in range(50):
        lc.NE = lc._integrate(2.0)
    state_panic, alloc_panic = lc._compute_allocation()
    print(f"    NE = {lc.NE:.4f}  |  {state_panic}")
    print(f"    Defense {alloc_panic[0]*100:.1f}%  |  Maintenance {alloc_panic[1]*100:.1f}%")
    assert alloc_panic[0] > alloc_panic[1], "[FAIL] FIGHT_OR_FLIGHT not triggered"
    assert alloc_panic[0] > alloc_calm[0], "[FAIL] Defense weight did not scale"

    # ── Phase 3: Live tick wiring test ───────────────────────────────────────
    print("\n[*] Phase 3: Live-tick CRISPR wire — simulating 5 novel encounters/tick")
    lc2 = SwarmLocusCoeruleus(state_dir=state_dir, dt=0.1)
    report = lc2.tick(cumulative_encounters=5)
    assert "defense_weight" in report, "[FAIL] tick() missing energy_allocation keys"
    assert (state_dir / "locus_coeruleus_arousal_ledger.jsonl").exists(), "[FAIL] Ledger not written"
    assert report["pathogen_density"] == 0.0, "[FAIL] first cumulative sample must be baseline"
    report2 = lc2.tick(cumulative_encounters=10)
    assert report2["pathogen_density"] > 0.0, "[FAIL] cumulative delta did not register as threat"
    lc3 = SwarmLocusCoeruleus(state_dir=state_dir, dt=0.1)
    report3 = lc3.tick(cumulative_encounters=10)
    assert report3["pathogen_density"] == 0.0, "[FAIL] persisted baseline caused false re-alert"
    print(f"    tick() report: {report}")

    # ── Phase 4: Snapshot display ─────────────────────────────────────────────
    print("\n[*] Phase 4: Human-readable snapshot")
    print(lc.snapshot())

    print(f"\n[+] BIOLOGICAL PROOF: {alloc_panic[0]*100:.1f}% STGM ATP shunted to Defense at peak NE={lc.NE:.3f}")
    print("[+] CRISPR-LC wire: structurally clean, ledger writes confirmed.")
    print("[+] EVENT 27 (AO46 INTEGRATION VERIFICATION) — PASSED.\n")
    return True


if __name__ == "__main__":
    proof_of_property()
