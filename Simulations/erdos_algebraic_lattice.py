#!/usr/bin/env python3
"""SENTINEL-0b — Algebraic escape from the plane (Gaussian-integer norm form).

The planar swarm caps at the triangular optimum (~3n edges) because it uses only
LOCAL geometry. To go higher you must use ALGEBRA, exactly as the field does:

  * The integer grid is the ring of Gaussian integers Z[i].
  * Two grid points are at squared-distance t  iff  their displacement (dx,dy)
    satisfies the NORM FORM   dx^2 + dy^2 = t.
  * The number of such displacements is r2(t) = #{(a,b) in Z^2 : a^2+b^2 = t},
    the sum-of-two-squares function. By Jacobi: r2(t) = 4 * (d_1(t) - d_3(t))
    (divisors of t that are 1 mod 4 minus those 3 mod 4).
  * r2 is UNBOUNDED: choose t = product of distinct primes p ≡ 1 (mod 4); each
    such prime multiplies the representation count. So scale the grid by 1/sqrt(t)
    and every interior point acquires r2(t) unit-distance neighbours.

That is the mechanism behind Erdős's lower bound  u(n) >= n^{1 + c/log log n}:
the maximal order of r2(t) is  2^{(1+o(1)) log t / log log t}.  This file is the
COMPUTABLE PROOF-OF-MECHANISM: pick t, build a grid patch, count exactly, show
edges/point climbing far past the triangular 3 — using number theory, not springs.

Honest label (covenant §7.11): this demonstrates the KNOWN Erdős lower-bound
construction numerically. It does NOT settle the asymptotic conjecture (the gap to
the Szemerédi–Trotter ceiling O(n^{4/3}) stays open). It is the algebraic "shadow"
idea at the level rigorously established in the literature.

Run:  python3 Simulations/erdos_algebraic_lattice.py
"""
from __future__ import annotations

import json
import math
import time
import uuid
from pathlib import Path


def r2_displacements(t: int) -> list[tuple[int, int]]:
    """All integer (dx,dy) with dx^2 + dy^2 = t  (the Z[i] norm-form solutions)."""
    out = []
    r = math.isqrt(t)
    for dx in range(-r, r + 1):
        rem = t - dx * dx
        if rem < 0:
            continue
        dy = math.isqrt(rem)
        if dy * dy == rem:
            for sy in {dy, -dy}:
                out.append((dx, sy))
    return list(set(out))


def r2(t: int) -> int:
    return len(r2_displacements(t))


def unit_pairs_on_grid(side: int, t: int) -> int:
    """Exact # of point pairs at distance 1 on a (side x side) grid scaled by 1/sqrt(t).

    Pair count = for each norm-form displacement (dx,dy) with the pair counted once,
    number of grid positions admitting that displacement = (side-|dx|)*(side-|dy|),
    summed over displacements, divided by 2 (each unordered pair counted twice).
    """
    disp = r2_displacements(t)
    total = 0
    for (dx, dy) in disp:
        ax, ay = abs(dx), abs(dy)
        if ax < side and ay < side:
            total += (side - ax) * (side - ay)
    return total // 2


def main():
    ts = time.time()
    state = Path(__file__).resolve().parents[1] / ".sifta_state"
    ledger = state / "erdos_unit_distance_sentinel.jsonl"

    side = 40                      # ~1600 points; large enough that interior dominates
    n = side * side
    print("SENTINEL-0b — Algebraic escape via Gaussian-integer norm form")
    print("=" * 64)
    print(f"grid {side}x{side} = {n} points; scale = 1/sqrt(t)\n")
    print(f"{'t':>6} {'r2(t)':>6} {'unit_pairs':>11} {'edges/pt':>9}  factor t (primes 1 mod 4)")

    # t values: 1 (plain grid), then products of primes ≡ 1 (mod 4): 5,13,17,29...
    t_values = [1, 2, 5, 25, 65, 325, 1105, 5 * 13 * 17 * 29]
    rows = []
    for t in t_values:
        e = unit_pairs_on_grid(side, t)
        rows.append({"t": t, "r2": r2(t), "unit_pairs": e, "edges_per_point": round(e / n, 3)})
        print(f"{t:>6} {r2(t):>6} {e:>11} {e/n:>9.2f}")

    best = max(rows, key=lambda r: r["edges_per_point"])
    print(f"\nPlanar swarm capped at ~3.0 edges/point (triangular).")
    print(f"Algebraic grid reaches {best['edges_per_point']:.2f} edges/point at "
          f"t={best['t']} (r2={best['r2']}) — the number-theoretic escape.")

    receipt = {
        "kind": "ALGEBRAIC_UNIT_DISTANCE_NORMFORM_V1",
        "trace_id": str(uuid.uuid4()),
        "ts": ts,
        "construction": "Z[i] norm form dx^2+dy^2=t; scale grid by 1/sqrt(t); r2(t) neighbours/point",
        "jacobi": "r2(t) = 4*(d_1(t)-d_3(t)); maximal order 2^{(1+o(1)) log t/log log t}",
        "grid_points": n,
        "results": rows,
        "best": best,
        "honest_label": "HYPOTHESIS/established-construction — numerically demonstrates the Erdős "
                        "lower-bound mechanism (r2-rich scaled grid). NOT a proof of the conjecture; "
                        "the gap to Szemerédi–Trotter O(n^{4/3}) stays open.",
    }
    try:
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt) + "\n")
        print(f"\nreceipt appended -> {ledger.name} (trace {receipt['trace_id'][:8]})")
    except OSError as e:
        print(f"\n(receipt not written: {e})")


if __name__ == "__main__":
    main()
