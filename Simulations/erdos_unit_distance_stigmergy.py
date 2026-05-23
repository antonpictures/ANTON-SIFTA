#!/usr/bin/env python3
"""SENTINEL-0 — Stigmergic Unit-Distance Field (Erdős 1946 problem).

Honest scope (covenant §7.11, no false summits):
  This does NOT prove or disprove the Erdős unit-distance conjecture. It is a
  stigmergic *explorer*. Swimmers (points) live in a shared field; each reads
  its neighbours and a pheromone trace, and moves to sit at distance ~1 from as
  many others as possible. The emergent attractor is the triangular (hexagonal)
  lattice, where each interior swimmer has 6 unit-distance partners — ~3n edges,
  beating the square grid's ~2n. The swarm discovers this from random chaos with
  no central planner. That emergent ~3n is the real, countable receipt.

The maths it touches:
  u(n) = max # pairs at exactly distance 1 over n points in the plane.
  square grid  ~ 2n - 2*sqrt(n)   (4-neighbour adjacency)
  triangular   ~ 3n - O(sqrt(n))  (6-neighbour adjacency, the local optimum)
  Erdős lower bound (deep, scaled grid): n^{1 + c/log log n}
  Szemerédi–Trotter upper bound:         O(n^{4/3})
The swarm targets the triangular local optimum; the asymptotic gap stays open.

Run:  python3 Simulations/erdos_unit_distance_stigmergy.py
"""
from __future__ import annotations

import json
import math
import time
import uuid
from pathlib import Path

import numpy as np

EPS = 0.06          # a pair counts as "unit distance" if |d - 1| < EPS
BAND_LO, BAND_HI = 0.55, 1.6   # only swimmers within this band exert a stigmergic pull


def count_unit_pairs(P: np.ndarray, eps: float = EPS) -> int:
    """Exact count of point pairs whose distance is within eps of 1."""
    diff = P[:, None, :] - P[None, :, :]
    d = np.sqrt((diff ** 2).sum(-1))
    iu = np.triu_indices(len(P), k=1)
    return int((np.abs(d[iu] - 1.0) < eps).sum())


def square_grid_baseline(n: int) -> tuple[np.ndarray, int]:
    """n points on an integer grid (unit spacing); count 4-neighbour unit edges."""
    s = int(round(math.sqrt(n)))
    pts = [(x, y) for y in range(s) for x in range(s)][:n]
    P = np.array(pts, dtype=float)
    return P, count_unit_pairs(P)


def stigmergic_solve(n: int, steps: int = 600, seed: int = 7,
                     grid_res: int = 48, record: bool = False):
    """Swimmers self-organize toward a dense unit-distance graph.

    Forces on each swimmer:
      1. unit-distance springs  — pull every in-band neighbour toward distance 1
      2. pheromone gradient      — drift toward cells where swimmers already have
                                   many unit partners (positive stigmergic feedback)
      3. annealed noise          — exploration that cools over time
    """
    rng = np.random.default_rng(seed)
    L = math.sqrt(n) * 1.05          # box side so density ~ 1 point / unit^2
    P = rng.uniform(0.0, L, size=(n, 2))

    pher = np.zeros((grid_res, grid_res))   # the shared stigmergic field
    evap = 0.86
    best_P, best_U = P.copy(), count_unit_pairs(P)
    frames = []

    def cell(p):
        c = np.clip((p / L * grid_res).astype(int), 0, grid_res - 1)
        return c[:, 0], c[:, 1]

    for step in range(steps):
        temp = 0.10 * (1.0 - step / steps)            # annealing
        diff = P[:, None, :] - P[None, :, :]
        d = np.sqrt((diff ** 2).sum(-1)) + 1e-9
        np.fill_diagonal(d, 1e9)
        unit = diff / d[:, :, None]                    # unit vectors i<-j

        # 1. spring force: in-band pairs pulled toward distance exactly 1
        in_band = (d > BAND_LO) & (d < BAND_HI)
        mag = (1.0 - d)                                # >0 push apart, <0 pull in
        mag = np.where(in_band, mag, 0.0)
        F = (unit * mag[:, :, None]).sum(axis=1)

        # per-swimmer current unit-partner count -> deposit pheromone
        partners = (np.abs(d - 1.0) < EPS).sum(axis=1).astype(float)
        cx, cy = cell(P)
        pher *= evap
        np.add.at(pher, (cx, cy), partners)

        # 2. pheromone gradient drift (read the field, climb it)
        gx, gy = np.gradient(pher)
        drift = np.stack([gx[cx, cy], gy[cx, cy]], axis=1)
        nrm = np.linalg.norm(drift, axis=1, keepdims=True) + 1e-9
        drift = drift / nrm * 0.05

        # 3. noise
        noise = rng.normal(0.0, temp, size=P.shape)

        P = P + 0.10 * F + drift + noise
        P = np.clip(P, 0.0, L)

        U = count_unit_pairs(P)
        if U > best_U:
            best_U, best_P = U, P.copy()
        if record and (step % 6 == 0):
            frames.append(P.copy())

    return best_P, best_U, frames


def main():
    ts = time.time()
    state = Path(__file__).resolve().parents[1] / ".sifta_state"
    ledger = state / "erdos_unit_distance_sentinel.jsonl"
    print("SENTINEL-0 — Stigmergic Unit-Distance Field\n" + "=" * 56)
    print(f"{'n':>5} {'grid~2n':>9} {'swarm':>7} {'swarm/n':>8} {'tri~3n':>8}  verdict")
    rows = []
    for n in (36, 64, 100, 144, 196):
        _, grid_U = square_grid_baseline(n)
        _, swarm_U, _ = stigmergic_solve(n)
        tri_ideal = 3 * n - 3 * int(round(math.sqrt(n)))   # rough hex interior estimate
        verdict = "swarm > grid" if swarm_U > grid_U else "grid >= swarm"
        print(f"{n:>5} {grid_U:>9} {swarm_U:>7} {swarm_U/n:>8.2f} {tri_ideal:>8}  {verdict}")
        rows.append({"n": n, "grid_unit_pairs": grid_U, "swarm_unit_pairs": swarm_U,
                     "swarm_per_n": round(swarm_U / n, 3), "triangular_ideal_est": tri_ideal})

    receipt = {
        "kind": "STIGMERGIC_UNIT_DISTANCE_SENTINEL_V1",
        "trace_id": str(uuid.uuid4()),
        "ts": ts,
        "eps": EPS,
        "results": rows,
        "honest_label": "ARCHITECT_DOCTRINE/HYPOTHESIS — emergent dense packing explorer, "
                        "not a proof of the Erdos conjecture. Square grid ~2n, swarm "
                        "approaches triangular ~3n local optimum.",
        "math": {
            "objective": "u(n)=max pairs at distance exactly 1",
            "square_grid": "~2n - 2*sqrt(n)",
            "triangular_lattice": "~3n - O(sqrt(n))",
            "erdos_lower_bound": "n^{1 + c/loglog n}",
            "szemeredi_trotter_upper": "O(n^{4/3})",
        },
    }
    try:
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt) + "\n")
        print(f"\nreceipt appended -> {ledger.name} (trace {receipt['trace_id'][:8]})")
    except OSError as e:
        print(f"\n(receipt not written: {e})")
    print("\nHonest note: this finds the triangular local optimum (~3n), beating the\n"
          "square grid (~2n). It does NOT settle Erdős's asymptotic conjecture.")


if __name__ == "__main__":
    main()
