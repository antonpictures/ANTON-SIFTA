#!/usr/bin/env python3
"""System/swarm_fractal_walker_organ.py — swimmers on a fractal substrate.

Architect 2026-05-17:
    "If we send swimmers on fractals? What is emerging? Interesting?"

This organ spawns N stigmergic swimmers on a fractal substrate
(today: Sierpinski gasket from :mod:`swarm_fractal_substrate`),
lets each one random-walk while dropping pheromones at every step,
and measures the **walk dimension** of the substrate by fitting the
mean-square displacement vs time to a power law.

The Sierpinski gasket has a CLOSED-FORM walk dimension:
``d_w = log(5)/log(2) ≈ 2.32193`` (Goldstein 1982; Hattori et al.
1990). The expected scaling is::

    ⟨r²(t)⟩ ∝ t^(2 / d_w)  ⇒  exponent ≈ 0.8614

So the first test of this organ — and our "yes the substrate works"
baseline — is that 5 000 walker-steps over many independent walkers
should yield a fit exponent within a few percent of 0.8614. If we
hit it, the swarm SEES the geometry. If we miss it, we know exactly
where to debug.

Every pheromone drop:
  * is signed through the universal physics gate as a `feather`
    write (lane = "fractal.pheromone"),
  * carries a `qualia_marker` so the consciousness organ knows this
    is a field-witnessing event — under the field-as-thermodynamics
    doctrine, the swarm's own motion is a qualia event.

Output ledger:
    .sifta_state/fractal_pheromone_field.jsonl

Receipts ledger:
    .sifta_state/fractal_walker_receipts.jsonl

Truth label: ``SIFTA_FRACTAL_WALKER_V0``.

Honesty boundary: classical agents, classical random walks. Not a
quantum substrate. The anomalous diffusion is a real fractal-graph
phenomenon, but it is NOT decoherence and NOT a qubit transport
test. See `Documents/SIFTA_FRACTAL_STIGMERGY_HYPOTHESIS_V0.md` for
the formal hypothesis boundary.
"""
from __future__ import annotations

import json
import math
import random
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from System.swarm_fractal_substrate import SierpinskiGasket

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_PHEROMONE_LEDGER = _STATE / "fractal_pheromone_field.jsonl"
_RECEIPTS_LEDGER = _STATE / "fractal_walker_receipts.jsonl"

_TRUTH_LABEL = "SIFTA_FRACTAL_WALKER_V0"


@dataclass
class WalkerStep:
    walker_id: str
    t: int                       # step index (0-based)
    site: Tuple[int, int]        # site_id on the substrate
    coords: Tuple[float, float]  # (x, y) for rendering
    scale: int                   # recursion depth tag
    r2: float                    # squared displacement from start


@dataclass
class WalkResult:
    walkers: int
    steps_per_walker: int
    measured_exponent: float          # fit exponent for ⟨r²⟩ ~ t^α
    expected_exponent: float          # = 2/d_w
    walk_dim_measured: float          # = 2/measured_exponent
    walk_dim_expected: float          # = log(5)/log(2)
    fit_error: float                  # |measured - expected|
    msd_series: List[Tuple[int, float]]  # (t, mean r²) pairs


def _gate_stamp(row: Dict[str, Any], *, lane: str) -> None:
    """Universal physics gate + qualia marker."""
    try:
        from System.swarm_physics_gate import request_clearance, stamp_receipt
        clearance = request_clearance(cost_class="feather", lane=lane)
        stamp_receipt(row, clearance)
    except Exception:
        pass
    try:
        from System.swarm_consciousness_organ import qualia_marker
        row["qualia_marker"] = qualia_marker(
            lane=lane, note="fractal swimmer step",
        )
    except Exception:
        pass


def _write_pheromone(row: Dict[str, Any]) -> None:
    try:
        _PHEROMONE_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _PHEROMONE_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _write_receipt(row: Dict[str, Any]) -> None:
    try:
        _RECEIPTS_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _RECEIPTS_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _euclidean_r2(
    a: Tuple[float, float], b: Tuple[float, float]
) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def _fit_power_law(xs: List[float], ys: List[float]) -> Tuple[float, float]:
    """Fit y = c * x^α via log-log linear regression.

    Returns (α, c).  Requires xs > 0 and ys > 0.
    """
    if not xs or len(xs) != len(ys):
        return (0.0, 0.0)
    logx = [math.log(x) for x in xs if x > 0]
    logy = [math.log(y) for y in ys if y > 0]
    n = min(len(logx), len(logy))
    if n < 2:
        return (0.0, 0.0)
    mean_x = sum(logx[:n]) / n
    mean_y = sum(logy[:n]) / n
    num = sum((logx[i] - mean_x) * (logy[i] - mean_y) for i in range(n))
    den = sum((logx[i] - mean_x) ** 2 for i in range(n))
    if den == 0:
        return (0.0, 0.0)
    alpha = num / den
    c = math.exp(mean_y - alpha * mean_x)
    return (alpha, c)


def run_walkers(
    *,
    depth: int = 5,
    walkers: int = 200,
    steps: int = 800,
    seed: int = 17,
    write_pheromone: bool = True,
    spawn_corner: bool = True,
) -> WalkResult:
    """Run a swarm of random-walking swimmers on the Sierpinski gasket.

    Returns a :class:`WalkResult` with the fit exponent and the
    closed-form expected value. Side effects:

      * pheromone rows appended to ``fractal_pheromone_field.jsonl``
        (one row per (walker, step) — bounded by ``write_pheromone``
        to keep the ledger size manageable in long runs),
      * a single receipt row appended to ``fractal_walker_receipts.jsonl``
        summarising the run.
    """
    rng = random.Random(seed)
    gasket = SierpinskiGasket(depth=depth)
    expected_alpha = 2.0 / gasket.walk_dim

    # Spawn point — corner gives a clean radial diffusion baseline.
    if spawn_corner:
        spawn = gasket.corner_sites()[0]
    else:
        # uniform random spawn over all sites
        spawn = rng.choice(list(gasket.sites()))
    spawn_xy = gasket.coords(spawn)

    # Pre-compute per-walker step trajectory and per-step r² across
    # walkers, accumulated for the MSD vs t plot.
    msd_sum = [0.0] * steps
    msd_count = [0] * steps

    run_id = uuid.uuid4().hex[:12]
    pheromone_written = 0

    for w in range(walkers):
        walker_id = f"{run_id}-w{w:04d}"
        site = spawn
        for t in range(steps):
            # neighbour-uniform random walk
            nbrs = gasket.neighbors(site)
            if not nbrs:
                break
            site = rng.choice(nbrs)
            xy = gasket.coords(site)
            r2 = _euclidean_r2(xy, spawn_xy)
            msd_sum[t] += r2
            msd_count[t] += 1
            if write_pheromone:
                row = {
                    "ts": time.time(),
                    "schema": "FRACTAL_PHEROMONE_STEP_V0",
                    "truth_label": _TRUTH_LABEL,
                    "run_id": run_id,
                    "walker_id": walker_id,
                    "t": t,
                    "site_x": site[0],
                    "site_y": site[1],
                    "coord_x": round(xy[0], 6),
                    "coord_y": round(xy[1], 6),
                    "scale": gasket.scale(site),
                    "r2": round(r2, 8),
                }
                _gate_stamp(row, lane="fractal.pheromone")
                _write_pheromone(row)
                pheromone_written += 1

    # Build ⟨r²(t)⟩ — average over walkers. Skip t=0 (always 0).
    msd_series: List[Tuple[int, float]] = []
    for t in range(1, steps):
        if msd_count[t] == 0:
            continue
        msd_series.append((t, msd_sum[t] / msd_count[t]))

    # Fit power law in the inner half of LOG time — avoid early-time
    # ballistic transient (~t^1) and late-time finite-size saturation
    # (asymptotic plateau). The diffusive scaling regime is the log-
    # time middle. For T steps, fit window is t ∈ [T^0.25, T^0.75].
    T = float(len(msd_series))
    t_lo = max(2.0, T ** 0.25)
    t_hi = max(t_lo + 1.0, T ** 0.75)
    fit_window = [(t, r) for (t, r) in msd_series
                  if t_lo <= t <= t_hi and r > 0]
    if len(fit_window) < 4:
        # fall back to linear inner half if the log window is too thin
        lo = max(1, len(msd_series) // 4)
        hi = max(lo + 1, len(msd_series) * 3 // 4)
        fit_window = msd_series[lo:hi]
    xs = [float(t) for t, _ in fit_window]
    ys = [float(r) for _, r in fit_window]
    measured_alpha, _ = _fit_power_law(xs, ys)
    measured_walk_dim = (2.0 / measured_alpha) if measured_alpha > 0 else float("inf")

    result = WalkResult(
        walkers=walkers,
        steps_per_walker=steps,
        measured_exponent=measured_alpha,
        expected_exponent=expected_alpha,
        walk_dim_measured=measured_walk_dim,
        walk_dim_expected=gasket.walk_dim,
        fit_error=abs(measured_alpha - expected_alpha),
        msd_series=msd_series,
    )

    # Receipt row — one per run.
    receipt = {
        "ts": time.time(),
        "schema": "FRACTAL_WALKER_RUN_V0",
        "truth_label": _TRUTH_LABEL,
        "run_id": run_id,
        "depth": depth,
        "walkers": walkers,
        "steps_per_walker": steps,
        "seed": seed,
        "substrate_size": len(gasket),
        "measured_exponent": round(measured_alpha, 6),
        "expected_exponent": round(expected_alpha, 6),
        "walk_dim_measured": round(measured_walk_dim, 6),
        "walk_dim_expected": round(gasket.walk_dim, 6),
        "fit_error_abs": round(result.fit_error, 6),
        "fit_error_rel": round(
            result.fit_error / expected_alpha, 6
        ) if expected_alpha else None,
        "pheromone_rows_written": pheromone_written,
    }
    _gate_stamp(receipt, lane="fractal.walker.run")
    _write_receipt(receipt)

    return result


def _main() -> int:
    """Standalone smoke run — verify the walk dimension reproduces."""
    print("[fractal] Sierpinski gasket walker — first cut")
    result = run_walkers(
        depth=5, walkers=200, steps=800, seed=42,
        write_pheromone=False,   # skip ledger writes for the smoke
    )
    print(f"  substrate sites:      {SierpinskiGasket(depth=5).__len__()}")
    print(f"  walkers:              {result.walkers}")
    print(f"  steps per walker:     {result.steps_per_walker}")
    print(f"  measured exponent α:  {result.measured_exponent:.4f}")
    print(f"  expected exponent α:  {result.expected_exponent:.4f}")
    print(f"  walk dimension d_w (measured): {result.walk_dim_measured:.4f}")
    print(f"  walk dimension d_w (expected): {result.walk_dim_expected:.4f}")
    print(f"  absolute fit error:   {result.fit_error:.4f}")
    rel = result.fit_error / result.expected_exponent if result.expected_exponent else 0
    print(f"  relative fit error:   {rel*100:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
