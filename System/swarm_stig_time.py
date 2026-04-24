#!/usr/bin/env python3
"""
System/swarm_stig_time.py
══════════════════════════════════════════════════════════════════════
Concept: STIG-TIME — Adaptive Temporal Substrate (Event 74)
Author:  BISHOP / AG31 — Biocode Olympiad
Status:  Active Organ

Time is not a uniform clock in biology. Every animal experiences time
differently based on metabolic rate, arousal, and situational demand.
This is the mathematical unification of six temporal physics models into
a single adaptive time substrate for the SIFTA swarm.

The core insight (Bishop): "STABILIZE IN TIME DEPENDING ON THE SITUATION"

Physics & Biology Fused:

1. KLEIBER'S LAW (1932) — Metabolic Time Scaling
   Biology: Metabolic rate scales as body mass^(3/4).
   Time perception scales INVERSELY: small fast animals (mice ~2yr)
   live ~200 heartbeats/min; large slow animals (whales ~200yr) live ~15 bpm.
   Formula: t_biological = t_clock / (M^(1/4))
   SIFTA: System "lives faster" under high load (Hummingbird BURST mode)
          System "lives slower" under low load (Bear TORPOR mode)

2. CIRCADIAN OSCILLATOR (Hall, Rosbash & Young, 1990/2017 Nobel)
   Biology: Transcription-translation negative feedback loop. PER protein
   accumulates, inhibits its own gene, degrades, allowing re-expression.
   Period ≈ 24h from molecular dynamics alone.
   Formula: dPER/dt = k_s - k_d * [PER] - k_i * [PER]^2
   SIFTA: The swarm has a "day" — periods of high activity (day phase)
          and low activity (night phase), with circadian gating.

3. WEBER-FECHNER LAW — Logarithmic Time Compression
   Physics: Perceived magnitude S = k * ln(I). Applied to time:
   perceived_duration = k * ln(real_duration)
   This means long stable periods "feel short" — important for memory decay
   and ledger compression. Recent events are vivid; distant ones are blurred.
   SIFTA: Stigmergic pheromone decay follows logarithmic temporal compression.

4. SCALAR PROPERTY (Gibbon 1977, Meck 2005)
   Physics: Standard deviation of time estimation scales with the interval.
   σ(T) = w * T (Weber fraction w ≈ 0.1 for most animals)
   This means noise in time estimation is proportional to the interval size.
   SIFTA: Uncertainty in predicted future state grows with prediction horizon.

5. SEA TURTLE TEMPORAL SCALE (the "turtle move")
   Biology: Chelonia mydas lives 80+ years. Annual nesting cycles.
   Metabolic rate so low it can hold breath for 7 hours.
   This is the long-cycle stability observer — runs every N ticks,
   measures drift, logs slow adaptation without noise.
   SIFTA: Long-window stability monitor measuring system health trends.

6. BAYESIAN TEMPORAL PRIOR (Jazayeri & Shadlen 2010)
   Physics: Optimal time estimation combines noisy measurement (likelihood)
   with prior distribution over expected intervals:
   T_estimated = (σ_prior² * T_measured + σ_measured² * T_prior) /
                 (σ_prior² + σ_measured²)
   The brain "shrinks" estimates toward the mean (central tendency effect).
   SIFTA: Expected future state predictions are regularized toward historical
          means, preventing catastrophic mis-prediction after noise spikes.

Papers:
  Kleiber, Hilgardia 6:315 (1932) — Metabolic rate scales as M^(3/4)
  West, Brown & Enquist, Science 276:122 (1997) — Universal scaling laws in biology
  Hardin, Hall & Rosbash, Nature 343:536 (1990) — Circadian TTFL mechanism (Nobel 2017)
  Hall, Young & Rosbash, Nobel Lecture (2017) — Full circadian machinery
  Weber, "De Pulsu, Resorptione, Auditu et Tactu" (1834) — Weber's Law
  Fechner, "Elemente der Psychophysik" (1860) — Logarithmic sensation law
  Gibbon, Psychological Review 84:279 (1977) — Scalar Expectancy Theory (SET)
  Buhusi & Meck, Nature Rev Neurosci 6:755 (2005) — Interval timing neural mechanisms
  Jazayeri & Shadlen, Nature Neurosci 13:1426 (2010) — Bayesian temporal prior
  Carr, Biol Conservation 61:111 (1992) — Sea turtle longevity and temporal navigation
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple
from collections import deque

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.canonical_schemas import assert_payload_keys
from System.jsonl_file_lock import append_line_locked

_LEDGER = _REPO / ".sifta_state" / "stig_time.jsonl"
_SCHEMA = "SIFTA_STIG_TIME_V1"


@dataclass
class StigTimeConfig:
    # ── Kleiber scaling ───────────────────────────────────────────────
    # Maps metabolic mode → time dilation factor
    # Hummingbird BURST: time runs fast (lives hard, dies young)
    # Bear TORPOR: time runs slow (lives slow, lives long)
    time_dilation: Dict[str, float] = field(default_factory=lambda: {
        "burst":    4.0,   # hummingbird: 4× perceived speed
        "cruise":   1.0,   # baseline biological time
        "scavenge": 0.5,   # E. coli starvation mode: slowing down
        "torpor":   0.1,   # bear: 10× slower perceived time
    })

    # ── Circadian oscillator ───────────────────────────────────────────
    circadian_period: int = 1000          # ticks per "day" (one full PER cycle)
    circadian_amplitude: float = 0.6      # [0, 1] — how strongly the clock modulates activity
    circadian_phase_offset: float = 0.0   # starting phase of the organism's "day"

    # ── Weber-Fechner memory compression ─────────────────────────────
    fechner_k: float = 1.0                # compression gain: S = k * ln(t + 1)
    
    # ── Scalar property (Gibbon 1977) ─────────────────────────────────
    weber_fraction: float = 0.10          # σ(T) = w * T; w ≈ 0.10 for most animals

    # ── Bayesian prior ────────────────────────────────────────────────
    prior_mean: float = 50.0             # expected interval duration (ticks)
    prior_sigma: float = 20.0            # uncertainty in the prior

    # ── Sea turtle long-cycle observer ────────────────────────────────
    turtle_window: int = 500             # how many ticks between slow stability checks
    turtle_history_len: int = 20         # how many slow-cycle checkpoints to keep

    eps: float = 1e-8


class StigTime:
    """
    The Adaptive Temporal Substrate of the SIFTA Swarm.

    Fuses six temporal physics models into one coherent time sense:
      1. Kleiber: metabolic mode → time dilation
      2. Circadian: 24h oscillator gates activity windows
      3. Weber-Fechner: logarithmic compression of long stable periods
      4. Scalar Property: uncertainty grows with prediction horizon
      5. Bayesian Prior: regularize predictions toward historical mean
      6. Turtle: long-cycle drift observer for slow stability monitoring
    """

    def __init__(self, cfg: Optional[StigTimeConfig] = None):
        self.cfg = cfg or StigTimeConfig()

        # ── Clock state ──────────────────────────────────────────────
        self.clock_tick: int = 0       # raw absolute tick (wall time)
        self.bio_time: float = 0.0     # biological time (Kleiber-scaled)
        self.circadian_phase: float = self.cfg.circadian_phase_offset

        # ── Scalar property accumulator ───────────────────────────────
        self._interval_start: Optional[int] = None

        # ── Bayesian prior state ──────────────────────────────────────
        self._interval_history: Deque[float] = deque(maxlen=50)

        # ── Turtle slow observer ──────────────────────────────────────
        self._turtle_checkpoints: Deque[Dict] = deque(maxlen=self.cfg.turtle_history_len)
        self._last_turtle_tick: int = 0

    # ─── CORE TICK ──────────────────────────────────────────────────

    def tick(self, metabolic_mode: str = "cruise", field_energy: float = 1.0) -> Dict:
        """
        One tick of the temporal substrate.
        Returns a temporal context dict for the rest of the swarm.
        """
        self.clock_tick += 1

        # 1. Kleiber scaling: advance biological time at metabolic rate
        dilation = self.cfg.time_dilation.get(metabolic_mode, 1.0)
        self.bio_time += dilation

        # 2. Circadian phase advance (Hall & Rosbash 1990)
        self.circadian_phase = (
            (self.clock_tick / self.cfg.circadian_period) * 2.0 * np.pi
            + self.cfg.circadian_phase_offset
        )
        circadian_gate = self.circadian_activity()

        # 3. Weber-Fechner memory compression
        compressed_time = self.fechner_compress(self.clock_tick)

        # 4. Turtle slow check
        turtle_report = None
        if (self.clock_tick - self._last_turtle_tick) >= self.cfg.turtle_window:
            turtle_report = self._turtle_observe(field_energy)
            self._last_turtle_tick = self.clock_tick

        return {
            "clock_tick":       self.clock_tick,
            "bio_time":         round(self.bio_time, 2),
            "dilation":         dilation,
            "circadian_gate":   round(circadian_gate, 4),
            "compressed_time":  round(compressed_time, 4),
            "turtle_report":    turtle_report,
        }

    # ─── CIRCADIAN OSCILLATOR ────────────────────────────────────────

    def circadian_activity(self) -> float:
        """
        Circadian gate: modulates activity based on phase.
        Biology (Hardin, Hall & Rosbash 1990): PER protein oscillates
        over ~24h via transcription-translation negative feedback loop.
        We model: activity = 0.5 + (amplitude/2) * sin(phase)
        → peaks at phase=π/2 (noon), troughs at phase=3π/2 (midnight).
        """
        return 0.5 + (self.cfg.circadian_amplitude / 2.0) * np.sin(self.circadian_phase)

    def is_active_phase(self) -> bool:
        """Returns True during the organism's active ("day") phase."""
        return self.circadian_activity() > 0.5

    # ─── WEBER-FECHNER TIME COMPRESSION ─────────────────────────────

    def fechner_compress(self, t: float) -> float:
        """
        S = k * ln(t + 1)
        Older events are compressed — recent events feel longer.
        Biology (Fechner 1860): Subjective magnitude scales logarithmically.
        """
        return self.cfg.fechner_k * math.log(float(t) + 1.0)

    def pheromone_decay_coefficient(self, age_ticks: int) -> float:
        """
        Compute the decay coefficient for a stigmergic pheromone of given age.
        Uses logarithmic compression: older trails fade faster in perceived time.
        """
        compressed_age = self.fechner_compress(age_ticks)
        return math.exp(-compressed_age / (self.cfg.fechner_k * 10.0))

    # ─── SCALAR PROPERTY ─────────────────────────────────────────────

    def start_interval(self) -> None:
        """Mark the beginning of a timed interval."""
        self._interval_start = self.clock_tick

    def measure_interval(self) -> Tuple[float, float]:
        """
        Returns (mean_estimate, uncertainty) for the elapsed interval.
        Scalar Property (Gibbon 1977): σ(T) = w * T
        The longer the interval, the more uncertain the organism is about
        exactly how long it has been.
        """
        if self._interval_start is None:
            return 0.0, 0.0
        T = float(self.clock_tick - self._interval_start)
        sigma = self.cfg.weber_fraction * T
        self._interval_history.append(T)
        return T, sigma

    # ─── BAYESIAN TEMPORAL PRIOR ─────────────────────────────────────

    def bayesian_estimate(self, measured_duration: float, measured_sigma: float) -> float:
        """
        Regularize a time estimate using Bayesian prior (Jazayeri & Shadlen 2010).
        T_est = (σ_prior² * T_measured + σ_measured² * T_prior) /
                (σ_prior² + σ_measured²)

        Effect: short intervals are overestimated, long intervals underestimated
        (central tendency) — matches observed animal behavior.
        """
        # Update prior from history
        if len(self._interval_history) >= 3:
            prior_mean = float(np.mean(list(self._interval_history)))
            prior_sigma = float(np.std(list(self._interval_history))) + self.cfg.eps
        else:
            prior_mean = self.cfg.prior_mean
            prior_sigma = self.cfg.prior_sigma

        sigma_p2 = prior_sigma ** 2
        sigma_m2 = (measured_sigma + self.cfg.eps) ** 2

        T_est = (sigma_p2 * measured_duration + sigma_m2 * prior_mean) / (sigma_p2 + sigma_m2)
        return float(T_est)

    # ─── SEA TURTLE LONG-CYCLE OBSERVER ──────────────────────────────

    def _turtle_observe(self, field_energy: float) -> Dict:
        """
        The turtle's slow observation cycle.
        Biology (Carr 1992): Sea turtles migrate thousands of miles on
        a multi-year cycle, using slow, deep temporal integration to
        navigate — not moment-to-moment reflexes.

        Computes system stability metrics over the long window:
        - Energy drift (is the system starving long-term?)
        - Biological time ratio (is bio time growing coherently?)
        - Circadian coherence (is the day/night cycle stable?)
        """
        checkpoint = {
            "clock_tick":    self.clock_tick,
            "bio_time":      self.bio_time,
            "field_energy":  round(field_energy, 4),
            "circadian":     round(self.circadian_activity(), 4),
        }
        self._turtle_checkpoints.append(checkpoint)

        # Compute drift across history
        if len(self._turtle_checkpoints) >= 2:
            energies = [c["field_energy"] for c in self._turtle_checkpoints]
            energy_drift = float(energies[-1] - energies[0])
            bio_times = [c["bio_time"] for c in self._turtle_checkpoints]
            bio_rate = (bio_times[-1] - bio_times[0]) / (len(bio_times) - 1 + self.cfg.eps)
        else:
            energy_drift = 0.0
            bio_rate = 0.0

        checkpoint["energy_drift"] = round(energy_drift, 4)
        checkpoint["bio_rate"] = round(bio_rate, 4)
        return checkpoint


def proof_of_property() -> bool:
    """
    MANDATE VERIFICATION — STIG-TIME ADAPTIVE TEMPORAL SUBSTRATE.

    Proves six temporal physics invariants:
      1. Kleiber scaling: bio_time advances faster in BURST than TORPOR
      2. Circadian oscillator: activity gates follow sinusoidal day/night cycle
      3. Weber-Fechner compression: perceived time grows logarithmically
      4. Scalar property: time uncertainty grows proportionally with interval
      5. Bayesian prior: estimates shrink toward historical mean (central tendency)
      6. Sea turtle long-cycle: slow drift is detected across N windows
    """
    print("\n=== SIFTA STIG-TIME (Event 74) : JUDGE VERIFICATION ===")

    cfg = StigTimeConfig(
        circadian_period=100,
        turtle_window=50,
    )
    st = StigTime(cfg)

    # Phase 1: Kleiber time dilation
    print("\n[*] Phase 1: Kleiber Metabolic Time Scaling (West et al. 1997)")
    st2 = StigTime(cfg)
    for _ in range(10):
        st.tick(metabolic_mode="burst")
    for _ in range(10):
        st2.tick(metabolic_mode="torpor")
    print(f"    Bio-time after 10 BURST ticks:  {st.bio_time:.2f}")
    print(f"    Bio-time after 10 TORPOR ticks: {st2.bio_time:.2f}")
    assert st.bio_time > st2.bio_time * 3.0, "[FAIL] BURST should advance bio_time >> TORPOR"

    # Phase 2: Circadian oscillator — sweep through one full cycle manually
    print("\n[*] Phase 2: Circadian Oscillator (Hardin, Hall & Rosbash, Nature 1990)")
    st_circ = StigTime(StigTimeConfig(circadian_period=50, turtle_window=10000))
    activities = []
    for _ in range(50):
        st_circ.tick("cruise")
        activities.append(st_circ.circadian_activity())
    max_act = max(activities)
    min_act = min(activities)
    print(f"    Activity range over 1 full cycle: [{min_act:.3f}, {max_act:.3f}]")
    print(f"    Expected amplitude: {cfg.circadian_amplitude:.1f}")
    assert (max_act - min_act) > 0.4, "[FAIL] Circadian oscillation amplitude too small"

    # Phase 3: Weber-Fechner compression
    print("\n[*] Phase 3: Weber-Fechner Logarithmic Time Compression (Fechner 1860)")
    t1 = st.fechner_compress(10)
    t10 = st.fechner_compress(100)
    t100 = st.fechner_compress(1000)
    ratio_1_to_10 = t10 / t1
    ratio_10_to_100 = t100 / t10
    print(f"    compress(10)={t1:.3f}, compress(100)={t10:.3f}, compress(1000)={t100:.3f}")
    print(f"    10x real time → {ratio_1_to_10:.2f}x perceived time (log compression)")
    assert ratio_1_to_10 < 10.0, "[FAIL] Time should be compressed (not linear)"
    assert ratio_10_to_100 < ratio_1_to_10, "[FAIL] Compression should increase with time"

    # Phase 4: Scalar property
    print("\n[*] Phase 4: Scalar Property — σ(T) = w*T (Gibbon, Psych Rev 1977)")
    st3 = StigTime(cfg)
    st3.start_interval()
    for _ in range(50):
        st3.tick("cruise")
    T_short, sigma_short = st3.measure_interval()

    st3.start_interval()
    for _ in range(200):
        st3.tick("cruise")
    T_long, sigma_long = st3.measure_interval()

    print(f"    Short interval T={T_short:.1f}, σ={sigma_short:.1f}")
    print(f"    Long  interval T={T_long:.1f},  σ={sigma_long:.1f}")
    assert sigma_long > sigma_short, "[FAIL] Uncertainty should scale with interval length"
    w_short = sigma_short / T_short
    w_long = sigma_long / T_long
    print(f"    Weber fraction: w_short={w_short:.3f}, w_long={w_long:.3f} (expect ~{cfg.weber_fraction})")

    # Phase 5: Bayesian central tendency
    print("\n[*] Phase 5: Bayesian Temporal Prior (Jazayeri & Shadlen, Nat Neurosci 2010)")
    # Seed history with intervals around 50 ticks
    st3._interval_history.extend([48.0, 52.0, 50.0, 49.0, 51.0])
    very_short = 5.0
    very_long = 200.0
    est_short = st3.bayesian_estimate(very_short, 0.5)
    est_long = st3.bayesian_estimate(very_long, 20.0)
    print(f"    True short duration={very_short}, Bayesian estimate={est_short:.2f} (pulled toward 50)")
    print(f"    True long duration={very_long}, Bayesian estimate={est_long:.2f} (pulled toward 50)")
    assert est_short > very_short, "[FAIL] Short interval should be overestimated (central tendency)"
    assert est_long < very_long, "[FAIL] Long interval should be underestimated (central tendency)"

    # Phase 6: Turtle long-cycle observer
    print("\n[*] Phase 6: Sea Turtle Long-Cycle Stability Observer (Carr 1992)")
    st4 = StigTime(cfg)
    turtle_reports = []
    declining_energy = 1.0
    for t in range(200):
        declining_energy -= 0.003
        result = st4.tick("cruise", field_energy=max(0.0, declining_energy))
        if result["turtle_report"] is not None:
            turtle_reports.append(result["turtle_report"])

    print(f"    Turtle checkpoints recorded: {len(turtle_reports)}")
    if len(turtle_reports) >= 2:
        drift = turtle_reports[-1]["energy_drift"]
        print(f"    Detected energy drift: {drift:.4f} (should be negative = declining)")
        assert drift < 0, "[FAIL] Turtle should detect declining energy"

    print("\n[+] BIOLOGICAL PROOF: STIG-TIME Adaptive Temporal Substrate verified.")
    print("    1. Kleiber: BURST bio_time >> TORPOR bio_time (West et al. 1997)")
    print("    2. Circadian: sinusoidal activity gate verified (Hall & Rosbash 1990)")
    print("    3. Weber-Fechner: logarithmic time compression (Fechner 1860)")
    print("    4. Scalar Property: σ(T) ∝ T (Gibbon 1977)")
    print("    5. Bayesian prior: central tendency effect confirmed (Jazayeri 2010)")
    print("    6. Turtle: long-cycle energy drift detected (Carr 1992)")
    print("[+] EVENT 74 PASSED.")
    return True


if __name__ == "__main__":
    proof_of_property()
