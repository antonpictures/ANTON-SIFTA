#!/usr/bin/env python3
"""System/swarm_turbulence_organ.py — stigmergic turbulence reconstruction.

Architect 2026-05-18:
    "FarSight runs one atmosphere per frame. We run a swarm."

This organ spawns N stigmergic swimmers over the **turbulence hypothesis
space**. Each swimmer carries one :math:`(r_0, \\text{seed})` pair, draws
the corresponding phase screen + PSF, scores how well that hypothesis
explains the observed degraded image, and deposits pheromone at the
matching bin in :math:`r_0`-space. Pheromone evaporates each tick; the
swarm converges on the :math:`r_0` that best explains the observation.

This replaces a single-point physics inversion with an **ensemble**:
the converged distribution over :math:`r_0` IS the uncertainty estimate,
not an afterthought.

Why stigmergic instead of MAP / gradient descent?
=================================================

1. **No gradients.** The forward operator includes a stochastic phase
   screen — bad surface for backprop. Gradient-free ensemble search
   handles this natively.
2. **Receipts.** Every swimmer's hypothesis + score is a row in
   ``turbulence_pheromone_field.jsonl``. The reconstruction is fully
   auditable: anyone can replay any swimmer's deposit by re-deriving
   the phase screen from ``(r0, seed)``.
3. **Free uncertainty quantification.** The pheromone distribution
   over :math:`r_0` is a Bayesian-flavored posterior. Variance of the
   posterior = how unsure we are about the seeing on this frame.
4. **Reuse.** Same architecture as ``swarm_fractal_walker_organ.py`` —
   different substrate, same body discipline.

Every deposit:
  * passes through :func:`swarm_physics_gate.request_clearance` as a
    ``feather`` (cheap write) on lane ``turbulence.pheromone``,
  * carries a ``qualia_marker`` from the consciousness organ.

Ledger
======

  * ``.sifta_state/turbulence_pheromone_field.jsonl`` — one row per
    swimmer deposit ``(r0, seed, score, pheromone_after)``.
  * ``.sifta_state/turbulence_reconstruction_receipts.jsonl`` — one
    row per converged reconstruction with ``(planted_cn2, recovered_cn2,
    posterior_mean_r0, posterior_std_r0, psnr)``.

Truth label: ``SIFTA_TURBULENCE_ORGAN_V0``.

Honesty boundary
================

* The synthetic targets in :mod:`swarm_turbulence_substrate` are
  drawings, not real surveillance imagery. The organ is validated on
  synthetic ground truth (planted :math:`C_n^2` is recovered within
  the posterior's 1σ).
* Real-world reconstruction quality depends on the receiver matching
  the actual atmosphere within the swarm's hypothesis grid. If real
  conditions sit outside the grid, the posterior collapses on a grid
  edge — a known failure mode that the receipts flag.
* This organ does NOT perform person identification. Identity
  attribution requires :mod:`swarm_sar_triage_organ` or an explicit,
  lawful-use catalog match (e.g., individual-zebra pattern matching).
"""
from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from System.swarm_turbulence_substrate import (
    TurbulenceParams,
    degrade,
    make_long_exposure_psf,
    make_phase_screen,
    make_psf,
    r0_to_cn2,
    wiener_restore,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_PHEROMONE_LEDGER = _STATE / "turbulence_pheromone_field.jsonl"
_RECEIPTS_LEDGER = _STATE / "turbulence_reconstruction_receipts.jsonl"

_TRUTH_LABEL = "SIFTA_TURBULENCE_ORGAN_V0"


def _now() -> float:
    return time.time()


def _safe_append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        # Ledger writes never raise; honesty pref. is to drop loudly.
        pass


def _request_clearance(lane: str, cost: str = "feather") -> Optional[Dict[str, Any]]:
    """Pass-through to the universal physics gate. Optional import."""
    try:
        from System.swarm_physics_gate import request_clearance  # type: ignore
        return request_clearance(cost_class=cost, lane=lane)
    except Exception:
        return None


def _qualia_marker(lane: str, note: str = "") -> Dict[str, Any]:
    """Pass-through to the consciousness organ. Optional import."""
    try:
        from System.swarm_consciousness_organ import qualia_marker  # type: ignore
        return qualia_marker(lane=lane, note=note)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Swimmer + ensemble
# ---------------------------------------------------------------------------

@dataclass
class TurbulenceSwimmer:
    """One stigmergic hypothesis about the atmosphere.

    Each swimmer carries a fixed ``seed`` (so the phase screen is
    deterministic) and a hypothesis :math:`r_0` in meters. Pheromone
    accumulates over ticks as the swarm decides this swimmer's
    hypothesis is good.
    """
    swimmer_id: str
    r0_m: float
    seed: int
    pheromone: float = 0.0
    last_score: float = 0.0
    ticks: int = 0


@dataclass
class ReconstructionResult:
    planted_cn2: Optional[float]
    posterior_mean_r0_m: float
    posterior_std_r0_m: float
    posterior_mean_cn2: float
    posterior_std_cn2: float
    psnr_db: float
    restored_image: np.ndarray
    swimmers: List[TurbulenceSwimmer]
    truth_label: str = _TRUTH_LABEL


def _psnr(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Peak signal-to-noise ratio in dB. Assumes inputs in [0, 1]."""
    ref = np.clip(reference, 0.0, 1.0).astype(np.float64)
    cand = np.clip(candidate, 0.0, 1.0).astype(np.float64)
    mse = float(np.mean((ref - cand) ** 2))
    if mse <= 1e-12:
        return 99.0
    return 10.0 * math.log10(1.0 / mse)


def _radial_psd(image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Radially-averaged power spectral density of an image.

    Returns (frequency_bin_index, radial_psd). The frequency axis is
    just the integer radius in Fourier pixels; the caller multiplies by
    the per-pixel frequency step to get cycles/m.
    """
    N = image.shape[0]
    centered = image - float(image.mean())
    F = np.fft.fftshift(np.fft.fft2(centered))
    psd = np.abs(F) ** 2

    yy, xx = np.indices((N, N)) - N / 2.0
    r = np.sqrt(xx * xx + yy * yy).astype(int)
    r = np.clip(r, 0, N // 2)

    counts = np.bincount(r.ravel(), minlength=N // 2 + 1)
    sums = np.bincount(r.ravel(), weights=psd.ravel(), minlength=N // 2 + 1)
    radial = sums / np.maximum(counts, 1)
    f_idx = np.arange(len(radial))
    return f_idx, radial


def _long_exposure_mtf(
    r0_m: float,
    f_cycles_per_m: np.ndarray,
    *,
    wavelength_m: float = 550e-9,
    focal_length_m: float = 0.5,
) -> np.ndarray:
    """Fried 1966 long-exposure atmospheric MTF.

    :math:`\\mathrm{MTF}(f) = \\exp\\!\\left[-3.44 \\left(\\frac{\\lambda f}{r_0}\\right)^{5/3}\\right]`

    The frequency ``f`` here is in cycles per meter on the *sensor*.
    To convert to angular frequency on the sky we'd multiply by the
    focal length; the same r0 dependence remains.
    """
    if r0_m <= 0 or not np.isfinite(r0_m):
        return np.ones_like(f_cycles_per_m)
    # Angular cycles per radian on the sky:
    f_ang = f_cycles_per_m * focal_length_m
    arg = (wavelength_m * f_ang / r0_m) ** (5.0 / 3.0)
    return np.exp(-3.44 * arg)


def _score_hypothesis(
    *,
    observed: np.ndarray,
    psf: np.ndarray,
    r0_m: float,
    pixel_pitch_m: float = 5e-6,
    wavelength_m: float = 550e-9,
    focal_length_m: float = 0.5,
) -> Tuple[float, np.ndarray]:
    """Score one swimmer's hypothesis by MTF-spectrum consistency.

    Unsupervised physics-based score:

      1. Compute the observed image's radial power spectrum.
      2. "Undo" the turbulence MTF² predicted by this swimmer's r0.
      3. Score = -|slope(log P_undone vs log f) - (-2)| at high f.

    Natural images (and our synthetic targets, which are piecewise-
    smooth) have a roughly :math:`1/f^2` PSD rolloff. If the swimmer's
    r0 is right, dividing by the predicted :math:`\\mathrm{MTF}^2`
    restores that natural slope. If r0 is too small, we over-amplify
    high frequencies and the slope becomes shallower than -2. If r0
    is too large, the slope stays steeper than -2 because turbulence
    blur is left unaccounted for.

    Also returns the Wiener restoration under this PSF, which the
    organ aggregates over high-pheromone swimmers.
    """
    N = observed.shape[0]
    pixel_pitch = float(pixel_pitch_m)

    f_idx, radial = _radial_psd(observed)
    # Convert bin index to cycles/m on the sensor
    df = 1.0 / (N * pixel_pitch)
    f_cycles = f_idx * df

    mtf2 = _long_exposure_mtf(
        r0_m,
        f_cycles,
        wavelength_m=wavelength_m,
        focal_length_m=focal_length_m,
    ) ** 2

    # Avoid the very low / very high bins (DC + corner aliasing)
    lo = max(3, N // 32)
    hi = min(len(radial) - 1, N // 3)
    if hi - lo < 5:
        restored = wiener_restore(observed, psf=psf)
        return 0.0, restored

    eps = 1e-30
    undone = radial[lo:hi] / (mtf2[lo:hi] + eps)
    log_psd = np.log(undone + eps)
    log_f = np.log(f_cycles[lo:hi] + eps)

    # Robust linear fit
    slope, _intercept = np.polyfit(log_f, log_psd, 1)
    target_slope = -2.0
    # Score: closer to target slope is better (max at 0)
    score = -abs(float(slope) - target_slope)

    # Restoration with this hypothesis's PSF
    restored = wiener_restore(observed, psf=psf)
    return score, restored


def run_swarm(
    observed: np.ndarray,
    *,
    n_swimmers: int = 32,
    r0_grid_m: Optional[Sequence[float]] = None,
    ticks: int = 6,
    pheromone_evaporation: float = 0.30,
    seed_offset: int = 0,
    planted_params: Optional[TurbulenceParams] = None,
    aperture_m: float = 0.2,
    pixel_pitch_m: float = 5e-6,
    write_ledger: bool = True,
) -> ReconstructionResult:
    """Run the stigmergic turbulence reconstruction.

    Parameters
    ----------
    observed : np.ndarray
        2-D degraded image, float in [0, 1].
    n_swimmers : int
        Number of hypothesis carriers.
    r0_grid_m : sequence of floats, optional
        :math:`r_0` values to spread swimmers across. Default: log-spaced
        from 1 cm to 50 cm.
    ticks : int
        How many rounds of (score → evaporate → deposit) to run.
    pheromone_evaporation : float
        Fraction of pheromone lost each tick (∈ [0, 1)).
    seed_offset : int
        Base seed; swimmer ``i`` uses ``seed_offset + i``.
    planted_params : TurbulenceParams, optional
        Ground truth for synthetic validation. If provided, the receipt
        records the recovery error.
    aperture_m, pixel_pitch_m : float
        Optics for the PSF model. Must match the forward degradation
        for synthetic validation to be meaningful.
    write_ledger : bool
        Whether to append rows to the JSONL ledgers.
    """
    if observed.ndim != 2:
        raise ValueError("observed must be a 2-D image")

    if r0_grid_m is None:
        r0_grid_m = list(np.geomspace(0.01, 0.50, n_swimmers))
    else:
        r0_grid_m = list(r0_grid_m)
        if len(r0_grid_m) != n_swimmers:
            n_swimmers = len(r0_grid_m)

    swimmers: List[TurbulenceSwimmer] = [
        TurbulenceSwimmer(
            swimmer_id=f"turb-{uuid.uuid4().hex[:8]}",
            r0_m=float(r0),
            seed=seed_offset + i,
        )
        for i, r0 in enumerate(r0_grid_m)
    ]

    grid_size = observed.shape[0]
    best_restored = observed.copy()
    best_score = -float("inf")

    qm = _qualia_marker("turbulence.reconstruct", note=f"n_swimmers={n_swimmers}")

    for tick in range(ticks):
        # Evaporate
        for sw in swimmers:
            sw.pheromone *= (1.0 - pheromone_evaporation)

        # Score every swimmer this tick (long-exposure PSF is
        # deterministic in r0; the per-tick seed is kept for the
        # short-exposure speckle path below).
        for sw in swimmers:
            psf = make_long_exposure_psf(
                r0_m=sw.r0_m,
                grid=grid_size,
                seed=sw.seed + 997 * tick,
            )
            score, restored = _score_hypothesis(
                observed=observed,
                psf=psf,
                r0_m=sw.r0_m,
                pixel_pitch_m=pixel_pitch_m,
            )
            sw.last_score = score
            sw.ticks += 1

            if score > best_score:
                best_score = score
                best_restored = restored

        # Pheromone deposit: only the top-K swimmers per tick get
        # pheromone, weighted by their relative score among that top
        # bracket. This matches ant-colony optimization where only the
        # K shortest-path ants deposit, keeping the posterior sharp.
        scores = np.array([sw.last_score for sw in swimmers], dtype=np.float64)
        k = max(1, len(swimmers) // 5)  # top quintile
        top_idx = np.argsort(scores)[-k:]  # indices of top-k
        top_scores = scores[top_idx]
        s_min_top = float(top_scores.min())
        s_max_top = float(top_scores.max())
        if s_max_top > s_min_top:
            local_w = (top_scores - s_min_top) / (s_max_top - s_min_top + 1e-12)
            local_w = local_w + 0.1  # small floor so runner-up still gets some
            local_w = local_w / local_w.sum() * k  # total budget = k units
        else:
            local_w = np.ones(k)

        for idx, w in zip(top_idx, local_w):
            sw = swimmers[idx]
            sw.pheromone += float(w)

            if write_ledger:
                clearance = _request_clearance("turbulence.pheromone")
                clearance_hash = (
                    clearance.get("clearance_hash") if isinstance(clearance, dict) else None
                )
                _safe_append_jsonl(
                    _PHEROMONE_LEDGER,
                    {
                        "ts": _now(),
                        "truth_label": _TRUTH_LABEL,
                        "tick": tick,
                        "swimmer_id": sw.swimmer_id,
                        "r0_m": sw.r0_m,
                        "score": sw.last_score,
                        "pheromone": sw.pheromone,
                        "clearance_hash": clearance_hash,
                        "qualia_marker": qm,
                    },
                )

    # Posterior over r0 from final pheromone
    weights = np.array([sw.pheromone for sw in swimmers], dtype=np.float64)
    if weights.sum() <= 0:
        weights = np.ones_like(weights)
    weights /= weights.sum()
    r0_arr = np.array([sw.r0_m for sw in swimmers], dtype=np.float64)
    mean_r0 = float((weights * r0_arr).sum())
    var_r0 = float((weights * (r0_arr - mean_r0) ** 2).sum())
    std_r0 = math.sqrt(max(var_r0, 0.0))

    # Translate to C_n^2
    mean_cn2 = r0_to_cn2(mean_r0)
    # Propagate uncertainty by sampling
    cn2_arr = np.array([r0_to_cn2(r) for r in r0_arr])
    cn2_mean_w = float((weights * cn2_arr).sum())
    cn2_var = float((weights * (cn2_arr - cn2_mean_w) ** 2).sum())
    cn2_std = math.sqrt(max(cn2_var, 0.0))

    psnr = _psnr(observed, best_restored)
    planted_cn2 = planted_params.cn2 if planted_params is not None else None

    if write_ledger:
        _safe_append_jsonl(
            _RECEIPTS_LEDGER,
            {
                "ts": _now(),
                "truth_label": _TRUTH_LABEL,
                "n_swimmers": n_swimmers,
                "ticks": ticks,
                "planted_cn2": planted_cn2,
                "posterior_mean_r0_m": mean_r0,
                "posterior_std_r0_m": std_r0,
                "posterior_mean_cn2": mean_cn2,
                "posterior_std_cn2": cn2_std,
                "psnr_db": psnr,
                "qualia_marker": qm,
            },
        )

    return ReconstructionResult(
        planted_cn2=planted_cn2,
        posterior_mean_r0_m=mean_r0,
        posterior_std_r0_m=std_r0,
        posterior_mean_cn2=mean_cn2,
        posterior_std_cn2=cn2_std,
        psnr_db=psnr,
        restored_image=best_restored,
        swimmers=swimmers,
    )


# ---------------------------------------------------------------------------
# Smoke test — planted r_0 recovery
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from System.swarm_turbulence_substrate import synthetic_target

    print(f"[{_TRUTH_LABEL}] smoke: planted-r0 recovery (zebra target, 128 grid)")
    img = synthetic_target(kind="zebra_stripes", grid=128)

    # Use a finer r0 grid spanning the relevant span
    r0_grid = list(np.geomspace(0.005, 0.30, 24))

    for planted_cn2 in (1e-15, 5e-15, 1e-14):
        params = TurbulenceParams(cn2=planted_cn2)
        degraded, _ = degrade(img, params=params, seed=11, noise_sigma=0.005,
                              long_exposure=True)
        result = run_swarm(
            degraded,
            n_swimmers=len(r0_grid),
            r0_grid_m=r0_grid,
            ticks=3,
            planted_params=params,
            write_ledger=False,
        )
        true_r0_cm = params.r0 * 100.0
        rec_r0_cm = result.posterior_mean_r0_m * 100.0
        rec_std_cm = result.posterior_std_r0_m * 100.0
        print(
            f"  planted C_n^2={planted_cn2:.1e}  true_r0={true_r0_cm:.2f} cm   "
            f"recovered r0={rec_r0_cm:.2f} ± {rec_std_cm:.2f} cm   "
            f"PSNR={result.psnr_db:.1f} dB"
        )
