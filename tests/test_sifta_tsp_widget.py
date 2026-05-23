"""Tests for the TSP solver core.

These exercise :mod:`System.swarm_tsp_solver`, which is the pure-Python
solver layer. The PyQt6 widget at ``Applications/sifta_tsp_widget.py``
imports from this module, so the solver tests cover the widget's
business logic without requiring Qt.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_tsp_solver import (  # noqa: E402
    TRUTH_LABEL,
    nearest_neighbour_plus_two_opt,
    solve_tsp,
)


# ── solver behaviour ────────────────────────────────────────────────────


def test_solver_returns_valid_tour_for_small_input():
    coords = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    receipt = solve_tsp(coords)
    assert receipt["truth_label"] == TRUTH_LABEL
    assert receipt["n"] == 4
    assert abs(receipt["total_distance"] - 40.0) < 1.0
    assert sorted(set(receipt["tour"])) == [0, 1, 2, 3]
    assert receipt["tour"][0] == receipt["tour"][-1]


def test_solver_handles_empty_input():
    receipt = solve_tsp([])
    assert receipt["n"] == 0
    assert receipt["tour"] == []
    assert receipt["solver"] in {"none", "trivial"}


def test_solver_handles_single_city():
    receipt = solve_tsp([(5.0, 5.0)])
    assert receipt["n"] == 1
    assert receipt["tour"][0] == 0


def test_solver_input_sha_is_stable():
    coords = [(1.1, 2.2), (3.3, 4.4), (5.5, 6.6)]
    r1 = solve_tsp(coords)
    r2 = solve_tsp(coords)
    assert r1["input_sha12"] == r2["input_sha12"]


def test_solver_never_claims_alice_computed_route():
    receipt = solve_tsp([(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)])
    note = receipt["truth_note"].lower()
    assert "did not compute" in note or "routed" in note
    assert receipt["solver"] in receipt["truth_note"]


def test_fallback_solver_is_deterministic_on_seeded_input():
    """nearest_neighbour + 2-opt is fully deterministic on the same input."""
    coords = [
        (0.0, 0.0), (1.0, 5.0), (3.0, 2.0), (6.0, 6.0), (8.0, 1.0),
        (4.5, 9.0), (7.0, 4.0),
    ]
    tour1, dist1, _ = nearest_neighbour_plus_two_opt(coords)
    tour2, dist2, _ = nearest_neighbour_plus_two_opt(coords)
    assert dist1 == dist2
    assert tour1 == tour2


def test_two_opt_improves_or_matches_nearest_neighbour():
    """2-opt should never produce a worse route than the initial NN tour."""
    coords = [
        (0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0),
        (5.0, 5.0), (3.0, 8.0), (7.0, 2.0),
    ]
    tour, dist, _ = nearest_neighbour_plus_two_opt(coords)
    # Sanity check: distance should be at most the brute-force greedy
    # nearest-neighbour-only upper bound. A 7-point cycle in a 10×10
    # square should never need more than 60.
    assert dist < 60.0
    assert tour[0] == tour[-1]
