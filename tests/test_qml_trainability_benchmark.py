#!/usr/bin/env python3
"""Tests for the QML trainability benchmark — verify the HARNESS is correct,
not that any particular strategy wins. (As of r480 the stigmergic optimizer
loses to coordinate descent on this toy task; the test must not assume a winner.)
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from System.swarm_qml_sifta_nuggets import run_trainability_benchmark, _tfim_2q_hamiltonian


def test_exact_ground_energy_is_minus_sqrt5():
    e0 = float(np.linalg.eigvalsh(_tfim_2q_hamiltonian())[0])
    assert abs(e0 - (-math.sqrt(5.0))) < 1e-6, e0


def test_benchmark_structure_and_variational_bound():
    r = run_trainability_benchmark(budget=150, seeds=5, write_receipt=False)
    assert set(r["results"]) == {"random", "coordinate_descent", "spsa", "stigmergic_aco"}
    for g in r["results"].values():
        assert np.isfinite(g["mean_gap"])
        assert g["best_gap"] >= -1e-6  # variational principle: E(theta) >= E0 always
    # the harness must actually optimize: at least one strategy gets near the ground state
    assert min(v["mean_gap"] for v in r["results"].values()) < 0.05, r["results"]
    assert r["verdict"] in {
        "stigmergic_won_toy_equal_budget",
        "stigmergic_beat_random_not_all_baselines",
        "stigmergic_did_not_beat_baselines",
    }


def test_deterministic():
    a = run_trainability_benchmark(budget=120, seeds=4, write_receipt=False)
    b = run_trainability_benchmark(budget=120, seeds=4, write_receipt=False)
    assert a["results"] == b["results"]


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
