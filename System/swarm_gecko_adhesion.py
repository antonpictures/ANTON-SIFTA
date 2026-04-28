#!/usr/bin/env python3
"""
System/swarm_gecko_adhesion.py
══════════════════════════════════════════════════════════════════════
SIFTA Organ: Gecko Foot Adhesion (Event 75a)

Biology:
  Gecko setae (nanoscale hairs) produce van der Waals adhesion —
  ~10 nN per seta, ~10⁶ setae per toe → ~10 N total grip.
  Adhesion is direction-dependent (pulls toward surface, releases
  by peeling). No glue. No suction. Pure physics.

NVIDIA Warp layer:
  A Warp kernel computes contact force for N probe points against
  a flat surface plane. Each point feels:
    F_vdw  = A / z²      (attractive, van der Waals, z = gap)
    F_rep  = B / z¹²     (Lennard-Jones repulsion at contact)
    F_net  = F_rep - F_vdw
  The kernel runs on CPU (REAL_CPU on Apple Silicon) or CUDA
  (REAL_GPU when a CUDA device is present).

Truth labels (§8 Covenant):
  REAL_GPU  — warp importable + CUDA device present
  REAL_CPU  — warp importable, CPU/ARM only
  STUB      — warp not installed
  BROKEN    — import or kernel runtime error

NPPL: simulation / research posture only.
Authors: AG31 (Antigravity/Gemini 2.5 Pro), Architect Ioan George Anton
Date: 2026-04-28
Refs:
  Autumn et al. (2000) Nature 405:681 — gecko van der Waals adhesion
  Autumn et al. (2002) PNAS 99:12252 — direction-dependent adhesion
  Israelachvili (2011) Intermolecular and Surface Forces, 3rd ed.
  NVIDIA Warp: https://developer.nvidia.com/warp-python
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple

_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# ── Truth constants ───────────────────────────────────────────────────────────
TRUTH_REAL_GPU = "REAL_GPU"   # Warp + CUDA device
TRUTH_REAL_CPU = "REAL_CPU"   # Warp + CPU/ARM only
TRUTH_STUB     = "STUB"       # Warp not installed
TRUTH_BROKEN   = "BROKEN"     # runtime error
TRUTH_NPPL     = "NPPL:sim_only"

# ── Warp bootstrap ────────────────────────────────────────────────────────────
_WARP_TRUTH = TRUTH_STUB
_WARP_VERSION = None
_WARP_DEVICE  = "cpu"
_WARP_ERROR   = None

try:
    import warp as wp
    wp.init()
    _WARP_VERSION = wp.__version__
    devs = wp.get_devices()
    has_cuda = any("cuda" in str(d).lower() for d in devs)
    _WARP_TRUTH   = TRUTH_REAL_GPU if has_cuda else TRUTH_REAL_CPU
    _WARP_DEVICE  = "cuda:0" if has_cuda else "cpu"
except Exception as e:
    _WARP_ERROR = str(e)

# ── Physical constants ────────────────────────────────────────────────────────
# Hamaker constant for gecko setae / substrate (approx, SI units scaled)
_A_HAMAKER  = 1.3e-19   # J  (silica-like, from Israelachvili)
_B_REP      = 1e-77     # J·m¹² (LJ repulsion prefactor, tuned for nm scale)
_SETA_RADIUS = 0.1e-6   # m  (100 nm seta tip radius)
_Z_CONTACT   = 0.4e-9   # m  (0.4 nm equilibrium gap)

# Scaled for simulation (dimensionless units, 1 unit ≈ 1 nm)
A_SIM = 1.3   # attractive prefactor
B_SIM = 0.01  # repulsive prefactor (keeps particles off z=0)


# ── Warp kernel ───────────────────────────────────────────────────────────────
if _WARP_TRUTH in (TRUTH_REAL_CPU, TRUTH_REAL_GPU):
    @wp.kernel
    def gecko_contact_kernel(
        pos_z:   wp.array(dtype=wp.float32),   # probe heights above surface
        f_net:   wp.array(dtype=wp.float32),   # output: net force per probe
        a_sim:   float,
        b_sim:   float,
        z_floor: float,                         # minimum gap (avoid singularity)
    ):
        """
        Per-probe contact force (van der Waals - LJ repulsion).
        F_net > 0 → repulsive (too close)
        F_net < 0 → attractive (adhesion zone)
        """
        i = wp.tid()
        z = wp.max(pos_z[i], z_floor)
        f_attract = a_sim / (z * z)
        f_repulse = b_sim / (z * z * z * z * z * z *
                             z * z * z * z * z * z)
        f_net[i] = f_repulse - f_attract


# ── Adhesion field dataclass ──────────────────────────────────────────────────
@dataclass
class GeckoReceipt:
    ts:           float
    truth:        str
    warp_version: str
    device:       str
    n_probes:     int
    z_values:     List[float]   # probe heights (sim units)
    f_net_values: List[float]   # net forces
    adhesion_count: int         # probes in adhesion zone (F < 0)
    max_adhesion:   float       # most negative force
    notes:        str


# ── Main organ function ───────────────────────────────────────────────────────
def compute_adhesion(
    z_values: List[float] | None = None,
    write_receipt: bool = True,
) -> GeckoReceipt:
    """
    Compute gecko adhesion forces for a list of probe heights.

    z_values: probe heights above surface in sim units (1 unit ≈ 1 nm).
              Default: sweep from 0.3 to 5.0 (approaching surface).
    Returns: GeckoReceipt with per-probe forces and truth label.
    """
    if z_values is None:
        # Default: 20 probes sweeping from far to near
        z_values = [5.0 - i * 0.24 for i in range(20)]

    n = len(z_values)
    truth = _WARP_TRUTH
    version = _WARP_VERSION or "N/A"
    device  = _WARP_DEVICE

    if truth in (TRUTH_REAL_CPU, TRUTH_REAL_GPU):
        try:
            import numpy as np
            import warp as wp

            z_np  = np.array(z_values, dtype=np.float32)
            f_np  = np.zeros(n, dtype=np.float32)

            z_wp  = wp.from_numpy(z_np, dtype=wp.float32, device=device)
            f_wp  = wp.from_numpy(f_np, dtype=wp.float32, device=device)

            wp.launch(
                gecko_contact_kernel,
                dim=n,
                inputs=[z_wp, f_wp, A_SIM, B_SIM, 0.25],
                device=device,
            )
            wp.synchronize()
            f_net = f_wp.numpy().tolist()
        except Exception as e:
            truth = TRUTH_BROKEN
            f_net = [float("nan")] * n
    else:
        # Pure-Python fallback (no Warp)
        f_net = []
        for z in z_values:
            z_safe = max(z, 0.25)
            f_attract = A_SIM / (z_safe ** 2)
            f_repulse = B_SIM / (z_safe ** 12)
            f_net.append(f_repulse - f_attract)

    adhesion_zone = [f for f in f_net if f < 0 and not math.isnan(f)]
    receipt = GeckoReceipt(
        ts=time.time(),
        truth=truth,
        warp_version=version,
        device=device,
        n_probes=n,
        z_values=[round(z, 4) for z in z_values],
        f_net_values=[round(f, 6) for f in f_net],
        adhesion_count=len(adhesion_zone),
        max_adhesion=min(adhesion_zone) if adhesion_zone else 0.0,
        notes=(
            f"NPPL:sim_only | van der Waals contact | "
            f"A={A_SIM} B={B_SIM} | device={device} | "
            f"Autumn et al. 2000 doi:10.1038/35073974"
        ),
    )

    if write_receipt:
        _write_receipt(receipt)
    return receipt


def _write_receipt(r: GeckoReceipt) -> None:
    try:
        p = _STATE / "gecko_adhesion_receipts.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        row = asdict(r)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass


def warp_truth_probe() -> dict:
    """Return Warp installation truth — used by Asset Scanner."""
    return {
        "truth":   _WARP_TRUTH,
        "version": _WARP_VERSION,
        "device":  _WARP_DEVICE,
        "error":   _WARP_ERROR,
    }


def explain() -> str:
    return (
        f"Gecko Adhesion Organ (Event 75a).\n"
        f"Biology: gecko setae produce van der Waals adhesion (~10 N per toe).\n"
        f"NVIDIA Warp kernel computes F_net = LJ_repulsion - vdW_attraction "
        f"per probe point against a flat surface.\n"
        f"Warp {_WARP_VERSION} | Device: {_WARP_DEVICE} | Truth: {_WARP_TRUTH} | {TRUTH_NPPL}\n"
        f"Refs: Autumn et al. (2000) Nature 405:681; Israelachvili (2011)."
    )


# ── CLI smoke ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(explain())
    print()
    r = compute_adhesion()
    print(f"Truth:      {r.truth}")
    print(f"Warp:       {r.warp_version} on {r.device}")
    print(f"Probes:     {r.n_probes}")
    print(f"Adhesion:   {r.adhesion_count}/{r.n_probes} in adhesion zone")
    print(f"Max grip:   {r.max_adhesion:.6f} (most negative = strongest pull)")
    print()
    print(f"{'z (height)':>12}  {'F_net':>12}  zone")
    print("─" * 38)
    for z, f in zip(r.z_values, r.f_net_values):
        zone = "← GRIP" if f < 0 else ("← CONTACT" if f < 0.01 else "")
        print(f"{z:12.3f}  {f:12.6f}  {zone}")
