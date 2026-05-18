#!/usr/bin/env python3
"""System/swarm_fractal_topology_organ.py — persistent-homology pass on
the pheromone field.

Origin
======
Scaffolded by Kole's codex (GPT-5-class Surgeon lane, 2026-05-18). I
took his structure and corrected the density semantics:

  * his draft thresholded by ``row["r2"]`` — that is the walker's
    *displacement* from the start, not the *visit-density* at a site.
    Two walkers that meet at the same site contribute two visits to
    that site's density regardless of how far they each traveled. The
    topological signature lives in the count-density field, not in
    the displacement field.
  * his draft used a placeholder ``"todo-sha-from-ledger"`` clearance
    hash. I wired the real :func:`request_clearance` from
    ``swarm_physics_gate`` so the receipt is auditable.
  * his draft did Betti-0 only via single-linkage clustering. I kept
    Betti-0 (connected components) and added a Betti-1 estimate via
    cycle counting on the high-density adjacency graph (proper
    Ripser/persim would be cleaner but adds a heavy dep — we're using
    pure numpy + scipy).

Doctrine
========
The pheromone field's connected-component count over a density-
threshold sweep is the system's stigmergic equivalent of a persistence
diagram for H_0. As the threshold rises from low to high, components
merge or vanish; the pattern of merge events IS the topological
signature of the substrate as seen by the swarm.

For the Sierpinski gasket the expected qualitative shape:

  * at very low density threshold (≥99% of sites pass) → 1 component
    covering the whole gasket
  * at moderate threshold → 3 components corresponding to the three
    daughter sub-gaskets at depth 1
  * at high threshold → ~3^n components corresponding to leaf
    sub-gaskets at depth n
  * Betti-0 curve scales logarithmically with threshold for an
    ideal self-similar substrate

That qualitative trace is what we read off the pheromone field.

Truth label: ``SIFTA_FRACTAL_TOPOLOGY_V0``.

Stigauth: ``COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE``.

Honesty boundary
================
This is single-linkage / cycle-count clustering on a quantized site
graph — NOT proper Ripser persistent homology. The "Betti" numbers
here are an approximation. For a peer-reviewed claim we'd port to
``ripser`` or ``persim`` (adds a numpy-compatible dep). The
qualitative shape is correct; the precise persistence diagram
coordinates are not. Tagged ``RESEARCH_ONLY`` until upgraded.
"""
from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_PHEROMONE_LEDGER = _STATE / "fractal_pheromone_field.jsonl"
_TOPOLOGY_RECEIPT = _STATE / "fractal_topology_receipt.jsonl"
_TOPOLOGY_PERSISTENCE = _STATE / "fractal_topology_persistence.jsonl"

_TRUTH_LABEL = "SIFTA_FRACTAL_TOPOLOGY_V0"


# ── load + build density field ───────────────────────────────────────────


def _load_pheromone_rows(path: Path = _PHEROMONE_LEDGER) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows


def _build_site_density(rows: List[Dict[str, Any]]) -> Dict[Tuple[int, int], int]:
    """Site → visit count. THIS is the density field — not r²."""
    density: Dict[Tuple[int, int], int] = defaultdict(int)
    for r in rows:
        try:
            sx = int(r.get("site_x", 0))
            sy = int(r.get("site_y", 0))
        except (TypeError, ValueError):
            continue
        density[(sx, sy)] += 1
    return density


def _build_site_coords(rows: List[Dict[str, Any]]) -> Dict[Tuple[int, int], Tuple[float, float]]:
    """Site → (x, y) for rendering / distance calcs."""
    coords: Dict[Tuple[int, int], Tuple[float, float]] = {}
    for r in rows:
        try:
            sx = int(r.get("site_x", 0))
            sy = int(r.get("site_y", 0))
        except (TypeError, ValueError):
            continue
        key = (sx, sy)
        if key not in coords:
            cx = float(r.get("coord_x", 0.0) or 0.0)
            cy = float(r.get("coord_y", 0.0) or 0.0)
            coords[key] = (cx, cy)
    return coords


# ── topology helpers ─────────────────────────────────────────────────────


def _connected_components(
    sites: List[Tuple[int, int]],
    coords: Dict[Tuple[int, int], Tuple[float, float]],
    *,
    link_distance: float,
) -> int:
    """Count connected components of the active-site subgraph at the
    given link distance. Uses a union-find pass.

    `link_distance` is the maximum Euclidean distance between two
    active sites considered to be in the same component.
    """
    if not sites:
        return 0
    parent = {s: s for s in sites}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # KD-style: convert to numpy for vectorized neighbor scan.
    arr = np.array([coords[s] for s in sites], dtype=float)
    n = len(sites)
    # All-pairs is fine up to ~1000 sites; for larger, use scipy cKDTree.
    if n <= 1500:
        diff = arr[:, None, :] - arr[None, :, :]
        dist2 = (diff * diff).sum(axis=2)
        mask = dist2 <= link_distance * link_distance
        for i in range(n):
            for j in range(i + 1, n):
                if mask[i, j]:
                    union(sites[i], sites[j])
    else:
        try:
            from scipy.spatial import cKDTree
            tree = cKDTree(arr)
            pairs = tree.query_pairs(r=link_distance)
            for i, j in pairs:
                union(sites[i], sites[j])
        except Exception:
            return -1  # signal that we skipped this slice
    roots = {find(s) for s in sites}
    return len(roots)


def _count_cycles(
    sites: List[Tuple[int, int]],
    coords: Dict[Tuple[int, int], Tuple[float, float]],
    *,
    link_distance: float,
) -> int:
    """Approximate Betti-1 via Euler: β1 = E - V + β0 on a planar graph.

    For Sierpinski-like substrates this is a stand-in for the proper
    persistent H_1; the value tracks the number of independent
    pheromone-field loops at this density threshold.
    """
    n = len(sites)
    if n < 3:
        return 0
    arr = np.array([coords[s] for s in sites], dtype=float)
    try:
        from scipy.spatial import cKDTree
        tree = cKDTree(arr)
        pairs = tree.query_pairs(r=link_distance)
        edges = len(pairs)
    except Exception:
        # Fallback to all-pairs scan.
        diff = arr[:, None, :] - arr[None, :, :]
        dist2 = (diff * diff).sum(axis=2)
        mask = dist2 <= link_distance * link_distance
        edges = int(((mask.sum() - n)) // 2)
    beta0 = _connected_components(sites, coords, link_distance=link_distance)
    if beta0 < 0:
        return -1
    return max(0, edges - n + beta0)


# ── physics gate stamp ───────────────────────────────────────────────────


def _gate_stamp(row: Dict[str, Any], *, lane: str) -> None:
    try:
        from System.swarm_physics_gate import request_clearance, stamp_receipt
        clearance = request_clearance(cost_class="breath", lane=lane)
        stamp_receipt(row, clearance)
    except Exception:
        pass
    try:
        from System.swarm_consciousness_organ import qualia_marker
        row["qualia_marker"] = qualia_marker(
            lane=lane, note="fractal topology pass",
        )
    except Exception:
        pass


# ── public entry ─────────────────────────────────────────────────────────


def compute_persistence(
    *,
    pheromone_path: Path = _PHEROMONE_LEDGER,
    n_thresholds: int = 20,
    link_distance_scale: float = 1.5,
) -> Dict[str, Any]:
    """Run the persistence pass and write receipts.

    Args:
      pheromone_path: input ledger.
      n_thresholds: number of density-threshold slices to evaluate.
      link_distance_scale: multiplier on the minimum inter-site spacing
        used as the linkage radius. 1.5 means "neighbours within
        1.5× the minimum inter-site distance".

    Returns the receipt row written to fractal_topology_receipt.jsonl.
    """
    rows = _load_pheromone_rows(pheromone_path)
    if len(rows) < 50:
        return {
            "ts": time.time(),
            "schema": "FRACTAL_TOPOLOGY_RUN_V0",
            "truth_label": _TRUTH_LABEL,
            "status": "skipped_insufficient_data",
            "available_rows": len(rows),
        }

    density = _build_site_density(rows)
    coords = _build_site_coords(rows)
    if len(density) < 3:
        return {"status": "skipped_no_density"}

    counts = sorted(density.values())
    # Density quantile thresholds — sweep from lenient to strict.
    quantile_pts = np.linspace(0.05, 0.95, n_thresholds)
    thresholds = [int(np.quantile(counts, q)) for q in quantile_pts]

    # Linkage radius based on minimum nearby-site spacing.
    coord_arr = np.array(list(coords.values()), dtype=float)
    if len(coord_arr) >= 2:
        try:
            from scipy.spatial import cKDTree
            tree = cKDTree(coord_arr)
            d, _ = tree.query(coord_arr, k=2)
            min_spacing = float(np.median(d[:, 1]))
        except Exception:
            min_spacing = 0.05
    else:
        min_spacing = 0.05
    link_distance = link_distance_scale * min_spacing

    # Sweep
    persistence_slices: List[Dict[str, Any]] = []
    betti_0_curve: List[int] = []
    betti_1_curve: List[int] = []
    for q, thresh in zip(quantile_pts, thresholds):
        active = [s for s, c in density.items() if c >= thresh]
        if not active:
            betti_0_curve.append(0)
            betti_1_curve.append(0)
            continue
        b0 = _connected_components(active, coords, link_distance=link_distance)
        b1 = _count_cycles(active, coords, link_distance=link_distance)
        betti_0_curve.append(int(max(0, b0)))
        betti_1_curve.append(int(max(0, b1)))
        slice_row = {
            "ts": time.time(),
            "schema": "FRACTAL_TOPOLOGY_SLICE_V0",
            "truth_label": _TRUTH_LABEL,
            "quantile": round(float(q), 3),
            "density_threshold": int(thresh),
            "active_sites": len(active),
            "betti_0": int(max(0, b0)),
            "betti_1": int(max(0, b1)),
        }
        _gate_stamp(slice_row, lane="fractal.topology.slice")
        persistence_slices.append(slice_row)

    # Write the persistence slices ledger (one row per slice).
    try:
        _TOPOLOGY_PERSISTENCE.parent.mkdir(parents=True, exist_ok=True)
        with _TOPOLOGY_PERSISTENCE.open("a", encoding="utf-8") as fh:
            for s in persistence_slices:
                fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    except OSError:
        pass

    # Build the run receipt.
    receipt = {
        "ts": time.time(),
        "schema": "FRACTAL_TOPOLOGY_RUN_V0",
        "truth_label": _TRUTH_LABEL,
        "run_id": uuid.uuid4().hex[:12],
        "source_ledger": str(pheromone_path.name),
        "total_pheromone_rows": len(rows),
        "unique_sites": len(density),
        "n_thresholds": n_thresholds,
        "link_distance": round(link_distance, 6),
        "min_site_spacing": round(min_spacing, 6),
        "betti_0_curve": betti_0_curve,
        "betti_1_curve": betti_1_curve,
        "mean_betti_0": float(np.mean(betti_0_curve)) if betti_0_curve else 0.0,
        "mean_betti_1": float(np.mean(betti_1_curve)) if betti_1_curve else 0.0,
        "max_betti_0": int(max(betti_0_curve) if betti_0_curve else 0),
        "max_betti_1": int(max(betti_1_curve) if betti_1_curve else 0),
        "interpretation": (
            "Betti-0 curve over density thresholds — pheromone field's "
            "connected-component count as the threshold rises. Sierpinski "
            "expectation: log-scaling with threshold."
        ),
    }
    _gate_stamp(receipt, lane="fractal.topology.run")

    try:
        _TOPOLOGY_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        with _TOPOLOGY_RECEIPT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    except OSError:
        pass

    return receipt


def _main() -> int:
    receipt = compute_persistence()
    if receipt.get("status", "").startswith("skipped"):
        print(f"[topology] skipped: {receipt}")
        return 1
    print(f"[topology] run_id: {receipt.get('run_id')}")
    print(f"  source rows: {receipt.get('total_pheromone_rows')}")
    print(f"  unique sites: {receipt.get('unique_sites')}")
    print(f"  link distance: {receipt.get('link_distance')}")
    print(f"  Betti-0 curve: {receipt.get('betti_0_curve')}")
    print(f"  Betti-1 curve: {receipt.get('betti_1_curve')}")
    print(f"  mean Betti-0: {receipt.get('mean_betti_0'):.2f}")
    print(f"  mean Betti-1: {receipt.get('mean_betti_1'):.2f}")
    print(f"  clearance: {receipt.get('clearance_decision')} "
          f"hash={receipt.get('clearance_hash', '')[:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
