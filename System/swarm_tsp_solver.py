#!/usr/bin/env python3
"""swarm_tsp_solver.py — three-backend TSP router.

Truth label: ``SIFTA_TSP_DEMO_V1``.

Separated from :mod:`Applications.sifta_tsp_widget` so the solver can
run without PyQt6 (tests, headless scripts, CI). The widget imports
from this module.

Three backends, picked at runtime by the architect-doctrine policy:

  1. **Stigmergic swimmer organ** (``System/swarm_traveling_salesman_swimmers``
     — shipped by Codex peer doctor). Ant-colony optimization with
     pheromone, elite deposit, 2-opt cleanup, and brute-force
     verification for small N. **Default for 3 ≤ N ≤ 30** — this is
     SIFTA's own organ, and it carries truth labels that distinguish
     EXACT_VERIFIED from HEURISTIC.
  2. **Google OR-Tools** constraint solver with guided local search.
     Used for N > 30 when available — handles larger instances faster
     than the swimmer iteration loop.
  3. **Nearest-neighbour + 2-opt** — pure-Python fallback. Always
     available.

Every receipt names the solver and the input SHA so Alice's route
output is auditable. Alice never claims she computed the tour herself.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from typing import List, Optional, Sequence, Tuple


TRUTH_LABEL = "SIFTA_TSP_DEMO_V1"

# Sweet spot for the stigmergic swimmer organ: enough room for the
# pheromone field to converge, small enough that 80*64 iterations
# stay under a second on commodity silicon.
STIGMERGIC_MIN_N = 3
STIGMERGIC_MAX_N = 30


def _try_stigmergic_swimmer_solver(
    coords: Sequence[Tuple[float, float]],
) -> Optional[Tuple[List[int], float, str, Optional[float], Optional[float]]]:
    """Try the SIFTA stigmergic swimmer organ.

    Returns ``(tour, total_distance, solver_name, exact_distance,
    exact_gap)`` or ``None`` if the organ is unavailable or the input
    is outside its honest range.

    The two extra return values let the receipt expose Codex's
    exact-verified truth label when small-N brute force confirms the
    swimmer's tour.
    """
    n = len(coords)
    if not (STIGMERGIC_MIN_N <= n <= STIGMERGIC_MAX_N):
        return None
    try:
        from System.swarm_traveling_salesman_swimmers import (  # type: ignore
            City,
            TspSwimmerConfig,
            solve_tsp_stigmergic,
        )
    except Exception:
        return None
    try:
        cities = [
            City(name=f"c{i:02d}", x=float(c[0]), y=float(c[1]))
            for i, c in enumerate(coords)
        ]
        cfg = TspSwimmerConfig(
            n_swimmers=max(16, min(64, n * 4)),
            iterations=max(20, min(80, n * 3)),
            seed=1337,
            exact_verify_limit=9,
        )
        result = solve_tsp_stigmergic(cities, cfg, write_receipt=False)
    except Exception:
        return None
    # Close the loop on the route the way the rest of swarm_tsp_solver
    # returns it: closed cycle of indices ending at the starting city.
    tour = list(result.best_route)
    if tour and tour[-1] != tour[0]:
        tour.append(tour[0])
    return (
        tour,
        float(result.best_distance),
        "stigmergic_swimmers",
        float(result.exact_distance) if result.exact_distance is not None else None,
        float(result.exact_gap) if result.exact_gap is not None else None,
    )


def _try_ortools_solver(
    coords: Sequence[Tuple[float, float]], *, time_limit_s: float = 1.0
) -> Optional[Tuple[List[int], float, str]]:
    """Try OR-Tools. Returns ``(tour, total_distance, solver_name)`` or None."""
    try:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2  # type: ignore
    except Exception:
        return None
    n = len(coords)
    if n < 2:
        return None
    SCALE = 1000
    dist = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dx = coords[i][0] - coords[j][0]
            dy = coords[i][1] - coords[j][1]
            dist[i][j] = int(round(math.sqrt(dx * dx + dy * dy) * SCALE))
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def cb(from_index: int, to_index: int) -> int:
        a = manager.IndexToNode(from_index)
        b = manager.IndexToNode(to_index)
        return dist[a][b]

    transit_id = routing.RegisterTransitCallback(cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_id)
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = max(1, int(time_limit_s))
    solution = routing.SolveWithParameters(params)
    if not solution:
        return None
    idx = routing.Start(0)
    tour: List[int] = []
    total = 0
    while not routing.IsEnd(idx):
        tour.append(manager.IndexToNode(idx))
        nxt = solution.Value(routing.NextVar(idx))
        total += dist[manager.IndexToNode(idx)][manager.IndexToNode(nxt)]
        idx = nxt
    tour.append(manager.IndexToNode(idx))
    return tour, total / SCALE, "or_tools_guided_local_search"


def nearest_neighbour_plus_two_opt(
    coords: Sequence[Tuple[float, float]]
) -> Tuple[List[int], float, str]:
    """Deterministic heuristic. Always available."""
    n = len(coords)

    def d(i: int, j: int) -> float:
        dx = coords[i][0] - coords[j][0]
        dy = coords[i][1] - coords[j][1]
        return math.sqrt(dx * dx + dy * dy)

    if n == 0:
        return [], 0.0, "trivial"
    if n == 1:
        return [0, 0], 0.0, "trivial"

    unvisited = set(range(1, n))
    tour: List[int] = [0]
    while unvisited:
        last = tour[-1]
        nxt = min(unvisited, key=lambda j: d(last, j))
        tour.append(nxt)
        unvisited.remove(nxt)
    tour.append(0)

    def tour_distance(t: List[int]) -> float:
        return sum(d(t[i], t[i + 1]) for i in range(len(t) - 1))

    improved = True
    passes = 0
    while improved and passes < 50:
        improved = False
        passes += 1
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                if j - i == 1:
                    continue
                new_tour = tour[:i] + tour[i:j + 1][::-1] + tour[j + 1:]
                if tour_distance(new_tour) + 1e-9 < tour_distance(tour):
                    tour = new_tour
                    improved = True
        if n > 200:
            break
    return tour, tour_distance(tour), "nearest_neighbour_plus_two_opt"


def solve_tsp(
    coords: Sequence[Tuple[float, float]],
    *,
    time_limit_s: float = 1.0,
    instance_name: Optional[str] = None,
) -> dict:
    """Return a route + receipt for the given coordinate list.

    The receipt names the solver, the input hash, and the total tour
    distance. Alice never claims to have solved it herself.
    """
    coord_list: List[Tuple[float, float]] = [tuple(map(float, c)) for c in coords]
    if not coord_list:
        out_empty: dict = {
            "truth_label": TRUTH_LABEL,
            "trace_id": str(uuid.uuid4()),
            "ts": time.time(),
            "solver": "none",
            "tour": [],
            "total_distance": 0.0,
            "n": 0,
            "note": "no input coords",
            "input_sha12": "",
            "input_coords": [],
            "truth_note": "no input — nothing to route.",
        }
        if instance_name:
            out_empty["instance_name"] = instance_name
        return out_empty
    n = len(coord_list)
    exact_distance: Optional[float] = None
    exact_gap: Optional[float] = None

    # 1) Try the SIFTA stigmergic swimmer organ first (Codex peer
    #    shipped at System/swarm_traveling_salesman_swimmers.py).
    #    This is SIFTA's own organ — the unified-field doctrine.
    swarm_result = _try_stigmergic_swimmer_solver(coord_list)
    if swarm_result is not None:
        tour, total, solver_name, exact_distance, exact_gap = swarm_result
    else:
        # 2) Larger instances or organ unavailable → OR-Tools.
        ortools_result = _try_ortools_solver(coord_list, time_limit_s=time_limit_s)
        if ortools_result is not None:
            tour, total, solver_name = ortools_result
        else:
            # 3) Pure-Python fallback. Always available.
            tour, total, solver_name = nearest_neighbour_plus_two_opt(coord_list)
    coord_text = json.dumps(coord_list, sort_keys=True)
    sha = hashlib.sha256(coord_text.encode("utf-8")).hexdigest()[:12]
    out: dict = {
        "truth_label": TRUTH_LABEL,
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "solver": solver_name,
        "exact_distance": exact_distance,
        "exact_gap": exact_gap,
        "tour": tour,
        "total_distance": round(total, 4),
        "n": len(coord_list),
        "input_sha12": sha,
        "input_coords": coord_list,
        "truth_note": (
            "Alice did not compute this route herself. She routed the "
            f"problem to {solver_name} and returned its output. The "
            "input coords are SHA-stable; the tour is reproducible."
        ),
    }
    if instance_name:
        out["instance_name"] = instance_name
    return out
