"""
System/swarm_code_knowledge_graph_layout.py
═══════════════════════════════════════════════
Round 72 (2026-05-27) — Code Knowledge Graph spatial layout organ.

Pure-Python, deterministic, stdlib-only force-directed layout over the
Round 70 ledgers. Feeds a future Qt viewer (Round 73, on George's mac)
that ONLY renders positions; the math lives here so it can be tested
offline on the Linux sandbox.

Doctrine touchpoints
====================
  - §0 AGI goal: layout is part of Alice's self-model — she can see
    the topology of her own body without us hand-drawing it.
  - §3 node sovereignty: positions are computed from this node's
    ledgers only. We never reach outside the repo.
  - §6 effector immunity: pure read. We never mutate the graph
    ledgers; layout receipts (if requested) write to a separate
    layout-snapshots stream — not the canonical nodes/edges files.
  - §7.5 Python-first: math only — sqrt, hypot. No NumPy. No PyQt.
  - §12 doctrine: pattern (Fruchterman-Reingold + layered angular
    sectors) is industry-standard graph drawing; no GPL code copied.

Algorithm
=========
  1. Load latest-row-wins nodes + edges (via the Round 70 helpers).
  2. Group nodes into LAYERS by top-level directory
     (System / Applications / tests / Utilities / Documents / Other).
  3. Place each layer on an angular sector around a center anchor.
     Seed each node's initial position deterministically from
     sha256(node_id) so the same graph yields the same picture.
  4. Run a few dozen Fruchterman-Reingold iterations:
       repulsion  ≈ k² / d   between every node pair
       attraction ≈ d² / k   along every edge
       layer pull ≈ small spring toward the layer anchor
     Temperature cools linearly so the layout settles.
  5. Compute bounding box. Done.

Output shape
============
    @dataclass LayoutResult:
        positions: dict[node_id, (x, y)]
        layers: dict[node_id, layer_name]
        layer_anchors: dict[layer_name, (x, y)]
        layer_colors: dict[layer_name, "#rrggbb"]
        bounding_box: (min_x, min_y, max_x, max_y)
        params: dict          # iterations / k / seed / etc.
        node_count: int
        edge_count: int

Public surface
══════════════
    LAYER_COLORS               — palette dict[layer_name, hex]
    DEFAULT_LAYERS             — ("System","Applications","tests","Utilities","Documents")
    compute_layout(nodes, edges, *, width, height, iterations, seed, layers)
        → LayoutResult
    compute_layout_from_state(state_dir, *, ...)
        → LayoutResult
    layout_summary_block(result) → str
        small prompt-ready summary for Alice
    layer_of(path)              — top-level directory bucket

This module never raises out of its public surface.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from System import swarm_code_knowledge_graph as graph


# ─── Palette / constants ───────────────────────────────────────────────────

DEFAULT_LAYERS: tuple[str, ...] = (
    "System",
    "Applications",
    "tests",
    "Utilities",
    "Documents",
)

LAYER_COLORS: dict[str, str] = {
    "System":       "#4ade80",   # green  — Alice's organs
    "Applications": "#60a5fa",   # blue   — surfaces / hands
    "tests":        "#fbbf24",   # amber  — proofs
    "Utilities":    "#a78bfa",   # violet — tools
    "Documents":    "#94a3b8",   # slate  — doctrine
    "Other":        "#d4d4d8",   # neutral
}


# ─── Data class ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LayoutResult:
    positions: dict[str, tuple[float, float]]
    layers: dict[str, str]
    layer_anchors: dict[str, tuple[float, float]]
    layer_colors: dict[str, str]
    bounding_box: tuple[float, float, float, float]
    params: dict
    node_count: int
    edge_count: int


# ─── Helpers ───────────────────────────────────────────────────────────────


def _norm(value: object) -> str:
    return str(value or "").strip()


def layer_of(path: str, *, known: Sequence[str] = DEFAULT_LAYERS) -> str:
    """Top-level directory bucket for a node path. Defaults to ``Other``."""
    text = _norm(path).replace("\\", "/")
    if not text:
        return "Other"
    head = text.split("/", 1)[0]
    if head in known:
        return head
    # case-insensitive fallback so 'System' matches 'system'
    head_cf = head.casefold()
    for layer in known:
        if layer.casefold() == head_cf:
            return layer
    return "Other"


def _seed_unit(node_id: str, salt: str = "") -> float:
    """Deterministic [0, 1) value from a node id + salt."""
    digest = hashlib.sha256((salt + "::" + node_id).encode("utf-8")).digest()
    raw = int.from_bytes(digest[:8], "big", signed=False)
    return raw / float(1 << 64)


def _latest_by_node_id(rows: Iterable[Mapping[str, object]]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for row in rows:
        nid = _norm(row.get("node_id"))
        if not nid:
            continue
        prior = latest.get(nid)
        if prior is None or float(row.get("ts") or 0.0) >= float(prior.get("ts") or 0.0):
            latest[nid] = dict(row)
    return latest


# ─── Core layout ───────────────────────────────────────────────────────────


def compute_layout(
    nodes: Sequence[Mapping[str, object]],
    edges: Sequence[Mapping[str, object]],
    *,
    width: float = 1600.0,
    height: float = 1200.0,
    iterations: int = 120,
    seed: int = 70,
    layers: Sequence[str] = DEFAULT_LAYERS,
) -> LayoutResult:
    """Force-directed layout over already-loaded node/edge rows.

    Empty input is allowed — returns an empty LayoutResult. Never raises.
    """
    # Latest-row-wins collapse so duplicate ledger writes don't break us.
    node_rows = _latest_by_node_id(nodes)
    node_ids = list(node_rows.keys())
    n = len(node_ids)
    if n == 0:
        return LayoutResult(
            positions={},
            layers={},
            layer_anchors={},
            layer_colors=dict(LAYER_COLORS),
            bounding_box=(0.0, 0.0, 0.0, 0.0),
            params={
                "iterations": int(iterations),
                "seed": int(seed),
                "width": float(width),
                "height": float(height),
            },
            node_count=0,
            edge_count=0,
        )

    # Group by layer.
    node_layer: dict[str, str] = {}
    layer_members: dict[str, list[str]] = {}
    for nid in node_ids:
        row = node_rows[nid]
        layer = layer_of(_norm(row.get("path")), known=layers)
        node_layer[nid] = layer
        layer_members.setdefault(layer, []).append(nid)

    # Layer anchors arranged around a circle, in deterministic order.
    layer_names = sorted(layer_members.keys())
    cx, cy = width / 2.0, height / 2.0
    anchor_radius = 0.35 * min(width, height)
    layer_anchors: dict[str, tuple[float, float]] = {}
    layer_count = max(1, len(layer_names))
    for i, layer in enumerate(layer_names):
        theta = (2.0 * math.pi * i) / layer_count
        layer_anchors[layer] = (
            cx + anchor_radius * math.cos(theta),
            cy + anchor_radius * math.sin(theta),
        )

    # Deterministic seed: place each node in its layer's wedge.
    positions: dict[str, list[float]] = {}
    salt = f"r72::seed={int(seed)}"
    for layer, members in layer_members.items():
        ax, ay = layer_anchors[layer]
        # Wedge spans a fraction of the circle proportional to layer size,
        # but capped so it doesn't fully overlap neighbouring layers.
        wedge = min(2.0 * math.pi / layer_count, math.pi / 2.0)
        for nid in members:
            u_theta = _seed_unit(nid, salt + "::theta")
            u_r = _seed_unit(nid, salt + "::r")
            local_theta = (u_theta - 0.5) * wedge
            local_r = 60.0 + 160.0 * u_r
            # Direction from layer anchor pointing outward (away from center).
            base_angle = math.atan2(ay - cy, ax - cx)
            angle = base_angle + local_theta
            x = ax + local_r * math.cos(angle)
            y = ay + local_r * math.sin(angle)
            positions[nid] = [x, y]

    # Build adjacency from edges that connect known node ids OR
    # match by (to_path, to_name) into a known node.
    edge_pairs: list[tuple[str, str]] = []
    name_to_id: dict[str, str] = {}
    path_to_id: dict[str, str] = {}
    for nid, row in node_rows.items():
        name = _norm(row.get("name")).casefold()
        path = _norm(row.get("path")).casefold()
        if name:
            name_to_id.setdefault(name, nid)
        if path and not _norm(row.get("name")):
            # File node — index raw path AND dotted-module form so import
            # edges that store "System.alpha" still resolve to a node whose
            # path is "System/alpha.py".
            path_to_id.setdefault(path, nid)
            module = path
            if module.endswith(".py"):
                module = module[:-3]
            module = module.replace("/", ".")
            if module.endswith(".__init__"):
                module = module[: -len(".__init__")]
            if module:
                path_to_id.setdefault(module, nid)

    edge_count_used = 0
    for edge in edges:
        from_id = _norm(edge.get("from_id"))
        if from_id not in positions:
            continue
        to_id = _norm(edge.get("to_id"))
        if to_id and to_id in positions:
            edge_pairs.append((from_id, to_id))
            edge_count_used += 1
            continue
        to_name = _norm(edge.get("to_name")).casefold()
        if to_name and to_name in name_to_id:
            edge_pairs.append((from_id, name_to_id[to_name]))
            edge_count_used += 1
            continue
        to_path = _norm(edge.get("to_path")).casefold()
        if to_path and to_path in path_to_id:
            edge_pairs.append((from_id, path_to_id[to_path]))
            edge_count_used += 1
            continue

    # Fruchterman-Reingold parameters.
    area = max(1.0, float(width) * float(height))
    k = math.sqrt(area / max(1, n))
    temperature = max(width, height) / 10.0
    iters = max(0, int(iterations))
    cool = temperature / max(1, iters)

    for step in range(iters):
        # Repulsion (O(n²) — fine for graphs up to a few thousand nodes).
        disp: dict[str, list[float]] = {nid: [0.0, 0.0] for nid in node_ids}
        for i_a in range(n):
            a = node_ids[i_a]
            ax, ay = positions[a]
            for i_b in range(i_a + 1, n):
                b = node_ids[i_b]
                bx, by = positions[b]
                dx = ax - bx
                dy = ay - by
                d = math.hypot(dx, dy) or 0.01
                # standard FR repulsion
                f = (k * k) / d
                ux = dx / d
                uy = dy / d
                disp[a][0] += ux * f
                disp[a][1] += uy * f
                disp[b][0] -= ux * f
                disp[b][1] -= uy * f

        # Attraction along edges.
        for src, dst in edge_pairs:
            sx, sy = positions[src]
            tx, ty = positions[dst]
            dx = sx - tx
            dy = sy - ty
            d = math.hypot(dx, dy) or 0.01
            f = (d * d) / k
            ux = dx / d
            uy = dy / d
            disp[src][0] -= ux * f
            disp[src][1] -= uy * f
            disp[dst][0] += ux * f
            disp[dst][1] += uy * f

        # Layer pull — spring toward each node's layer anchor. Tuned so
        # layer structure survives the all-pairs repulsion even on small
        # graphs.
        pull = 0.15
        for nid in node_ids:
            ax, ay = layer_anchors[node_layer[nid]]
            px, py = positions[nid]
            disp[nid][0] -= (px - ax) * pull
            disp[nid][1] -= (py - ay) * pull

        # Apply displacement, capped by current temperature, and clamp the
        # result to the canvas bounding box so a few oversized repulsion
        # vectors can't fly nodes off to infinity.
        margin = 0.05 * min(width, height)
        x_lo, x_hi = -margin, width + margin
        y_lo, y_hi = -margin, height + margin
        for nid in node_ids:
            ddx, ddy = disp[nid]
            d = math.hypot(ddx, ddy) or 0.01
            step_x = (ddx / d) * min(d, temperature)
            step_y = (ddy / d) * min(d, temperature)
            nx = positions[nid][0] + step_x
            ny = positions[nid][1] + step_y
            if nx < x_lo: nx = x_lo
            elif nx > x_hi: nx = x_hi
            if ny < y_lo: ny = y_lo
            elif ny > y_hi: ny = y_hi
            positions[nid][0] = nx
            positions[nid][1] = ny

        temperature = max(0.0, temperature - cool)

    # Freeze and compute bounding box.
    frozen: dict[str, tuple[float, float]] = {
        nid: (float(positions[nid][0]), float(positions[nid][1]))
        for nid in node_ids
    }
    xs = [p[0] for p in frozen.values()]
    ys = [p[1] for p in frozen.values()]
    bbox = (min(xs), min(ys), max(xs), max(ys))

    return LayoutResult(
        positions=frozen,
        layers=dict(node_layer),
        layer_anchors=dict(layer_anchors),
        layer_colors={layer: LAYER_COLORS.get(layer, LAYER_COLORS["Other"]) for layer in layer_names},
        bounding_box=bbox,
        params={
            "iterations": iters,
            "seed": int(seed),
            "width": float(width),
            "height": float(height),
            "k": float(k),
            "layer_count": layer_count,
        },
        node_count=n,
        edge_count=edge_count_used,
    )


def compute_layout_from_state(
    state_dir: Path | str = ".sifta_state",
    *,
    width: float = 1600.0,
    height: float = 1200.0,
    iterations: int = 120,
    seed: int = 70,
    layers: Sequence[str] = DEFAULT_LAYERS,
    max_nodes: int = 5000,
    max_edges: int = 10000,
) -> LayoutResult:
    """Load latest nodes/edges from the Round 70 ledgers, then lay them out."""
    nodes = graph.load_recent_nodes(state_dir, max_n=max_nodes)
    edges = graph.load_recent_edges(state_dir, max_n=max_edges)
    return compute_layout(
        nodes,
        edges,
        width=width,
        height=height,
        iterations=iterations,
        seed=seed,
        layers=layers,
    )


def layout_summary_block(result: LayoutResult) -> str:
    """Small prompt block describing the current layout."""
    if result.node_count == 0:
        return "CODE GRAPH LAYOUT: no nodes positioned (ledgers empty)."
    layer_counts: dict[str, int] = {}
    for layer in result.layers.values():
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
    parts = ", ".join(f"{name}={count}" for name, count in sorted(layer_counts.items()))
    return (
        f"CODE GRAPH LAYOUT: {result.node_count} nodes, "
        f"{result.edge_count} edges; layers: {parts}. "
        "Positions are deterministic for the same ledger contents — "
        "the viewer just renders them."
    )


__all__ = [
    "DEFAULT_LAYERS",
    "LAYER_COLORS",
    "LayoutResult",
    "compute_layout",
    "compute_layout_from_state",
    "layer_of",
    "layout_summary_block",
]
