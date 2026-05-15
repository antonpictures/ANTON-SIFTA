from __future__ import annotations

import json
import math

import pytest

from System.swarm_traveling_salesman_swimmers import (
    City,
    TspSwimmerConfig,
    distance_matrix,
    exact_tsp_bruteforce,
    nearest_neighbor_tour,
    solve_tsp_stigmergic,
    tour_distance,
)


def _square():
    return [
        City("A", 0.0, 0.0),
        City("B", 1.0, 0.0),
        City("C", 1.0, 1.0),
        City("D", 0.0, 1.0),
    ]


def test_square_is_exact_verified_and_receipted(tmp_path):
    result = solve_tsp_stigmergic(
        _square(),
        TspSwimmerConfig(n_swimmers=24, iterations=20, seed=7),
        state_dir=tmp_path,
    )

    assert result.truth_label == "TSP_SWIMMER_EXACT_VERIFIED_SMALL_N"
    assert result.best_distance == pytest.approx(4.0)
    assert result.exact_distance == pytest.approx(4.0)
    assert set(result.best_city_route) == {"A", "B", "C", "D"}
    assert result.receipt_path is not None
    assert result.receipt_hash is not None

    rows = (tmp_path / "tsp_swimmer_receipts.jsonl").read_text(encoding="utf-8").splitlines()
    row = json.loads(rows[-1])
    assert row["action"] == "TSP_STIGMERGIC_SWIMMER_SOLVE"
    assert row["truth_label"] == result.truth_label
    assert row["receipt_hash"] == result.receipt_hash


def test_swimmer_result_matches_or_improves_baseline(tmp_path):
    cities = [
        City("depot", 0.0, 0.0),
        City("north", 0.4, 4.2),
        City("east", 5.5, 1.0),
        City("south", 1.5, -3.0),
        City("west", -3.5, 0.8),
        City("hub", 2.4, 2.1),
        City("dock", -1.0, -2.5),
    ]

    baseline_route, baseline_distance = nearest_neighbor_tour(cities)
    result = solve_tsp_stigmergic(
        cities,
        TspSwimmerConfig(n_swimmers=80, iterations=60, seed=91),
        state_dir=tmp_path,
    )

    assert set(result.best_route) == set(range(len(cities)))
    assert result.baseline_distance <= baseline_distance + 1e-9
    assert result.best_distance <= result.baseline_distance + 1e-9
    assert result.improvement_vs_baseline >= 0.0
    assert len(result.best_by_iteration) == 60
    assert result.best_by_iteration[-1] <= result.best_by_iteration[0] + 1e-9
    assert tour_distance(baseline_route, distance_matrix(cities)) == pytest.approx(baseline_distance)


def test_seed_is_deterministic_without_receipts():
    cities = [
        City("A", 0.0, 0.0),
        City("B", 2.0, 1.0),
        City("C", 4.0, 0.0),
        City("D", 3.0, 3.0),
        City("E", 0.5, 2.5),
    ]
    cfg = TspSwimmerConfig(n_swimmers=32, iterations=25, seed=123)

    a = solve_tsp_stigmergic(cities, cfg, write_receipt=False)
    b = solve_tsp_stigmergic(cities, cfg, write_receipt=False)

    assert a.best_route == b.best_route
    assert a.best_distance == pytest.approx(b.best_distance)
    assert a.best_by_iteration == b.best_by_iteration


def test_exact_bruteforce_checks_known_rectangle():
    cities = [
        City("A", 0.0, 0.0),
        City("B", 3.0, 0.0),
        City("C", 3.0, 2.0),
        City("D", 0.0, 2.0),
    ]

    route, length = exact_tsp_bruteforce(cities)

    assert set(route) == {0, 1, 2, 3}
    assert length == pytest.approx(10.0)


def test_rejects_bad_city_sets():
    with pytest.raises(ValueError, match="at least three"):
        solve_tsp_stigmergic([City("A", 0, 0), City("B", 1, 1)], write_receipt=False)

    with pytest.raises(ValueError, match="duplicate"):
        solve_tsp_stigmergic(
            [City("A", 0, 0), City("A", 1, 1), City("C", 2, 2)],
            write_receipt=False,
        )

    with pytest.raises(ValueError, match="non-finite"):
        solve_tsp_stigmergic(
            [City("A", 0, 0), City("B", math.inf, 1), City("C", 2, 2)],
            write_receipt=False,
        )


def test_pheromone_matrix_stays_symmetric(tmp_path):
    result = solve_tsp_stigmergic(
        _square(),
        TspSwimmerConfig(n_swimmers=16, iterations=10, seed=4),
        state_dir=tmp_path,
    )

    matrix = result.pheromone
    assert len(matrix) == 4
    for i in range(4):
        assert matrix[i][i] == pytest.approx(0.0)
        for j in range(4):
            assert matrix[i][j] == pytest.approx(matrix[j][i])
