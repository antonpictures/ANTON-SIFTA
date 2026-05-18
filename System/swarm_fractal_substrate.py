#!/usr/bin/env python3
"""System/swarm_fractal_substrate.py — fractal geometries swimmers can walk.

Architect 2026-05-17 (verbatim, abridged):
    "What about fractals? If we send swimmers on fractals? What is
    emerging? Interesting?"

This module exposes fractal substrates as graphs that SIFTA swimmers
can traverse. The first cut covers the **Sierpinski gasket** because:

  * Its walk dimension is a closed-form number — d_w = log(5)/log(2)
    ≈ 2.3219 (Goldstein 1982; Hattori et al. 1990). That gives us a
    falsification test for the very first run.
  * The graph is small enough to fit in memory at depth 6–8 (43–732
    sites at depth 4, 366 at depth 5, …) while still being a real
    fractal with non-trivial Hausdorff dimension d_f = log(3)/log(2)
    ≈ 1.5849.
  * The visual is striking — a perfect demo for the Architect / Kole.

Each substrate exposes a small, uniform interface so the walker organ
doesn't care which fractal it's on:

    substrate.sites()         -> Iterable[site_id]
    substrate.neighbors(site) -> List[site_id]
    substrate.coords(site)    -> (x, y) in [0, 1]^2 for rendering
    substrate.is_void(site)   -> bool  (kept as a hook for substrates
                                        where coordinates exist but the
                                        site is part of the cut-out region)
    substrate.scale(site)     -> int (recursion depth where this site
                                        first appears — useful for
                                        multi-scale pheromone analysis)
    substrate.fractal_dim     -> float  Hausdorff dimension
    substrate.walk_dim        -> float  expected walk dimension
                                        (closed-form when known)

Truth label: ``SIFTA_FRACTAL_SUBSTRATE_V0``.

Stigauth: ``COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE``.

Honesty boundary
================
This is a CLASSICAL discrete-graph substrate for stigmergic agents.
It is not a quantum simulation. The fractal connectivity gives rise
to anomalous diffusion that LOOKS analogous to localization phenomena
on fractal quantum substrates, but the swarm here transports classical
pheromones, not qubit amplitudes. See
``Documents/SIFTA_FRACTAL_STIGMERGY_HYPOTHESIS_V0.md`` (when written)
for the full hypothesis / non-claims.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple

_TRUTH_LABEL = "SIFTA_FRACTAL_SUBSTRATE_V0"


class SierpinskiGasket:
    """The Sierpinski gasket as a discrete graph at recursion depth ``n``.

    Construction: start with the 3 vertices of an equilateral triangle.
    At each level, every solid sub-triangle is replaced by three smaller
    sub-triangles, each scaled by 1/2. The vertices of all surviving
    sub-triangles form the graph; two vertices are neighbours iff they
    are connected by an edge of any surviving sub-triangle.

    At depth n the graph has (3^(n+1) + 3)/2 vertices.  Some sites
    appear at multiple recursion levels (corner vertices of larger
    sub-triangles); ``scale(site)`` returns the SHALLOWEST level at
    which the site first exists, so a multi-scale pheromone analysis
    can weight contributions per generation.

    Walk dimension d_w = log(5)/log(2) ≈ 2.32193 (classical result).
    Hausdorff dimension d_f = log(3)/log(2) ≈ 1.58496.
    """

    # Known closed-form constants for this geometry.
    fractal_dim: float = math.log(3) / math.log(2)
    walk_dim: float = math.log(5) / math.log(2)

    def __init__(self, depth: int = 5) -> None:
        if depth < 1 or depth > 8:
            raise ValueError("depth must be in [1, 8] for practical memory")
        self._depth = int(depth)
        # site -> (x, y), with site_id = a stable rounded-tuple key.
        self._coords: Dict[Tuple[int, int], Tuple[float, float]] = {}
        # site -> set of neighbour site_ids
        self._adj: Dict[Tuple[int, int], set] = {}
        # site -> shallowest recursion level at which the site appears
        self._scale: Dict[Tuple[int, int], int] = {}
        self._build()

    # ── construction ─────────────────────────────────────────────────
    def _key(self, x: float, y: float) -> Tuple[int, int]:
        # Quantize to avoid floating-point drift at deep recursion.
        # 2**12 grid points span [0, 1] cleanly at depth ≤ 12.
        q = 1 << 14
        return (int(round(x * q)), int(round(y * q)))

    def _coord_of(self, key: Tuple[int, int]) -> Tuple[float, float]:
        q = float(1 << 14)
        return (key[0] / q, key[1] / q)

    def _add_edge(self, a: Tuple[int, int], b: Tuple[int, int]) -> None:
        self._adj.setdefault(a, set()).add(b)
        self._adj.setdefault(b, set()).add(a)

    def _add_triangle(
        self,
        vs: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]],
        depth: int,
    ) -> None:
        # Quantized keys
        ka = self._key(*vs[0])
        kb = self._key(*vs[1])
        kc = self._key(*vs[2])
        for key, xy in ((ka, vs[0]), (kb, vs[1]), (kc, vs[2])):
            if key not in self._coords:
                self._coords[key] = xy
                self._scale[key] = depth
            else:
                # Shallowest recursion wins for the scale tag.
                if depth < self._scale[key]:
                    self._scale[key] = depth
        if depth == self._depth:
            # leaf triangle — add its three edges
            self._add_edge(ka, kb)
            self._add_edge(kb, kc)
            self._add_edge(kc, ka)
            return
        # Recurse into the three sub-triangles formed by midpoints.
        m_ab = ((vs[0][0] + vs[1][0]) / 2, (vs[0][1] + vs[1][1]) / 2)
        m_bc = ((vs[1][0] + vs[2][0]) / 2, (vs[1][1] + vs[2][1]) / 2)
        m_ca = ((vs[2][0] + vs[0][0]) / 2, (vs[2][1] + vs[0][1]) / 2)
        self._add_triangle((vs[0], m_ab, m_ca), depth + 1)
        self._add_triangle((m_ab, vs[1], m_bc), depth + 1)
        self._add_triangle((m_ca, m_bc, vs[2]), depth + 1)

    def _build(self) -> None:
        # Outer triangle: A = (0, 0), B = (1, 0), C = (0.5, sqrt(3)/2)
        a = (0.0, 0.0)
        b = (1.0, 0.0)
        c = (0.5, math.sqrt(3) / 2)
        self._add_triangle((a, b, c), depth=0)

    # ── public API ───────────────────────────────────────────────────
    def sites(self) -> Iterable[Tuple[int, int]]:
        return self._adj.keys()

    def __len__(self) -> int:
        return len(self._adj)

    def neighbors(self, site: Tuple[int, int]) -> List[Tuple[int, int]]:
        return list(self._adj.get(site, ()))

    def coords(self, site: Tuple[int, int]) -> Tuple[float, float]:
        return self._coord_of(site)

    def scale(self, site: Tuple[int, int]) -> int:
        return self._scale.get(site, self._depth)

    def is_void(self, site: Tuple[int, int]) -> bool:
        # All site_ids in self._adj are on the gasket; the void is the
        # complement set of points we never visit. Kept as a hook for
        # substrates where coords exist outside the graph.
        return site not in self._adj

    def corner_sites(self) -> List[Tuple[int, int]]:
        """The three outermost corners — useful as walker spawn points."""
        return [
            self._key(0.0, 0.0),
            self._key(1.0, 0.0),
            self._key(0.5, math.sqrt(3) / 2),
        ]

    @property
    def depth(self) -> int:
        return self._depth


__all__ = ["SierpinskiGasket"]
