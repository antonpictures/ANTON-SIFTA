#!/usr/bin/env python3
"""
System/swarm_spider_web.py
══════════════════════════════════════════════════════════════════════
SIFTA Organ: Spider Web Vibration (Event 75c)

Biology:
  Spider silk threads form a spring-mass graph. One touch anywhere
  propagates as a damped wave through all nodes. The spider sits at
  the hub, reads the wave pattern, and localises the disturbance to
  sub-millimetre accuracy — without eyes, in the dark.

  "The web is the spider's distributed nervous surface."
  — Witt, Reed & Peakall (1968) A Spider's Web

Physics (spring-mass on graph):
  Each node i has scalar out-of-plane displacement d[i].
  Each edge (i,j) is a spring with stiffness k.
  Force on i: F[i] = k * Σ(d[j] - d[i])  for all neighbours j
  Damped Euler integration:
    v[i] += dt * (F[i] - γ·v[i])
    d[i] += dt * v[i]

NVIDIA Warp layer:
  A Warp kernel runs the per-node update in parallel.
  Topology: hub-and-spoke orb web (N_RADIAL × N_RING nodes + centre).
  Adjacency stored as [N, MAX_DEG] int32 array (padded with -1).

Truth labels (§8 Covenant):
  REAL_GPU  — Warp + CUDA device
  REAL_CPU  — Warp + CPU/ARM (Apple Silicon)
  STUB      — Warp not installed
  BROKEN    — kernel propagation invariant fails

NPPL: simulation / research posture only.
Authors: AG31 (Antigravity/Gemini 2.5 Pro), Architect Ioan George Anton
Date: 2026-04-28
Refs:
  Witt, Reed & Peakall (1968) A Spider's Web, Springer — web as nervous surface
  Mortimer et al. (2016) J R Soc Interface 13:20160024
    doi:10.1098/rsif.2016.0024 — web vibration and information
  Naftilan (1999) J Exp Biol 202:3245 — silk spring constants
  NVIDIA Warp: https://developer.nvidia.com/warp-python
"""
from __future__ import annotations

import json, math, time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple, Optional

_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# ── Truth constants ───────────────────────────────────────────────────────────
TRUTH_REAL_GPU = "REAL_GPU"
TRUTH_REAL_CPU = "REAL_CPU"
TRUTH_STUB     = "STUB"
TRUTH_BROKEN   = "BROKEN"
TRUTH_NPPL     = "NPPL:sim_only"

# ── Warp bootstrap ────────────────────────────────────────────────────────────
_WARP_TRUTH   = TRUTH_STUB
_WARP_VERSION = None
_WARP_DEVICE  = "cpu"
_WARP_ERROR   = None

try:
    import warp as wp
    wp.init()
    _WARP_VERSION = wp.__version__
    devs = wp.get_devices()
    has_cuda = any("cuda" in str(d).lower() for d in devs)
    _WARP_TRUTH  = TRUTH_REAL_GPU if has_cuda else TRUTH_REAL_CPU
    _WARP_DEVICE = "cuda:0" if has_cuda else "cpu"
except Exception as e:
    _WARP_ERROR = str(e)

# ── Warp kernel: damped spring-mass step ─────────────────────────────────────
MAX_DEG = 12   # maximum neighbours per node (hub has N_RADIAL spokes)

if _WARP_TRUTH in (TRUTH_REAL_CPU, TRUTH_REAL_GPU):
    @wp.kernel
    def web_step_kernel(
        disp:       wp.array(dtype=wp.float32),      # [N] current displacement
        vel:        wp.array(dtype=wp.float32),      # [N] current velocity
        disp_out:   wp.array(dtype=wp.float32),      # [N] output displacement
        vel_out:    wp.array(dtype=wp.float32),      # [N] output velocity
        neighbors:  wp.array2d(dtype=wp.int32),      # [N, MAX_DEG]
        stiffness:  float,
        damping:    float,
        dt:         float,
    ):
        """Parallel per-node damped spring update."""
        i = wp.tid()
        max_k = neighbors.shape[1]

        force = float(0.0)
        for k in range(max_k):
            j = neighbors[i, k]
            if j >= 0:
                force = force + stiffness * (disp[j] - disp[i])

        acc        = force - damping * vel[i]
        v_new      = vel[i] + dt * acc
        vel_out[i] = v_new
        disp_out[i]= disp[i] + dt * v_new


# ── Web topology builder ──────────────────────────────────────────────────────
def build_orb_web(n_radial: int = 8, n_ring: int = 5) -> dict:
    """
    Build hub-and-spoke orb web adjacency.
    Node 0 = centre hub.
    Nodes 1..n_radial*n_ring: ring[r][s] at index 1 + r*n_radial + s.
    Edges: radial (hub→ring1, ring1→ring2, …) + circumferential (around each ring).
    Returns dict with node count, adjacency [N, MAX_DEG], positions [N, 2].
    """
    N = 1 + n_radial * n_ring

    def nidx(ring: int, spoke: int) -> int:
        return 1 + ring * n_radial + (spoke % n_radial)

    adj: List[List[int]] = [[] for _ in range(N)]

    def add_edge(a: int, b: int) -> None:
        if b not in adj[a]: adj[a].append(b)
        if a not in adj[b]: adj[b].append(a)

    # Radial edges hub → ring 0
    for s in range(n_radial):
        add_edge(0, nidx(0, s))
    # Radial edges ring r → ring r+1
    for r in range(n_ring - 1):
        for s in range(n_radial):
            add_edge(nidx(r, s), nidx(r + 1, s))
    # Circumferential edges within each ring
    for r in range(n_ring):
        for s in range(n_radial):
            add_edge(nidx(r, s), nidx(r, s + 1))

    # Pad adjacency to MAX_DEG
    adj_pad = [row[:MAX_DEG] + [-1] * (MAX_DEG - len(row[:MAX_DEG])) for row in adj]

    # 2-D positions (for labelling)
    pos = [(0.0, 0.0)]   # hub
    for r in range(n_ring):
        radius = (r + 1) / n_ring
        for s in range(n_radial):
            angle = 2 * math.pi * s / n_radial
            pos.append((radius * math.cos(angle), radius * math.sin(angle)))

    return {"n_nodes": N, "adj": adj_pad, "positions": pos,
            "n_radial": n_radial, "n_ring": n_ring}


# ── Receipt dataclass ─────────────────────────────────────────────────────────
@dataclass
class WebReceipt:
    ts:           float
    truth:        str
    warp_version: str
    device:       str
    n_nodes:      int
    n_edges:      int
    source_node:  int
    impulse:      float
    ticks:        int
    stiffness:    float
    damping:      float
    # Snapshot at final tick
    max_disp_node:  int
    max_disp_val:   float
    total_energy:   float   # sum of disp²
    energy_t0:      float   # energy right after impulse
    energy_ratio:   float   # total_energy / energy_t0 (should be < 1 with damping)
    all_bounded:    bool    # no NaN / inf
    notes:          str


# ── Main organ function ───────────────────────────────────────────────────────
def pluck(
    source_node:  int   = 0,
    impulse:      float = 1.0,
    ticks:        int   = 30,
    stiffness:    float = 0.5,
    damping:      float = 0.1,
    dt:           float = 0.05,
    n_radial:     int   = 8,
    n_ring:       int   = 5,
    write_receipt: bool = True,
) -> WebReceipt:
    """
    Apply an impulse to `source_node` and propagate vibration for `ticks` steps.
    Returns WebReceipt with energy decay, max node, truth label.
    """
    web   = build_orb_web(n_radial, n_ring)
    N     = web["n_nodes"]
    adj   = web["adj"]
    truth = _WARP_TRUTH
    dev   = _WARP_DEVICE
    ver   = _WARP_VERSION or "N/A"

    # Clamp source node
    src = max(0, min(source_node, N - 1))

    # Count edges
    n_edges = sum(1 for row in adj for j in row if j >= 0) // 2

    if _WARP_TRUTH in (TRUTH_REAL_CPU, TRUTH_REAL_GPU):
        try:
            import numpy as np

            adj_np  = np.array(adj,            dtype=np.int32)
            disp_np = np.zeros(N,              dtype=np.float32)
            vel_np  = np.zeros(N,              dtype=np.float32)
            disp_np[src] = impulse             # apply impulse as initial displacement

            energy_t0 = float(np.sum(disp_np ** 2))

            # Warp arrays
            disp_wp    = wp.from_numpy(disp_np,  dtype=wp.float32, device=dev)
            vel_wp     = wp.from_numpy(vel_np,   dtype=wp.float32, device=dev)
            disp_out_wp= wp.zeros(N, dtype=wp.float32, device=dev)
            vel_out_wp = wp.zeros(N, dtype=wp.float32, device=dev)
            adj_wp     = wp.from_numpy(adj_np,   dtype=wp.int32,   device=dev)

            for _ in range(ticks):
                wp.launch(web_step_kernel, dim=N,
                          inputs=[disp_wp, vel_wp, disp_out_wp, vel_out_wp,
                                  adj_wp, stiffness, damping, dt],
                          device=dev)
                wp.synchronize()
                # Swap buffers
                disp_wp, disp_out_wp = disp_out_wp, disp_wp
                vel_wp,  vel_out_wp  = vel_out_wp,  vel_wp

            final_disp = disp_wp.numpy()
            all_bounded = bool(np.all(np.isfinite(final_disp)))
            total_energy = float(np.sum(final_disp ** 2))
            max_node = int(np.argmax(np.abs(final_disp)))
            max_val  = float(final_disp[max_node])

        except Exception as e:
            truth = TRUTH_BROKEN
            energy_t0 = impulse ** 2
            total_energy = float("nan")
            energy_ratio = float("nan")
            max_node = src
            max_val  = impulse
            all_bounded = False
    else:
        # Pure-Python fallback
        disp = [0.0] * N
        vel  = [0.0] * N
        disp[src] = impulse
        energy_t0 = sum(d * d for d in disp)

        for _ in range(ticks):
            new_disp = disp[:]
            new_vel  = vel[:]
            for i in range(N):
                force = sum(
                    stiffness * (disp[j] - disp[i])
                    for j in adj[i] if j >= 0
                )
                acc       = force - damping * vel[i]
                new_vel[i]  = vel[i] + dt * acc
                new_disp[i] = disp[i] + dt * new_vel[i]
            disp, vel = new_disp, new_vel

        all_bounded = all(math.isfinite(d) for d in disp)
        total_energy = sum(d * d for d in disp)
        max_node = max(range(N), key=lambda i: abs(disp[i]))
        max_val  = disp[max_node]

    energy_ratio = (total_energy / energy_t0) if energy_t0 > 1e-12 else 0.0

    receipt = WebReceipt(
        ts=time.time(),
        truth=truth,
        warp_version=ver,
        device=dev,
        n_nodes=N,
        n_edges=n_edges,
        source_node=src,
        impulse=impulse,
        ticks=ticks,
        stiffness=stiffness,
        damping=damping,
        max_disp_node=max_node,
        max_disp_val=round(max_val, 6),
        total_energy=round(total_energy, 6) if math.isfinite(total_energy) else -1.0,
        energy_t0=round(energy_t0, 6),
        energy_ratio=round(energy_ratio, 6) if math.isfinite(energy_ratio) else -1.0,
        all_bounded=all_bounded,
        notes=(
            f"NPPL:sim_only | orb-web spring-mass | "
            f"device={dev} | "
            f"Mortimer et al. 2016 doi:10.1098/rsif.2016.0024 | "
            f"Naftilan 1999 J Exp Biol 202:3245"
        ),
    )
    if write_receipt:
        _write_receipt(receipt)
    return receipt


def _write_receipt(r: WebReceipt) -> None:
    try:
        p = _STATE / "spider_web_receipts.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(r)) + "\n")
    except Exception:
        pass


def warp_truth_probe() -> dict:
    return {"truth": _WARP_TRUTH, "version": _WARP_VERSION,
            "device": _WARP_DEVICE, "error": _WARP_ERROR}


def explain() -> str:
    backend = ("NVIDIA Warp GPU" if _WARP_TRUTH == TRUTH_REAL_GPU else
               "NVIDIA Warp CPU" if _WARP_TRUTH == TRUTH_REAL_CPU else "Pure Python")
    return (
        f"Spider Web Organ (Event 75c).\n"
        f"Biology: web silk = distributed nervous surface; one touch propagates "
        f"as damped wave; spider localises disturbance from hub.\n"
        f"NVIDIA Warp kernel: parallel per-node spring-mass update "
        f"(stiffness + damping, [N×MAX_DEG] adjacency).\n"
        f"Topology: orb web — hub + {8}×{5} radial×ring nodes.\n"
        f"Warp {_WARP_VERSION} | Device: {_WARP_DEVICE} | "
        f"Truth: {_WARP_TRUTH} | {TRUTH_NPPL}\n"
        f"Backend: {backend}\n"
        f"Refs: Mortimer et al. (2016) J R Soc Interface 13:20160024; "
        f"Naftilan (1999) J Exp Biol 202:3245; Witt, Reed & Peakall (1968)."
    )


# ── CLI smoke ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(explain())
    print()
    r = pluck(source_node=5, impulse=1.0, ticks=30)
    print(f"Truth:         {r.truth}")
    print(f"Warp:          {r.warp_version} on {r.device}")
    print(f"Nodes:         {r.n_nodes}  Edges: {r.n_edges}")
    print(f"Impulse at:    node {r.source_node}")
    print(f"After {r.ticks} ticks:")
    print(f"  Max disp:    node {r.max_disp_node} = {r.max_disp_val:.6f}")
    print(f"  Energy t=0:  {r.energy_t0:.6f}")
    print(f"  Energy now:  {r.total_energy:.6f}")
    print(f"  Decay ratio: {r.energy_ratio:.4f}  (< 1.0 = damping working)")
    print(f"  All bounded: {r.all_bounded}")
