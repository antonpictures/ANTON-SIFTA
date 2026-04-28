#!/usr/bin/env python3
"""
System/swarm_bat_echolocation.py
══════════════════════════════════════════════════════════════════════
SIFTA Organ: Bat Echolocation (Event 75b)

Biology:
  Bats emit ultrasonic chirps (20–200 kHz FM sweeps). Sound hits
  objects and echoes back. Time-of-flight gives distance. The brain
  processes inter-aural time differences for azimuth and HRTFs for
  elevation. Result: a full 3-D map of nearby space in the dark,
  updated ~20× per second.

NVIDIA Warp layer:
  A Warp kernel casts N rays from an origin point in a hemisphere
  of directions (azimuth × elevation sweep). Each ray is tested
  against M sphere obstacles using ray-sphere intersection math.
  Returns a distance map: one float per ray (distance to nearest
  hit, or max_range if no hit).

  Ray-sphere intersection (per ray i, per obstacle j):
    oc = origin - center_j
    b  = dot(oc, dir_i)
    c  = dot(oc, oc) - r_j²
    discriminant = b² - c
    if discriminant > 0:
        t = -b - sqrt(discriminant)
        if t > 0 and t < min_dist → hit

Truth labels (§8 Covenant):
  REAL_GPU  — warp importable + CUDA device present
  REAL_CPU  — warp importable, CPU/ARM only (Apple Silicon)
  STUB      — warp not installed
  BROKEN    — kernel runtime error

NPPL: simulation / research posture only.
Authors: AG31 (Antigravity/Gemini 2.5 Pro), Architect Ioan George Anton
Date: 2026-04-28
Refs:
  Griffin (1958) Listening in the Dark — discovery of echolocation
  Simmons, Fenton & O'Farrell (1979) Science 203:16 — FM sweep analysis
  Konishi (2003) Annu Rev Neurosci 26:31 — auditory space maps
  NVIDIA Warp: https://developer.nvidia.com/warp-python
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, asdict, field
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

# ── Warp kernel: ray-sphere intersection ─────────────────────────────────────
if _WARP_TRUTH in (TRUTH_REAL_CPU, TRUTH_REAL_GPU):
    @wp.kernel
    def bat_ray_kernel(
        ray_dirs:         wp.array2d(dtype=wp.float32),  # [N, 3]
        obs_centers:      wp.array2d(dtype=wp.float32),  # [M, 3]
        obs_radii:        wp.array(dtype=wp.float32),    # [M]
        origin_x: float, origin_y: float, origin_z: float,
        max_range: float,
        hit_dist:  wp.array(dtype=wp.float32),           # [N] out
        hit_obj:   wp.array(dtype=wp.int32),             # [N] out
    ):
        """
        Per-ray: test against all sphere obstacles, record nearest hit.
        hit_dist[i] = distance to nearest intersection (max_range if miss).
        hit_obj[i]  = obstacle index (-1 if miss).
        """
        i = wp.tid()
        dx = ray_dirs[i, 0]
        dy = ray_dirs[i, 1]
        dz = ray_dirs[i, 2]

        min_dist = max_range
        nearest  = wp.int32(-1)

        n_obs = obs_centers.shape[0]
        for j in range(n_obs):
            # oc = origin - center_j
            ocx = origin_x - obs_centers[j, 0]
            ocy = origin_y - obs_centers[j, 1]
            ocz = origin_z - obs_centers[j, 2]
            rj  = obs_radii[j]

            b   = ocx*dx + ocy*dy + ocz*dz
            c   = ocx*ocx + ocy*ocy + ocz*ocz - rj*rj
            disc = b*b - c
            if disc > 0.0:
                t = -b - wp.sqrt(disc)
                if t > 0.001 and t < min_dist:
                    min_dist = t
                    nearest  = wp.int32(j)

        hit_dist[i] = min_dist
        hit_obj[i]  = nearest


# ── Scene / obstacle helpers ──────────────────────────────────────────────────
@dataclass
class Obstacle:
    cx: float
    cy: float
    cz: float
    radius: float
    label: str = "obstacle"


DEFAULT_SCENE = [
    Obstacle(5.0, 0.0, 0.0, 0.8, "wall_front"),
    Obstacle(0.0, 4.0, 0.0, 0.6, "wall_right"),
    Obstacle(-3.0, 2.0, 1.5, 0.5, "ceiling_pip"),
    Obstacle(2.0, -3.0, 0.5, 1.0, "prey"),      # the bat is hunting this
    Obstacle(0.0, 0.0, -4.0, 1.2, "floor_rock"),
]


def _build_ray_dirs(n_az: int = 18, n_el: int = 9) -> List[Tuple[float, float, float]]:
    """Generate a hemisphere of ray directions (azimuth × elevation grid)."""
    dirs = []
    for ai in range(n_az):
        az = (2 * math.pi * ai) / n_az
        for ei in range(n_el):
            el = 0.0 if n_el == 1 else (math.pi / 2) * ei / (n_el - 1)
            dx = math.cos(el) * math.cos(az)
            dy = math.cos(el) * math.sin(az)
            dz = math.sin(el)
            mag = math.sqrt(dx*dx + dy*dy + dz*dz)
            dirs.append((dx/mag, dy/mag, dz/mag))
    return dirs


# ── Receipt dataclass ─────────────────────────────────────────────────────────
@dataclass
class EchoReceipt:
    ts:            float
    truth:         str
    warp_version:  str
    device:        str
    n_rays:        int
    n_obstacles:   int
    origin:        Tuple[float, float, float]
    max_range:     float
    hit_count:     int        # rays that hit something
    nearest_dist:  float      # distance to closest hit
    nearest_obj:   str        # label of closest obstacle
    mean_hit_dist: float      # mean distance of all hits
    distance_map:  List[float]  # per-ray distances (max_range = miss)
    notes:         str


# ── Main organ function ───────────────────────────────────────────────────────
def emit_pulse(
    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    scene:  Optional[List[Obstacle]] = None,
    n_az:   int = 18,
    n_el:   int = 9,
    max_range: float = 10.0,
    write_receipt: bool = True,
) -> EchoReceipt:
    """
    Emit an echolocation pulse from `origin`.
    Cast n_az × n_el rays against all obstacles in `scene`.
    Returns EchoReceipt with full distance map and truth label.
    """
    scene = DEFAULT_SCENE if scene is None else scene
    dirs  = _build_ray_dirs(n_az, n_el)
    N     = len(dirs)
    M     = len(scene)
    truth = _WARP_TRUTH
    version = _WARP_VERSION or "N/A"
    device  = _WARP_DEVICE

    ox, oy, oz = float(origin[0]), float(origin[1]), float(origin[2])

    if M == 0:
        # Empty scene — all rays miss
        dist_map = [max_range] * N
        obj_map  = [-1] * N
    elif truth in (TRUTH_REAL_CPU, TRUTH_REAL_GPU):
        try:
            import numpy as np

            dirs_np  = np.array(dirs,  dtype=np.float32)          # [N,3]
            obs_c_np = np.array([[o.cx, o.cy, o.cz] for o in scene],
                                dtype=np.float32)                  # [M,3]
            obs_r_np = np.array([o.radius for o in scene],
                                dtype=np.float32)                  # [M]
            hit_d_np = np.full(N, max_range, dtype=np.float32)
            hit_o_np = np.full(N, -1, dtype=np.int32)

            d_wp = wp.from_numpy(dirs_np,  dtype=wp.float32, device=device)
            c_wp = wp.from_numpy(obs_c_np, dtype=wp.float32, device=device)
            r_wp = wp.from_numpy(obs_r_np, dtype=wp.float32, device=device)
            hd_wp= wp.from_numpy(hit_d_np, dtype=wp.float32, device=device)
            ho_wp= wp.from_numpy(hit_o_np, dtype=wp.int32,   device=device)

            wp.launch(
                bat_ray_kernel,
                dim=N,
                inputs=[d_wp, c_wp, r_wp, ox, oy, oz,
                        max_range, hd_wp, ho_wp],
                device=device,
            )
            wp.synchronize()

            dist_map = hd_wp.numpy().tolist()
            obj_map  = ho_wp.numpy().tolist()

        except Exception as e:
            truth    = TRUTH_BROKEN
            dist_map = [max_range] * N
            obj_map  = [-1] * N
    else:
        # Pure-Python fallback
        dist_map = []
        obj_map  = []
        for (dx, dy, dz) in dirs:
            best_t = max_range
            best_j = -1
            for j, obs in enumerate(scene):
                ocx = ox - obs.cx
                ocy = oy - obs.cy
                ocz = oz - obs.cz
                b   = ocx*dx + ocy*dy + ocz*dz
                c   = ocx*ocx + ocy*ocy + ocz*ocz - obs.radius**2
                disc = b*b - c
                if disc > 0:
                    t = -b - math.sqrt(disc)
                    if t > 0.001 and t < best_t:
                        best_t = t
                        best_j = j
            dist_map.append(best_t)
            obj_map.append(best_j)

    # Summarise
    hits = [(d, j) for d, j in zip(dist_map, obj_map) if j >= 0]
    hit_count    = len(hits)
    if hits:
        nearest_dist = min(d for d, _ in hits)
        nearest_j    = min(hits, key=lambda x: x[0])[1]
        nearest_obj  = scene[nearest_j].label if 0 <= nearest_j < M else "?"
        mean_hit_dist= sum(d for d, _ in hits) / hit_count
    else:
        nearest_dist  = max_range
        nearest_obj   = "none"
        mean_hit_dist = max_range

    receipt = EchoReceipt(
        ts=time.time(),
        truth=truth,
        warp_version=version,
        device=device,
        n_rays=N,
        n_obstacles=M,
        origin=origin,
        max_range=max_range,
        hit_count=hit_count,
        nearest_dist=round(nearest_dist, 4),
        nearest_obj=nearest_obj,
        mean_hit_dist=round(mean_hit_dist, 4),
        distance_map=[round(d, 4) for d in dist_map],
        notes=(
            f"NPPL:sim_only | bat FM-sweep ray cast | "
            f"device={device} | "
            f"Griffin 1958; Simmons et al. 1979 doi:10.1126/science.760194"
        ),
    )
    if write_receipt:
        _write_receipt(receipt)
    return receipt


def _write_receipt(r: EchoReceipt) -> None:
    try:
        p = _STATE / "bat_echo_receipts.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        row = asdict(r)
        row["origin"] = list(row["origin"])
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass


def warp_truth_probe() -> dict:
    return {
        "truth":   _WARP_TRUTH,
        "version": _WARP_VERSION,
        "device":  _WARP_DEVICE,
        "error":   _WARP_ERROR,
    }


def explain() -> str:
    backend = "NVIDIA Warp GPU" if _WARP_TRUTH == TRUTH_REAL_GPU else \
              ("NVIDIA Warp CPU" if _WARP_TRUTH == TRUTH_REAL_CPU else "Pure Python")
    return (
        f"Bat Echolocation Organ (Event 75b).\n"
        f"Biology: FM-sweep chirps → ray hits → time-of-flight → 3-D space map.\n"
        f"NVIDIA Warp kernel casts N rays against M sphere obstacles "
        f"via ray-sphere intersection.\n"
        f"Warp {_WARP_VERSION} | Device: {_WARP_DEVICE} | "
        f"Truth: {_WARP_TRUTH} | {TRUTH_NPPL}\n"
        f"Backend: {backend}\n"
        f"Refs: Griffin (1958); Simmons et al. (1979) Science 203:16; "
        f"Konishi (2003) Annu Rev Neurosci 26:31."
    )


# ── CLI smoke ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(explain())
    print()
    r = emit_pulse()
    print(f"Truth:        {r.truth}")
    print(f"Warp:         {r.warp_version} on {r.device}")
    print(f"Rays:         {r.n_rays}")
    print(f"Obstacles:    {r.n_obstacles}")
    print(f"Hits:         {r.hit_count}/{r.n_rays}")
    print(f"Nearest:      {r.nearest_dist:.3f} units → '{r.nearest_obj}'")
    print(f"Mean hit dist:{r.mean_hit_dist:.3f} units")
    print()
    print(f"{'Ray':>5}  {'Distance':>10}  Object")
    print("─" * 40)
    for i, (d, s) in enumerate(zip(r.distance_map, DEFAULT_SCENE * 100)):
        label = ""
        # find which obstacle this ray hit
        if d < r.max_range:
            label = "← HIT"
        if i >= 10:
            break
        print(f"{i:5d}  {d:10.4f}  {label}")
    print(f"  ... ({r.n_rays} rays total)")
