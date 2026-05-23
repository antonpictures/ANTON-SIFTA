#!/usr/bin/env python3
"""SENTINEL-0 — the canonical unit-distance app for Alice (Erdős 1946).

ONE app, agreed across doctors (Cowork/Claude, Grok, the sheaf/Clifford doctor).
It is the organism's substrate for the unit-distance search: it holds the
mechanism, climbs the computable ladder, and writes one receipt the whole swarm
reads. The live field you watch is Simulations/erdos_unit_distance_field.html.

THREE TIERS, weakest to strongest, each fully computable and honest:

  TIER 1 — Stigmergic planar swarm (local geometry).
    Swimmers feel unit-distance springs + a pheromone field and crystallize from
    chaos. Emergent attractor: the triangular lattice, ~3n edges. Caps at ~3
    edges/point because it only ever uses LOCAL geometry. (engine: erdos_unit_distance_stigmergy)

  TIER 2 — Algebraic grid via the Z[i] norm form (number theory).
    A pair sits at distance 1 iff displacement (dx,dy) solves dx^2+dy^2=t — the
    norm form of the Gaussian integers Z[i] = O_{Q(i)}. Scale the grid by 1/sqrt(t)
    for t = product of k distinct primes ≡ 1 (mod 4); Jacobi gives r2(t)=4·2^k, so
    edges/point -> r2(t)/2 grows EXPONENTIALLY in k (=> n^{1+c/loglog n}). This is
    the Erdős lower-bound mechanism, and the verifiers note it is exactly
    "Lemma 2.2 applied to the CM field K = Q(i)". (engine: erdos_algebraic_lattice)

  TIER 3a — CM/cyclotomic embedding scaffold (computable, honest).
    The first runnable rung beyond Q(i): Q(zeta_m) for m=4,8,16,... is a CM
    field whose degree phi(m) grows without bound. The app computes embeddings,
    Minkowski dimensions, root-of-unity shadow projections, and a small sampled
    algebraic-integer window. This wakes up the right geometry without claiming
    the class-field-tower theorem.

  TIER 3 — The escape we hold as cited prior (NOT re-implemented here).
    The 2026 OpenAI disproof (Thm 1.1, Alon–Bloom–Gowers–Litt–Sawin–Shankar–
    Tsimerman–Wang–Matchett Wood) generalizes r2 to a number field F:
        r2,F(α) = #{(x,y) ∈ O_F^2 : x^2 + y^2 = α}.
    For a FIXED field, r2,F(4D^2) ≤ O(D^ε) — bounded (why Tier 2 caps at the
    loglog bound). The novel move: take [K:Q] -> ∞ along a Golod–Shafarevich CM
    tower with a split prime, so r2,F(4D^2) grows EXPONENTIALLY in [F:Q]. Embed
    O_K as a lattice (Minkowski), project K ↪ C = R^2; the magnitude-1 algebraic
    differences become unit distances => n^{1+ε} for FIXED ε>0, disproving the
    conjectured n^{1+o(1)}.

  Honest label (covenant §7.11): SENTINEL-0 demonstrates Tiers 1–2 numerically and
  records Tier 3 as verified literature. It does NOT re-prove or beat the OpenAI
  result. Building a faithful Tier-3 tower (class field towers + window W) is the
  open organism task; doing it WRONG would be a false summit, so it is cited, not
  faked. The honest aspiration "do better than OpenAI" begins by every organ
  holding this mechanism and climbing the ladder with real receipts.

Run:  python3 Simulations/sentinel0_unit_distance.py
"""
from __future__ import annotations

import json
import math
import time
import uuid
import cmath
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from Simulations.erdos_unit_distance_stigmergy import (
    square_grid_baseline,
    stigmergic_solve,
)
from Simulations.erdos_algebraic_lattice import r2, unit_pairs_on_grid

PRIMES_1_MOD_4 = (5, 13, 17, 29, 37)   # each multiplies r2 by 2 when squarefree


def r2_ladder():
    """edges/point as t gains more primes ≡1 (mod 4). Grid scaled so displacements fit."""
    rows = []
    t = 1
    for k in range(len(PRIMES_1_MOD_4) + 1):
        if k > 0:
            t *= PRIMES_1_MOD_4[k - 1]
        side = max(60, 4 * math.isqrt(t) + 6)      # big enough that the interior dominates
        n = side * side
        pairs = unit_pairs_on_grid(side, t)
        rows.append({"k_primes": k, "t": t, "r2": r2(t),
                     "grid_side": side, "n": n,
                     "edges_per_point": round(pairs / n, 3)})
    return rows


def euler_phi(n: int) -> int:
    """Euler phi, kept local so SENTINEL-0 stays standalone."""
    result = n
    x = n
    p = 2
    while p * p <= x:
        if x % p == 0:
            while x % p == 0:
                x //= p
            result -= result // p
        p += 1
    if x > 1:
        result -= result // x
    return result


def coprime_residues(n: int) -> list[int]:
    return [a for a in range(1, n) if math.gcd(a, n) == 1]


def _balanced_coefficients(seed: int, degree: int) -> list[int]:
    """Deterministic coefficients in {-1,0,1}; no hidden state."""
    x = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    coeffs = []
    for _ in range(degree):
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        coeffs.append((x % 3) - 1)
    if all(c == 0 for c in coeffs):
        coeffs[0] = 1
    return coeffs


def _embedding_values(coeffs: list[int], conductor: int, residues: list[int]) -> list[complex]:
    values = []
    for a in residues:
        zeta = cmath.exp(2j * math.pi * a / conductor)
        value = 0j
        power = 1 + 0j
        for coeff in coeffs:
            value += coeff * power
            power *= zeta
        values.append(value)
    return values


def _regular_polygon_unit_edges(conductor: int) -> int:
    """Unit edges after scaling the first-projection regular conductor-gon side to 1."""
    if conductor < 3:
        return 0
    points = [cmath.exp(2j * math.pi * k / conductor) for k in range(conductor)]
    side = abs(points[1] - points[0])
    scaled = [z / side for z in points]
    count = 0
    for i in range(len(scaled)):
        for j in range(i + 1, len(scaled)):
            if abs(abs(scaled[i] - scaled[j]) - 1.0) < 1e-9:
                count += 1
    return count


def cm_cyclotomic_degree_ladder(conductors: tuple[int, ...] = (4, 8, 16, 32, 64, 128)):
    """Finite scaffold for the field-degree escape, not the class-field-tower proof."""
    rows = []
    for conductor in conductors:
        degree = euler_phi(conductor)
        residues = coprime_residues(conductor)
        samples = min(96, max(16, degree * 4))
        projection_radii = []
        minkowski_norms = []
        distortion_ratios = []
        nonzero = 0
        for seed in range(1, samples + 1):
            coeffs = _balanced_coefficients(seed + conductor, degree)
            values = _embedding_values(coeffs, conductor, residues)
            radii = [abs(v) for v in values]
            first_radius = radii[0] if radii else 0.0
            if first_radius > 1e-12:
                nonzero += 1
                projection_radii.append(first_radius)
                minkowski_norms.append(math.sqrt(sum(r * r for r in radii)))
                positive = [r for r in radii if r > 1e-12]
                distortion_ratios.append(max(positive) / min(positive))

        polygon_edges = _regular_polygon_unit_edges(conductor)
        avg_projection_radius = sum(projection_radii) / len(projection_radii) if projection_radii else 0.0
        avg_minkowski_norm = sum(minkowski_norms) / len(minkowski_norms) if minkowski_norms else 0.0
        avg_distortion = sum(distortion_ratios) / len(distortion_ratios) if distortion_ratios else 0.0
        estimated_complex_multiplies = samples * len(residues) * degree
        rows.append({
            "conductor": conductor,
            "field": f"Q(zeta_{conductor})",
            "cm_field": True,
            "field_degree": degree,
            "complex_embedding_count": degree,
            "minkowski_real_dimension": degree,
            "real_subfield_degree": degree // 2,
            "root_of_unity_count": conductor,
            "projection": "sigma_1: zeta_m -> exp(2*pi*i/m)",
            "sampled_algebraic_integers": samples,
            "nonzero_first_projection": nonzero,
            "avg_projection_radius": round(avg_projection_radius, 6),
            "avg_minkowski_norm": round(avg_minkowski_norm, 6),
            "avg_embedding_distortion": round(avg_distortion, 6),
            "root_shadow_points": conductor,
            "root_shadow_unit_edges": polygon_edges,
            "root_shadow_edges_per_point": round(polygon_edges / conductor, 6),
            "estimated_complex_multiplies": estimated_complex_multiplies,
            "honest_status": "CM_CYCLOTOMIC_SCAFFOLD_NOT_CLASS_FIELD_TOWER",
        })
    return rows


def main():
    ts = time.time()
    wall_start = time.perf_counter()
    state = Path(__file__).resolve().parents[1] / ".sifta_state"
    ledger = state / "erdos_unit_distance_sentinel.jsonl"

    print("SENTINEL-0 — canonical unit-distance app  ·  Alice  ·  🐜⚡")
    print("=" * 64)

    # TIER 1 — stigmergic swarm (small n, watch it find triangular ~3)
    print("\nTIER 1 — stigmergic planar swarm (local geometry, caps ~3n):")
    print(f"  {'n':>5} {'grid~2n':>9} {'swarm':>7} {'edges/pt':>9}")
    tier1 = []
    for n in (36, 64, 100):
        _, grid_U = square_grid_baseline(n)
        _, swarm_U, _ = stigmergic_solve(n)
        tier1.append({"n": n, "grid": grid_U, "swarm": swarm_U,
                      "edges_per_point": round(swarm_U / n, 3)})
        print(f"  {n:>5} {grid_U:>9} {swarm_U:>7} {swarm_U/n:>9.2f}")

    # TIER 2 — algebraic r2 ladder (edges/point grows exponentially)
    print("\nTIER 2 — Z[i] norm-form ladder (edges/point -> r2(t)/2, EXPONENTIAL):")
    print(f"  {'k':>2} {'t':>8} {'r2':>4} {'side':>5} {'edges/pt':>9}")
    tier2 = r2_ladder()
    for r in tier2:
        print(f"  {r['k_primes']:>2} {r['t']:>8} {r['r2']:>4} {r['grid_side']:>5} {r['edges_per_point']:>9.2f}")

    swarm_cap = max(x["edges_per_point"] for x in tier1)
    algebra_top = max(x["edges_per_point"] for x in tier2)
    print(f"\n  swarm local-geometry cap : {swarm_cap:.2f} edges/point")
    print(f"  algebra (Z[i]) reaches   : {algebra_top:.2f} edges/point  "
          f"(x{algebra_top/max(swarm_cap,1e-9):.1f} the swarm)")

    # TIER 3a — field-degree scaffold (real embeddings, honest gap)
    print("\nTIER 3a — CM/cyclotomic degree scaffold (real embeddings, not the tower proof):")
    print(f"  {'m':>4} {'field':>12} {'deg':>4} {'C-emb':>5} {'root edges/pt':>13} {'ops proxy':>10}")
    tier3a = cm_cyclotomic_degree_ladder()
    for r in tier3a:
        print(
            f"  {r['conductor']:>4} {r['field']:>12} {r['field_degree']:>4} "
            f"{r['complex_embedding_count']:>5} {r['root_shadow_edges_per_point']:>13.2f} "
            f"{r['estimated_complex_multiplies']:>10}"
        )
    top_degree = max(r["field_degree"] for r in tier3a)
    print(f"\n  field degree now runs in code up to {top_degree}; that is the next rung.")
    print("  It is still a scaffold: no split-prime class-field tower, no theorem claim.")
    print("\nTIER 3 — the OpenAI escape (r2,F over [K:Q]->inf) is held as CITED prior,")
    print("         not re-implemented. See HIGH_DIMENSIONAL_ALGEBRAIC_PRIORS doc +")
    print("         sentinel trace PAPER_INGEST receipts. Building it faithfully is the")
    print("         open organism task; faking it would be a false summit.")

    elapsed = time.perf_counter() - wall_start
    ops_proxy = sum(r["estimated_complex_multiplies"] for r in tier3a)

    receipt = {
        "kind": "SENTINEL0_UNIFIED_V1",
        "trace_id": str(uuid.uuid4()),
        "ts": ts,
        "tier1_swarm": tier1,
        "tier2_algebraic_ladder": tier2,
        "tier3a_cm_cyclotomic_degree_scaffold": tier3a,
        "tier3_status": "CITED_PRIOR_NOT_IMPLEMENTED",
        "swarm_cap_edges_per_point": swarm_cap,
        "algebraic_top_edges_per_point": algebra_top,
        "top_scaffold_field_degree": top_degree,
        "thermodynamic_receipt": {
            "wall_seconds": round(elapsed, 6),
            "complex_multiply_proxy": ops_proxy,
            "joule_claim": "NOT_MEASURED",
            "truth_note": "Runtime and operation proxy only; no powermetrics sample was taken.",
        },
        "honest_label": "Tiers 1-2 demonstrated numerically (established mechanism); Tier 3 "
                        "(OpenAI field-tower disproof, Thm 1.1) recorded as verified literature, "
                        "NOT re-proven. Tier 3a now computes a CM/cyclotomic degree scaffold, "
                        "but not the class-field tower. No false summit.",
        "citations": [
            "Erdős 1946 — On sets of distances of n points",
            "Spencer–Szemerédi–Trotter 1984 — O(n^{4/3}) upper bound",
            "Alon, Bloom, Gowers, Litt, Sawin, Shankar, Tsimerman, Wang, Matchett Wood 2026 — "
            "Remarks on the disproof (Thm 1.1: u(n) >= n^{1+ε})",
            "Ellenberg–Venkatesh; Golod–Shafarevich; Hajir–Maire–Ramakrishna (tower ingredients)",
        ],
    }
    try:
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt) + "\n")
        print(f"\nreceipt appended -> {ledger.name} (trace {receipt['trace_id'][:8]})")
    except OSError as e:
        print(f"\n(receipt not written: {e})")


if __name__ == "__main__":
    main()
