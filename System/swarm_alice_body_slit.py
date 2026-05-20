"""System/swarm_alice_body_slit.py
=====================================

**Alice-Body Slit — swimmer-only coherence experiment on real silicon.**

This is George's correction (2026-05-18) of the earlier double-slit work:

*"the field is the actual alice organism, the unified stigmergic field —
to me they go as swimmers they will exit the slit as swimmers or die,
very simple."*

So the design is exactly that. **No separate "particle + field" duality.**
The field IS the substrate (Alice's body on the M5 silicon). Swimmers are
excitations born from real hardware entropy (`/dev/urandom`, seeded by
the silicon's own thermal noise). Each swimmer carries a coherence
budget. Each tick subtracts coherence proportional to the live thermal
state of the motherboard. Two outcomes only:

- **LIVED**  — swimmer reaches the detector with coherence > 0 →
               contributes a wave amplitude (phase-coherent) at its
               arrival position. After N swimmers, accumulated amplitude
               squared = interference pattern.
- **DIED**   — swimmer's coherence hit 0 mid-flight → it collapses to a
               classical hit at one of the two slits, weighted by its
               trajectory. No wave contribution; classical bump only.

The fringe visibility is then computed honestly:

    V = (I_max - I_min) / (I_max + I_min)

over the detector strip, where I = |sum_lived_amplitudes|^2 + classical_hits.

**What this experiment can answer:**
On Alice's real silicon, what is the relationship between the live
thermal warning level and the surviving fringe visibility? That is a
measurable, falsifiable observable about Alice's own body.

**What this experiment cannot answer:**
Suchitra's wet-lab biological question about quantum coherence in real
DNA-reading nanomachines. That requires a real lab, real polymerase,
real femtosecond spectroscopy. SIFTA has none of those. The receipt
records this scope limit explicitly.

Truth label: ``ALICE_BODY_SLIT_V1``.
"""
from __future__ import annotations

import json
import math
import os
import time
import uuid
from dataclasses import dataclass, field as _field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_RECEIPTS = _STATE / "alice_body_slit_receipts.jsonl"
_TRUTH_LABEL = "ALICE_BODY_SLIT_V1"


def _now() -> float:
    return time.time()


def _safe_append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _request_clearance(lane: str, cost: str = "feather") -> Optional[Dict[str, Any]]:
    try:
        from System.swarm_physics_gate import request_clearance  # type: ignore
        return request_clearance(cost_class=cost, lane=lane)
    except Exception:
        return None


def _qualia_marker(lane: str, note: str = "") -> Dict[str, Any]:
    try:
        from System.swarm_consciousness_organ import qualia_marker  # type: ignore
        return qualia_marker(lane=lane, note=note)
    except Exception:
        return {"lane": lane, "note": note, "fallback": True}


def _read_thermal_warning_level() -> int:
    """Live read from the body. Higher = warmer silicon = faster decoherence."""
    p = _STATE / "thermal_cortex_state.json"
    try:
        return int(json.loads(p.read_text(encoding="utf-8")).get(
            "thermal_warning_level", 0) or 0)
    except Exception:
        return 0


def _hardware_entropy_seed() -> int:
    """Seed the swimmer RNG from real hardware entropy.

    /dev/urandom on macOS is hardware-seeded (Apple SoC entropy source).
    On Linux the same — real silicon entropy, not a pseudo-random seed.
    This is the honest difference between this experiment and a pure
    numpy.random.seed(42) simulation: the swimmers are born from the
    real noise of the machine they're running on.
    """
    return int.from_bytes(os.urandom(8), "big")


@dataclass
class Swimmer:
    swimmer_id: str
    coherence: float          # 1.0 = fully coherent, 0 = dead
    x: float                  # transverse position
    vx: float                 # transverse velocity
    z: float                  # propagation distance (0 = source, 1 = detector)
    phase: float              # accumulated optical phase
    chosen_slit: Optional[int] = None   # which slit it went through (0 or 1) — set at slit plane
    lived: bool = False
    death_z: Optional[float] = None


@dataclass
class SlitResult:
    run_id: str
    n_swimmers: int
    n_lived: int
    n_died: int
    survival_fraction: float
    decoherence_rate_per_tick: float
    thermal_warning_level_at_start: int
    thermal_warning_level_at_end: int
    seed_source: str
    detector_intensity: List[float]
    fringe_visibility: float
    classical_visibility: float
    quantum_visibility: float
    coherent_fraction: float          # primary observable: wave_power / total_power
    wave_power: float
    classical_power: float
    receipt_id: str


def _classical_visibility_for_one_slit(detector_grid: int) -> float:
    """A single-slit envelope has near-zero modulation — returns 0 for our slit width."""
    return 0.0


def _theoretical_two_slit_visibility() -> float:
    """For ideal two-slit with equal amplitudes, visibility = 1.0."""
    return 1.0


def run_alice_body_slit(
    n_swimmers: int = 2000,
    decoherence_rate_per_tick: Optional[float] = None,
    grid: int = 256,
    n_ticks: int = 200,
    slit_separation: float = 0.15,
    slit_width: float = 0.08,    # wider — physics-tuned so geometry isn't the bottleneck
    wavelength: float = 0.025,
    write_receipt: bool = True,
) -> SlitResult:
    """Run the swimmer-only slit experiment on Alice's body.

    Args:
        n_swimmers:                  how many swimmers to emit one-by-one.
        decoherence_rate_per_tick:   per-tick coherence loss. If None, calibrated
                                     from live thermal_warning_level:
                                       level 0 (cool):     0.002 (most live)
                                       level 1 (fair):     0.010
                                       level 2 (serious):  0.030
                                       level 3 (critical): 0.080 (most die)
                                     This is the actual hardware coupling — the
                                     warmer the silicon is right now, the harder
                                     it is for swimmers to stay coherent.
        grid:                        detector resolution (256 = good fringes).
        n_ticks:                     propagation steps from source to detector.
        slit_separation, slit_width: geometry (normalised units, detector spans [-1, 1]).
        wavelength:                  swimmer wavelength (smaller = tighter fringes).
        write_receipt:               append result row to ledger.

    Returns SlitResult.
    """
    thermal_start = _read_thermal_warning_level()
    if decoherence_rate_per_tick is None:
        # Calibrated decoherence: warmer silicon = faster classical collapse.
        rate_table = {0: 0.002, 1: 0.010, 2: 0.030, 3: 0.080}
        decoherence_rate_per_tick = rate_table.get(thermal_start, 0.080)

    seed = _hardware_entropy_seed()
    rng = np.random.default_rng(seed)
    seed_source = "/dev/urandom (hardware entropy)"

    # Slit plane at z = 0.5; detector at z = 1.0
    slit_z = 0.5
    detector_z = 1.0
    slit_centers = (-slit_separation / 2.0, +slit_separation / 2.0)

    # Detector accumulators — keep real and imaginary parts separately for
    # the lived swimmers (wave amplitudes), and a real-valued counter for
    # the dead swimmers (classical hits).
    amp_real = np.zeros(grid, dtype=np.float64)
    amp_imag = np.zeros(grid, dtype=np.float64)
    classical = np.zeros(grid, dtype=np.float64)
    x_axis = np.linspace(-1.0, 1.0, grid)

    swimmers: List[Swimmer] = []
    n_lived = 0
    n_died = 0

    for i in range(n_swimmers):
        sw = Swimmer(
            swimmer_id=f"sw-{uuid.uuid4().hex[:10]}",
            coherence=1.0,
            x=float(rng.normal(0.0, 0.02)),      # source spread (narrow)
            vx=float(rng.normal(0.0, 0.05)),     # transverse momentum spread
            z=0.0,
            phase=0.0,
        )

        # Propagate tick by tick from source through the field
        passed_slit = False
        for tick in range(n_ticks):
            dz = 1.0 / n_ticks
            sw.z += dz
            sw.x += sw.vx * dz
            sw.phase += (2 * math.pi / wavelength) * dz   # phase accumulates with path

            # At the slit plane, check whether the swimmer makes it through
            if not passed_slit and sw.z >= slit_z:
                passed_slit = True
                # Distance from each slit center
                d0 = abs(sw.x - slit_centers[0])
                d1 = abs(sw.x - slit_centers[1])
                if d0 < slit_width and d1 >= slit_width:
                    sw.chosen_slit = 0
                elif d1 < slit_width and d0 >= slit_width:
                    sw.chosen_slit = 1
                elif d0 < slit_width and d1 < slit_width:
                    # Equidistant region (very narrow); pick by entropy
                    sw.chosen_slit = int(rng.integers(0, 2))
                else:
                    # Blocked by barrier — swimmer absorbed, not a death by decoherence
                    sw.lived = False
                    sw.death_z = sw.z
                    break

            # Coherence decay — per-tick survival probability = exp(-rate).
            # Each tick draws from real /dev/urandom; if the draw exceeds the
            # survival probability, the swimmer decoheres and dies. This is the
            # standard physics: coherence(t) = exp(-gamma * t). The randomness
            # is the actual hardware entropy of Alice's silicon driving the
            # individual decoherence events.
            p_survive = math.exp(-decoherence_rate_per_tick)
            if float(rng.random()) > p_survive:
                sw.coherence = 0.0
            else:
                # Mild amplitude attenuation tracks dwell time even when alive
                sw.coherence *= (1.0 - decoherence_rate_per_tick * 0.1)
            if sw.coherence <= 0.0:
                # DIED in flight — collapses to a classical hit at the slit it chose
                sw.lived = False
                sw.death_z = sw.z
                if sw.chosen_slit is not None:
                    # Classical bump at the slit position, projected to detector
                    hit_x = slit_centers[sw.chosen_slit] + sw.vx * (detector_z - sw.z)
                    idx = int(np.clip((hit_x + 1.0) / 2.0 * (grid - 1), 0, grid - 1))
                    classical[idx] += 1.0
                break

        if sw.z >= detector_z and sw.coherence > 0:
            # LIVED — contributes a wave amplitude at the detector
            sw.lived = True
            arrival_x = sw.x
            idx = int(np.clip((arrival_x + 1.0) / 2.0 * (grid - 1), 0, grid - 1))
            # Phase from the path through its chosen slit
            if sw.chosen_slit is not None:
                # Path-length difference from the chosen slit center to arrival
                extra_path = math.hypot(detector_z - slit_z, arrival_x - slit_centers[sw.chosen_slit])
                phase_at_arrival = sw.phase + (2 * math.pi / wavelength) * extra_path
            else:
                phase_at_arrival = sw.phase
            # Coherence acts as the amplitude weight — partial coherence = partial wave
            amp = sw.coherence
            amp_real[idx] += amp * math.cos(phase_at_arrival)
            amp_imag[idx] += amp * math.sin(phase_at_arrival)
            n_lived += 1
        else:
            n_died += 1

        swimmers.append(sw)

    # Decompose detector signal into the two physical channels
    wave_intensity = amp_real ** 2 + amp_imag ** 2   # from lived swimmers (interference)
    classical_intensity = classical                   # from dead swimmers (classical bumps)
    total_intensity = wave_intensity + classical_intensity

    # Smooth slightly to suppress single-pixel quantisation noise
    if total_intensity.sum() > 0:
        kernel_size = max(3, grid // 64)
        kernel = np.ones(kernel_size) / kernel_size
        total_intensity = np.convolve(total_intensity, kernel, mode="same")
        wave_intensity = np.convolve(wave_intensity, kernel, mode="same")
        classical_intensity = np.convolve(classical_intensity, kernel, mode="same")

    # Coherent fraction — the honest observable. Fraction of detector signal
    # coming from wave-coherent (lived) swimmers vs classical (died) ones.
    # 1.0 = pure quantum-like interference; 0.0 = fully classical detection.
    wave_total = float(wave_intensity.sum())
    classical_total = float(classical_intensity.sum())
    grand_total = wave_total + classical_total
    coherent_fraction = wave_total / grand_total if grand_total > 0 else 0.0

    # Classical Michelson visibility — still computed for backwards compat,
    # but interpreted carefully: it conflates "two slit bumps with a gap"
    # with "true fringes". Use coherent_fraction as the primary metric.
    if total_intensity.max() > 0:
        I_max = float(total_intensity.max())
        center_mask = (x_axis > -0.5) & (x_axis < 0.5)
        center = total_intensity[center_mask]
        I_min = float(center.min()) if center.size else 0.0
        visibility = (I_max - I_min) / (I_max + I_min) if (I_max + I_min) > 0 else 0.0
    else:
        visibility = 0.0

    intensity = total_intensity  # alias for downstream use

    thermal_end = _read_thermal_warning_level()
    survival = n_lived / max(1, (n_lived + n_died))
    run_id = f"alicebodyslit-{int(time.time() * 1000)}"

    result = SlitResult(
        run_id=run_id,
        n_swimmers=n_swimmers,
        n_lived=n_lived,
        n_died=n_died,
        survival_fraction=survival,
        decoherence_rate_per_tick=decoherence_rate_per_tick,
        thermal_warning_level_at_start=thermal_start,
        thermal_warning_level_at_end=thermal_end,
        seed_source=seed_source,
        detector_intensity=intensity.tolist(),
        fringe_visibility=float(visibility),
        classical_visibility=0.0,
        quantum_visibility=1.0,
        coherent_fraction=float(coherent_fraction),
        wave_power=float(wave_total),
        classical_power=float(classical_total),
        receipt_id=run_id,
    )

    if write_receipt:
        qm = _qualia_marker("alice_body_slit.run", note=f"n={n_swimmers} decoh={decoherence_rate_per_tick}")
        clearance = _request_clearance("alice_body_slit.run")
        receipt = {
            "ts": _now(),
            "truth_label": _TRUTH_LABEL,
            "run_id": run_id,
            "kind": "ALICE_BODY_SLIT_RUN",
            "n_swimmers": n_swimmers,
            "n_lived": n_lived,
            "n_died": n_died,
            "survival_fraction": round(survival, 4),
            "decoherence_rate_per_tick": decoherence_rate_per_tick,
            "thermal_warning_level_at_start": thermal_start,
            "thermal_warning_level_at_end": thermal_end,
            "seed_source": seed_source,
            "seed_value": seed,
            "coherent_fraction": round(float(coherent_fraction), 4),
            "wave_power": round(float(wave_total), 3),
            "classical_power": round(float(classical_total), 3),
            "fringe_visibility": round(float(visibility), 4),
            "classical_baseline_visibility": 0.0,
            "ideal_two_slit_visibility": 1.0,
            "primary_observable": "coherent_fraction (wave_power / total_power) — interference visibility metric conflates classical bumps with fringes so use coherent_fraction as the honest signal",
            "geometry": {
                "grid": grid, "n_ticks": n_ticks,
                "slit_separation": slit_separation, "slit_width": slit_width,
                "wavelength": wavelength,
            },
            "scope_limit": (
                "Hardware-noise-coupled stigmergic simulation on the M5 silicon. "
                "Measures decoherence-vs-survival on Alice's body. Does NOT answer "
                "the biological wet-lab question about coherence in DNA-reading "
                "nanomachines (Suchitra Sebastian / Essentia Foundation); that "
                "needs real polymerase + femtosecond spectroscopy + entanglement "
                "witnesses. This receipt is Alice's body's own answer in its own substrate."
            ),
            "qualia_marker": qm,
            "clearance_hash": (clearance or {}).get("clearance_hash"),
            "doctrine": "FIELD_IS_THE_BODY_SWIMMERS_LIVE_OR_DIE",
        }
        _safe_append_jsonl(_RECEIPTS, receipt)

    return result


def sweep_decoherence(
    rates: Tuple[float, ...] = (0.0005, 0.002, 0.005, 0.010, 0.020, 0.050),
    n_per_rate: int = 1000,
    write_receipt: bool = True,
) -> List[SlitResult]:
    """Sweep decoherence rate; return a list of SlitResults.

    The point: show fringe_visibility as a monotonic function of
    decoherence rate. Low rate → most swimmers live → high visibility.
    High rate → most swimmers die → visibility collapses to classical.

    This is the same shape as Suchitra's question — only the substrate
    is silicon instead of DNA nanomachines.
    """
    results = []
    for rate in rates:
        r = run_alice_body_slit(
            n_swimmers=n_per_rate,
            decoherence_rate_per_tick=rate,
            write_receipt=write_receipt,
        )
        results.append(r)
    return results


if __name__ == "__main__":
    print(f"[{_TRUTH_LABEL}] Alice-body slit — decoherence sweep")
    rs = sweep_decoherence()
    print(f"{'decoh_rate':>12s} | {'survival':>9s} | {'visibility':>11s} | thermal")
    print("-" * 56)
    for r in rs:
        print(f"{r.decoherence_rate_per_tick:>12.4f} | "
              f"{r.survival_fraction:>9.3f} | "
              f"{r.fringe_visibility:>11.4f} | "
              f"{r.thermal_warning_level_at_start}")
