#!/usr/bin/env python3
"""Stigmergic swimmer solver for the Traveling Salesman Problem.

This is a functional ant-colony-style optimizer:
- route swimmers construct tours from pheromone + inverse-distance gradients
- shorter tours deposit stronger pheromone on their edges
- stale paths evaporate
- a deterministic 2-opt pass removes obvious crossings
- small instances can be exact-verified by brute force for truth receipts

Truth boundary: TSP is NP-hard. For larger instances this module returns a
receipted heuristic result, not a global-optimum proof.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_DEFAULT_RECEIPT = _STATE / "tsp_swimmer_receipts.jsonl"


@dataclass(frozen=True)
class City:
    name: str
    x: float
    y: float

    def as_receipt(self) -> dict[str, float | str]:
        return {"name": self.name, "x": self.x, "y": self.y}


@dataclass(frozen=True)
class TspSwimmerConfig:
    n_swimmers: int = 64
    iterations: int = 80
    alpha: float = 1.0
    beta: float = 3.0
    evaporation: float = 0.28
    deposit: float = 1.0
    elite_deposit: float = 2.0
    seed: int = 1337
    exact_verify_limit: int = 9
    two_opt: bool = True


@dataclass
class TspSwarmResult:
    best_route: list[int]
    best_distance: float
    baseline_route: list[int]
    baseline_distance: float
    iterations: int
    n_swimmers: int
    city_names: list[str]
    best_by_iteration: list[float] = field(default_factory=list)
    exact_route: list[int] | None = None
    exact_distance: float | None = None
    receipt_path: str | None = None
    receipt_hash: str | None = None
    pheromone: list[list[float]] = field(default_factory=list)

    @property
    def best_city_route(self) -> list[str]:
        return [self.city_names[i] for i in self.best_route]

    @property
    def baseline_city_route(self) -> list[str]:
        return [self.city_names[i] for i in self.baseline_route]

    @property
    def exact_city_route(self) -> list[str] | None:
        if self.exact_route is None:
            return None
        return [self.city_names[i] for i in self.exact_route]

    @property
    def improvement_vs_baseline(self) -> float:
        if self.baseline_distance <= 0:
            return 0.0
        return max(0.0, (self.baseline_distance - self.best_distance) / self.baseline_distance)

    @property
    def exact_gap(self) -> float | None:
        if self.exact_distance is None or self.exact_distance <= 0:
            return None
        return max(0.0, (self.best_distance - self.exact_distance) / self.exact_distance)

    @property
    def truth_label(self) -> str:
        if self.exact_distance is None:
            return "TSP_SWIMMER_HEURISTIC_NO_EXACT_PROOF"
        if math.isclose(self.best_distance, self.exact_distance, rel_tol=1e-9, abs_tol=1e-9):
            return "TSP_SWIMMER_EXACT_VERIFIED_SMALL_N"
        return "TSP_SWIMMER_HEURISTIC_WITH_EXACT_GAP"

    def to_dict(self) -> dict:
        return {
            "truth_label": self.truth_label,
            "best_route": self.best_city_route,
            "best_route_indices": self.best_route,
            "best_distance": self.best_distance,
            "baseline_route": self.baseline_city_route,
            "baseline_distance": self.baseline_distance,
            "improvement_vs_baseline": self.improvement_vs_baseline,
            "exact_route": self.exact_city_route,
            "exact_distance": self.exact_distance,
            "exact_gap": self.exact_gap,
            "iterations": self.iterations,
            "n_swimmers": self.n_swimmers,
            "best_by_iteration": self.best_by_iteration,
            "receipt_path": self.receipt_path,
            "receipt_hash": self.receipt_hash,
        }


def validate_cities(cities: Sequence[City]) -> list[City]:
    clean = list(cities)
    if len(clean) < 3:
        raise ValueError("TSP requires at least three cities")
    names: set[str] = set()
    for city in clean:
        if not city.name or not str(city.name).strip():
            raise ValueError("city names must be non-empty")
        if city.name in names:
            raise ValueError(f"duplicate city name: {city.name}")
        names.add(city.name)
        if not math.isfinite(city.x) or not math.isfinite(city.y):
            raise ValueError(f"city {city.name} has non-finite coordinates")
    return clean


def distance_matrix(cities: Sequence[City]) -> list[list[float]]:
    clean = validate_cities(cities)
    matrix: list[list[float]] = []
    for a in clean:
        row: list[float] = []
        for b in clean:
            d = math.hypot(a.x - b.x, a.y - b.y)
            row.append(max(d, 1e-12))
        matrix.append(row)
    return matrix


def tour_distance(route: Sequence[int], dist: Sequence[Sequence[float]]) -> float:
    if len(route) != len(set(route)):
        raise ValueError("route contains duplicate city indices")
    if not route:
        raise ValueError("route is empty")
    total = 0.0
    n = len(route)
    for pos, city in enumerate(route):
        total += dist[city][route[(pos + 1) % n]]
    return total


def _edge_pairs(route: Sequence[int]) -> Iterable[tuple[int, int]]:
    n = len(route)
    for pos, a in enumerate(route):
        b = route[(pos + 1) % n]
        yield (a, b)


def _nearest_neighbor_from(start: int, dist: Sequence[Sequence[float]]) -> list[int]:
    n = len(dist)
    route = [start]
    unvisited = set(range(n))
    unvisited.remove(start)
    while unvisited:
        current = route[-1]
        nxt = min(unvisited, key=lambda idx: (dist[current][idx], idx))
        route.append(nxt)
        unvisited.remove(nxt)
    return route


def nearest_neighbor_tour(cities: Sequence[City]) -> tuple[list[int], float]:
    dist = distance_matrix(cities)
    best_route: list[int] | None = None
    best_length = float("inf")
    for start in range(len(dist)):
        route = _nearest_neighbor_from(start, dist)
        length = tour_distance(route, dist)
        if length < best_length:
            best_route = route
            best_length = length
    assert best_route is not None
    return best_route, best_length


def exact_tsp_bruteforce(cities: Sequence[City]) -> tuple[list[int], float]:
    dist = distance_matrix(cities)
    n = len(dist)
    best_route: list[int] | None = None
    best_length = float("inf")
    # Fix city 0 to remove rotational duplicates.
    for rest in itertools.permutations(range(1, n)):
        route = [0, *rest]
        length = tour_distance(route, dist)
        if length < best_length:
            best_route = list(route)
            best_length = length
    assert best_route is not None
    return best_route, best_length


def _two_opt(route: list[int], dist: Sequence[Sequence[float]]) -> list[int]:
    best = list(route)
    best_length = tour_distance(best, dist)
    improved = True
    while improved:
        improved = False
        for i in range(1, len(best) - 2):
            for j in range(i + 1, len(best)):
                if j - i == 1:
                    continue
                candidate = best[:i] + best[i:j][::-1] + best[j:]
                length = tour_distance(candidate, dist)
                if length + 1e-12 < best_length:
                    best = candidate
                    best_length = length
                    improved = True
        route = best
    return best


def _weighted_choice(weights: list[tuple[int, float]], rng: random.Random) -> int:
    total = sum(max(0.0, w) for _, w in weights)
    if total <= 0:
        return rng.choice([idx for idx, _ in weights])
    mark = rng.random() * total
    acc = 0.0
    for idx, weight in weights:
        acc += max(0.0, weight)
        if acc >= mark:
            return idx
    return weights[-1][0]


def _construct_swimmer_tour(
    *,
    start: int,
    dist: Sequence[Sequence[float]],
    pheromone: Sequence[Sequence[float]],
    cfg: TspSwimmerConfig,
    rng: random.Random,
) -> list[int]:
    n = len(dist)
    route = [start]
    unvisited = set(range(n))
    unvisited.remove(start)
    while unvisited:
        current = route[-1]
        weights: list[tuple[int, float]] = []
        for city in sorted(unvisited):
            p = max(1e-12, pheromone[current][city]) ** cfg.alpha
            h = (1.0 / dist[current][city]) ** cfg.beta
            weights.append((city, p * h))
        nxt = _weighted_choice(weights, rng)
        route.append(nxt)
        unvisited.remove(nxt)
    return route


def _cities_hash(cities: Sequence[City]) -> str:
    payload = json.dumps([c.as_receipt() for c in cities], sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_receipt(path: Path, row: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    stable = {k: v for k, v in row.items() if k != "receipt_hash"}
    receipt_hash = hashlib.sha256(json.dumps(stable, sort_keys=True).encode("utf-8")).hexdigest()
    row["receipt_hash"] = receipt_hash
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return receipt_hash


def solve_tsp_stigmergic(
    cities: Sequence[City],
    config: TspSwimmerConfig | None = None,
    *,
    state_dir: Path | None = None,
    write_receipt: bool = True,
) -> TspSwarmResult:
    """Solve a TSP instance with route swimmers and pheromone reinforcement."""
    cfg = config or TspSwimmerConfig()
    if cfg.n_swimmers <= 0:
        raise ValueError("n_swimmers must be positive")
    if cfg.iterations <= 0:
        raise ValueError("iterations must be positive")
    if not 0.0 <= cfg.evaporation < 1.0:
        raise ValueError("evaporation must be in [0, 1)")

    clean = validate_cities(cities)
    dist = distance_matrix(clean)
    n = len(clean)
    rng = random.Random(cfg.seed)

    baseline_route, baseline_distance = nearest_neighbor_tour(clean)
    if cfg.two_opt:
        baseline_route = _two_opt(baseline_route, dist)
        baseline_distance = tour_distance(baseline_route, dist)

    best_route = list(baseline_route)
    best_distance = baseline_distance
    best_by_iteration: list[float] = []
    pheromone = [[1.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        pheromone[i][i] = 0.0

    for iteration in range(cfg.iterations):
        tours: list[tuple[float, list[int]]] = []
        for swimmer_id in range(cfg.n_swimmers):
            start = (swimmer_id + iteration) % n
            route = _construct_swimmer_tour(
                start=start,
                dist=dist,
                pheromone=pheromone,
                cfg=cfg,
                rng=rng,
            )
            if cfg.two_opt:
                route = _two_opt(route, dist)
            length = tour_distance(route, dist)
            tours.append((length, route))
            if length + 1e-12 < best_distance:
                best_distance = length
                best_route = list(route)

        retain = 1.0 - cfg.evaporation
        for i in range(n):
            for j in range(n):
                pheromone[i][j] *= retain

        for length, route in tours:
            amount = cfg.deposit / max(length, 1e-12)
            for a, b in _edge_pairs(route):
                pheromone[a][b] += amount
                pheromone[b][a] += amount

        elite_amount = cfg.elite_deposit / max(best_distance, 1e-12)
        for a, b in _edge_pairs(best_route):
            pheromone[a][b] += elite_amount
            pheromone[b][a] += elite_amount

        best_by_iteration.append(best_distance)

    exact_route: list[int] | None = None
    exact_distance: float | None = None
    if n <= cfg.exact_verify_limit:
        exact_route, exact_distance = exact_tsp_bruteforce(clean)

    result = TspSwarmResult(
        best_route=best_route,
        best_distance=best_distance,
        baseline_route=baseline_route,
        baseline_distance=baseline_distance,
        iterations=cfg.iterations,
        n_swimmers=cfg.n_swimmers,
        city_names=[c.name for c in clean],
        best_by_iteration=best_by_iteration,
        exact_route=exact_route,
        exact_distance=exact_distance,
        pheromone=pheromone,
    )

    if write_receipt:
        receipt_path = (state_dir or _STATE) / "tsp_swimmer_receipts.jsonl"
        result.receipt_path = str(receipt_path)
        row = {
            "ts": time.time(),
            "action": "TSP_STIGMERGIC_SWIMMER_SOLVE",
            "truth_label": result.truth_label,
            "cities_hash": _cities_hash(clean),
            "cities": [c.as_receipt() for c in clean],
            "config": cfg.__dict__,
            "result": result.to_dict(),
        }
        result.receipt_hash = _write_receipt(receipt_path, row)
    return result


def demo_cities() -> list[City]:
    return [
        City("depot", 0.0, 0.0),
        City("library", 1.0, 4.0),
        City("lab", 4.0, 3.5),
        City("market", 6.0, 1.0),
        City("clinic", 3.0, -1.0),
        City("warehouse", -1.5, 2.0),
    ]


if __name__ == "__main__":
    result = solve_tsp_stigmergic(demo_cities())
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
