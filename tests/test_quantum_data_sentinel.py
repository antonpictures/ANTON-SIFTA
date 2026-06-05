#!/usr/bin/env python3
"""Correctness checks for the quantum sentinel's real local solve.

The transverse-field Ising model has two exactly solvable limits we assert
against, which proves local_tfim_ground_state returns real, correct quantum data
(not a fabricated number). Also smoke-tests the existing catalog/report so the
extension does not break the brother organ.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from System.swarm_quantum_data_sentinel import (
    local_tfim_ground_state,
    quantum_data_sentinel_report,
    suggested_swimmer_experiments,
)


def test_classical_ferromagnet_limit():
    # h = 0  =>  H = -J sum Z_i Z_{i+1}; ground energy = -J*(n-1) (all aligned).
    n, j = 6, 1.0
    p = local_tfim_ground_state(n_spins=n, j_coupling=j, h_field=0.0)
    assert abs(p["ground_state_energy"] - (-(n - 1) * j)) < 1e-6, p["ground_state_energy"]


def test_pure_field_limit():
    # J = 0  =>  H = -h sum X_i; ground state all |+>, energy = -h*n.
    n, h = 6, 1.0
    p = local_tfim_ground_state(n_spins=n, j_coupling=0.0, h_field=h)
    assert abs(p["ground_state_energy"] - (-h * n)) < 1e-6, p["ground_state_energy"]


def test_field_lowers_energy_below_classical():
    n = 6
    p = local_tfim_ground_state(n_spins=n, j_coupling=1.0, h_field=1.0)
    assert p["ground_state_energy"] < -(n - 1) - 1e-9, p["ground_state_energy"]


def test_prior_normalized_hashed_deterministic():
    p = local_tfim_ground_state(n_spins=6, j_coupling=1.0, h_field=1.0)
    dist = np.array(p["ground_state_distribution"])
    assert abs(dist.sum() - 1.0) < 1e-6, dist.sum()
    assert len(dist) == 2 ** 6
    assert len(p["prior_sha256"]) == 64
    p2 = local_tfim_ground_state(n_spins=6, j_coupling=1.0, h_field=1.0)
    assert p["prior_sha256"] == p2["prior_sha256"]


def test_correlation_diagonal_is_one():
    p = local_tfim_ground_state(n_spins=5, j_coupling=1.0, h_field=0.5)
    corr = np.array(p["zz_correlation_matrix"])
    assert corr.shape == (5, 5)
    assert np.allclose(np.diag(corr), 1.0, atol=1e-6), np.diag(corr)


def test_report_and_catalog_still_work():
    # Extension must not break the existing honest catalog/report.
    report = quantum_data_sentinel_report(state_dir="/tmp/qsentinel_test", write_receipt=False)
    assert report["source_count"] >= 6
    exp_ids = {e["experiment_id"] for e in suggested_swimmer_experiments()}
    assert "tfim_ground_state_real_solve" in exp_ids
    assert "bell_local_receipt_smoke_test" in exp_ids


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
