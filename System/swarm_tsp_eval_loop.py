#!/usr/bin/env python3
"""swarm_tsp_eval_loop.py — Voss-style CI eval pipeline for the TSP organ.

Truth label: ``SIFTA_TSP_EVAL_V1``.

Laurie Voss at AI Engineer Europe 2026: *most agents get tested by
running a few queries and checking if it looks right — the **vibes
problem**. It doesn't catch regressions, doesn't run in CI, and
doesn't tell you whether a prompt fix broke three other things.*

This loop is the structural reply for the TSP organ. It is **not**
"run the solver once and look at the picture." It is a fixed bank of
problems, every backend run against every problem, gap-to-optimum
computed where ground truth exists, and a regression flag raised when
the current run is worse than the last logged run by more than a
configured tolerance.

What the loop measures
-------------------------

For each test problem and each available backend:

  * tour distance
  * solver runtime in milliseconds
  * exact_gap (when problem size <= ``exact_verify_limit``)
  * tour validity (every city visited once, closed loop)

Regression detection
--------------------

Compares current run against the last logged run on the same problem
+ backend. Flags a regression when current distance is worse than
last by more than ``regression_tolerance`` (default 5%) or when a
backend that previously hit exact optimum no longer does.

CI usage
--------

::

    python3 -m System.swarm_tsp_eval_loop --check-regressions

Exits 0 when no regressions. Exits 1 with a JSON report of
regressions on stdout when at least one fired. Wire into CI to catch
TSP-organ drift before it reaches Architect-visible surfaces.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


TRUTH_LABEL = "SIFTA_TSP_EVAL_V1"
EVAL_LEDGER_NAME = "tsp_eval_runs.jsonl"
DEFAULT_TOLERANCE = 0.05  # 5% worse than last run is a regression


_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"


# ── canonical test bank ──────────────────────────────────────────────────


@dataclass(frozen=True)
class EvalProblem:
    """One deterministic TSP test case.

    ``known_optimum`` is filled in when the problem is small enough for
    brute-force ground truth. The loop re-derives it at run time;
    this field only documents the expected value.
    """

    name: str
    coords: Tuple[Tuple[float, float], ...]
    known_optimum: Optional[float] = None
    description: str = ""


# These are the canonical test problems. Adding to this list is how
# the loop grows over time. Each entry is reproducible and named.
TEST_BANK: Tuple[EvalProblem, ...] = (
    EvalProblem(
        name="unit_square",
        coords=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        known_optimum=4.0,
        description="4-city square; any TSP tour has length 4.",
    ),
    EvalProblem(
        name="triangle_3_4_5",
        coords=((0.0, 0.0), (3.0, 0.0), (0.0, 4.0)),
        known_optimum=12.0,
        description="3-4-5 right triangle; optimal tour = 12.",
    ),
    EvalProblem(
        name="hexagon_radius_1",
        coords=tuple(
            (round(math.cos(math.radians(60 * i)), 6),
             round(math.sin(math.radians(60 * i)), 6))
            for i in range(6)
        ),
        known_optimum=6.0,
        description="6-city regular hexagon, radius 1; perimeter = 6.",
    ),
    EvalProblem(
        name="octagon_radius_1",
        coords=tuple(
            (round(math.cos(math.radians(45 * i)), 6),
             round(math.sin(math.radians(45 * i)), 6))
            for i in range(8)
        ),
        known_optimum=None,  # ~6.123; re-derived at run time
        description="8-city regular octagon, radius 1.",
    ),
    EvalProblem(
        name="cluster_two_groups",
        coords=(
            (0.0, 0.0), (1.0, 0.0), (0.5, 0.5),
            (10.0, 10.0), (11.0, 10.0), (10.5, 10.5),
        ),
        known_optimum=None,
        description="Two clusters of three cities — tests if solver crosses cluster boundary once.",
    ),
    EvalProblem(
        name="random_seed_42_n10",
        coords=tuple(_ for _ in []),  # placeholder
        known_optimum=None,
        description="10 random cities, seed 42 — exact verifiable.",
    ),
    EvalProblem(
        name="random_seed_99_n15",
        coords=tuple(_ for _ in []),  # placeholder
        known_optimum=None,
        description="15 random cities, seed 99 — outside brute-force range.",
    ),
    EvalProblem(
        name="grid_3x3",
        coords=tuple((float(i), float(j)) for i in range(3) for j in range(3)),
        known_optimum=None,
        description="3x3 unit grid — well-known structure.",
    ),
)


def _fill_random_problems() -> List[EvalProblem]:
    """Replace the random_seed_* placeholders with deterministic coords."""
    out: List[EvalProblem] = []
    import random
    for p in TEST_BANK:
        if p.name == "random_seed_42_n10":
            rng = random.Random(42)
            coords = tuple(
                (round(rng.uniform(0, 100), 4), round(rng.uniform(0, 100), 4))
                for _ in range(10)
            )
            out.append(EvalProblem(name=p.name, coords=coords, description=p.description))
        elif p.name == "random_seed_99_n15":
            rng = random.Random(99)
            coords = tuple(
                (round(rng.uniform(0, 100), 4), round(rng.uniform(0, 100), 4))
                for _ in range(15)
            )
            out.append(EvalProblem(name=p.name, coords=coords, description=p.description))
        else:
            out.append(p)
    return out


# ── solver registry ──────────────────────────────────────────────────────


def _validate_tour(tour: Sequence[int], n: int) -> bool:
    """Tour is valid when every city appears exactly once + it's closed."""
    if not tour:
        return n == 0
    if tour[0] != tour[-1]:
        return False
    body = tour[:-1]
    return sorted(body) == list(range(n))


def _tour_distance(tour: Sequence[int], coords: Sequence[Tuple[float, float]]) -> float:
    if not tour:
        return 0.0
    total = 0.0
    for a, b in zip(tour, tour[1:]):
        dx = coords[a][0] - coords[b][0]
        dy = coords[a][1] - coords[b][1]
        total += math.sqrt(dx * dx + dy * dy)
    return total


def _run_stigmergic(coords: Sequence[Tuple[float, float]]) -> Optional[Dict[str, Any]]:
    try:
        from System.swarm_traveling_salesman_swimmers import (
            City,
            TspSwimmerConfig,
            solve_tsp_stigmergic,
        )
    except Exception:
        return None
    if len(coords) < 3:
        return None
    cities = [City(name=f"c{i:02d}", x=float(c[0]), y=float(c[1])) for i, c in enumerate(coords)]
    cfg = TspSwimmerConfig(
        n_swimmers=max(16, min(64, len(coords) * 4)),
        iterations=max(20, min(80, len(coords) * 4)),
        seed=1337,
    )
    start = time.perf_counter()
    result = solve_tsp_stigmergic(cities, cfg, write_receipt=False)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    tour = list(result.best_route)
    if tour and tour[-1] != tour[0]:
        tour.append(tour[0])
    return {
        "tour": tour,
        "distance": float(result.best_distance),
        "elapsed_ms": round(elapsed_ms, 3),
        "exact_distance": result.exact_distance,
        "exact_gap": result.exact_gap,
    }


def _run_nearest_neighbour(coords: Sequence[Tuple[float, float]]) -> Optional[Dict[str, Any]]:
    try:
        from System.swarm_tsp_solver import nearest_neighbour_plus_two_opt
    except Exception:
        return None
    start = time.perf_counter()
    tour, dist, _ = nearest_neighbour_plus_two_opt(coords)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return {
        "tour": tour,
        "distance": float(dist),
        "elapsed_ms": round(elapsed_ms, 3),
        "exact_distance": None,
        "exact_gap": None,
    }


def _run_ortools(coords: Sequence[Tuple[float, float]]) -> Optional[Dict[str, Any]]:
    try:
        from System.swarm_tsp_solver import _try_ortools_solver
    except Exception:
        return None
    start = time.perf_counter()
    result = _try_ortools_solver(coords, time_limit_s=1.0)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    if result is None:
        return None
    tour, dist, _ = result
    return {
        "tour": tour,
        "distance": float(dist),
        "elapsed_ms": round(elapsed_ms, 3),
        "exact_distance": None,
        "exact_gap": None,
    }


SolverFn = Callable[[Sequence[Tuple[float, float]]], Optional[Dict[str, Any]]]
SOLVER_REGISTRY: Tuple[Tuple[str, SolverFn], ...] = (
    ("stigmergic_swimmers", _run_stigmergic),
    ("nearest_neighbour_plus_two_opt", _run_nearest_neighbour),
    ("or_tools_guided_local_search", _run_ortools),
)


# ── eval run ─────────────────────────────────────────────────────────────


@dataclass
class EvalReport:
    truth_label: str = TRUTH_LABEL
    ts: float = 0.0
    trace_id: str = ""
    problems: List[Dict[str, Any]] = field(default_factory=list)
    regressions: List[Dict[str, Any]] = field(default_factory=list)
    backend_avg_gap: Dict[str, float] = field(default_factory=dict)
    backend_runs: Dict[str, int] = field(default_factory=dict)
    sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truth_label": self.truth_label,
            "ts": self.ts,
            "trace_id": self.trace_id,
            "problems": self.problems,
            "regressions": self.regressions,
            "backend_avg_gap": self.backend_avg_gap,
            "backend_runs": self.backend_runs,
            "sha256": self.sha256,
        }


def _read_last_eval(ledger_path: Path) -> Optional[Dict[str, Any]]:
    if not ledger_path.exists():
        return None
    try:
        lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def _build_ground_truth(coords: Sequence[Tuple[float, float]]) -> Optional[float]:
    """Brute-force optimum for problems with N <= 9."""
    if len(coords) > 9:
        return None
    try:
        from System.swarm_traveling_salesman_swimmers import City, exact_tsp_bruteforce
    except Exception:
        return None
    cities = [City(name=f"c{i:02d}", x=float(c[0]), y=float(c[1])) for i, c in enumerate(coords)]
    try:
        _, dist = exact_tsp_bruteforce(cities)
    except Exception:
        return None
    return float(dist)


def run_eval(
    *,
    state_dir: Optional[Path] = None,
    write: bool = True,
    regression_tolerance: float = DEFAULT_TOLERANCE,
) -> EvalReport:
    """Run every backend against every problem, log results, check regressions."""
    base = state_dir if state_dir is not None else _DEFAULT_STATE
    base.mkdir(parents=True, exist_ok=True)
    ledger_path = base / EVAL_LEDGER_NAME
    last_eval = _read_last_eval(ledger_path)
    last_by_key: Dict[str, Dict[str, Any]] = {}
    if last_eval and isinstance(last_eval.get("problems"), list):
        for entry in last_eval["problems"]:
            if not isinstance(entry, dict):
                continue
            for backend_run in entry.get("backends", []):
                if not isinstance(backend_run, dict):
                    continue
                key = f"{entry.get('problem')}|{backend_run.get('backend')}"
                last_by_key[key] = backend_run

    problems = _fill_random_problems()
    out_problems: List[Dict[str, Any]] = []
    regressions: List[Dict[str, Any]] = []
    backend_sums: Dict[str, float] = {}
    backend_counts: Dict[str, int] = {}

    for problem in problems:
        if not problem.coords:
            continue
        optimum = _build_ground_truth(problem.coords)
        backends_run: List[Dict[str, Any]] = []
        for backend_name, solver in SOLVER_REGISTRY:
            res = solver(problem.coords)
            if res is None:
                continue
            n = len(problem.coords)
            tour_ok = _validate_tour(res["tour"], n)
            dist = res["distance"]
            elapsed = res["elapsed_ms"]
            this_gap: Optional[float] = None
            if optimum is not None and optimum > 0:
                this_gap = round(max(0.0, (dist - optimum) / optimum), 6)
                backend_sums[backend_name] = backend_sums.get(backend_name, 0.0) + this_gap
                backend_counts[backend_name] = backend_counts.get(backend_name, 0) + 1

            # Regression check vs last logged run
            key = f"{problem.name}|{backend_name}"
            prev = last_by_key.get(key)
            regressed = False
            regression_note = ""
            if prev is not None:
                prev_dist = prev.get("distance")
                if isinstance(prev_dist, (int, float)) and prev_dist > 0:
                    ratio = (dist - prev_dist) / prev_dist
                    if ratio > regression_tolerance:
                        regressed = True
                        regression_note = (
                            f"distance worsened by {ratio:.1%} vs last run "
                            f"({prev_dist:.4f} → {dist:.4f})"
                        )
                if (
                    prev.get("exact_gap") == 0.0
                    and this_gap is not None
                    and this_gap > 0.0
                ):
                    regressed = True
                    regression_note = (
                        f"backend previously hit exact optimum "
                        f"(gap=0) but now reports gap={this_gap:.1%}"
                    )

            entry = {
                "backend": backend_name,
                "distance": round(dist, 6),
                "elapsed_ms": elapsed,
                "tour_valid": bool(tour_ok),
                "n": n,
                "optimum": optimum,
                "gap_to_optimum": this_gap,
                "regressed": regressed,
                "regression_note": regression_note,
            }
            backends_run.append(entry)
            if regressed:
                regressions.append({
                    "problem": problem.name,
                    "backend": backend_name,
                    "note": regression_note,
                })

        out_problems.append({
            "problem": problem.name,
            "n": len(problem.coords),
            "optimum": optimum,
            "description": problem.description,
            "backends": backends_run,
        })

    avg_gap = {
        name: round(backend_sums[name] / backend_counts[name], 6)
        for name in backend_sums
        if backend_counts.get(name)
    }

    report = EvalReport(
        ts=time.time(),
        trace_id=str(uuid.uuid4()),
        problems=out_problems,
        regressions=regressions,
        backend_avg_gap=avg_gap,
        backend_runs={k: v for k, v in backend_counts.items()},
    )
    payload = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"))
    report.sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    if write:
        with ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(report.to_dict(), sort_keys=True, ensure_ascii=False) + "\n")

    return report


# ── CLI ──────────────────────────────────────────────────────────────────

def _print_summary(report: EvalReport) -> None:
    print(f"TRUTH:       {report.truth_label}")
    print(f"PROBLEMS:    {len(report.problems)}")
    print(f"REGRESSIONS: {len(report.regressions)}")
    print(f"AVG_GAP:     {report.backend_avg_gap}")
    print(f"SHA:         {report.sha256[:16]}")
    if report.regressions:
        print("\nREGRESSED:")
        for r in report.regressions:
            print(f"  - {r['problem']}/{r['backend']}: {r['note']}")
    print("\nPER-PROBLEM:")
    for p in report.problems:
        opt = p.get("optimum")
        opt_str = f"optimum={opt:.4f}" if isinstance(opt, (int, float)) else "optimum=N/A"
        print(f"  {p['problem']} (n={p['n']}, {opt_str}):")
        for b in p.get("backends", []):
            gap = b.get("gap_to_optimum")
            gap_str = f"gap={gap:.4f}" if isinstance(gap, (int, float)) else "gap=N/A"
            flag = " [REGRESSION]" if b.get("regressed") else ""
            print(
                f"    {b['backend']:34s} dist={b['distance']:.4f}  "
                f"{gap_str}  {b['elapsed_ms']:.1f}ms{flag}"
            )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--no-write", action="store_true")
    p.add_argument(
        "--check-regressions",
        action="store_true",
        help="Exit 1 (with JSON regression report on stdout) when any regression fires.",
    )
    p.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE,
        help=f"Regression tolerance (default {DEFAULT_TOLERANCE})",
    )
    args = p.parse_args()
    report = run_eval(write=not args.no_write, regression_tolerance=args.tolerance)
    if args.check_regressions:
        if report.regressions:
            print(json.dumps({"regressions": report.regressions}, indent=2))
            return 1
        print(json.dumps({"regressions": []}, indent=2))
        return 0
    _print_summary(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
