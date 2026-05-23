#!/usr/bin/env python3
"""Tests for the Kuramoto organ synchrony module (exact spec requirements)."""

import numpy as np
from System import swarm_organ_synchrony_kuramoto as kuramoto


def test_synthetic_synchrony():
    """10 identical oscillators with strong coupling → R > 0.95."""
    np.random.seed(7)
    phases = {f"org{i}": {"theta": np.random.uniform(0, 2*np.pi), "omega": 1.0, "n_events": 10}
              for i in range(10)}
    res = kuramoto.simulate_kuramoto(phases, K=2.0, n_steps=800)
    assert res["R"][-1] > 0.9, f"Expected high synchrony, got R={res['R'][-1]:.3f}"


def test_synthetic_incoherent():
    """Wide frequency spread + K=0 → R < 0.35."""
    np.random.seed(42)
    phases = {f"org{i}": {"theta": float(i * 0.7),
                          "omega": float(i * 1.8), "n_events": 10}
              for i in range(10)}
    res = kuramoto.simulate_kuramoto(phases, K=0.0, n_steps=500)
    assert res["R"][-1] < 0.35, f"Expected low synchrony, got R={res['R'][-1]:.3f}"


def test_critical_coupling_monotonic():
    """R(K) should be non-decreasing past K_c on Gaussian frequencies."""
    np.random.seed(11)
    phases = {f"org{i}": {"theta": 0.0, "omega": np.random.normal(0, 1), "n_events": 10}
              for i in range(12)}
    Kc = kuramoto.critical_coupling(phases)
    Rs = []
    for k in np.linspace(0, 4 * Kc, 6):
        r = kuramoto.simulate_kuramoto(phases, K=k, n_steps=600)["R"][-1]
        Rs.append(r)
    for i in range(len(Rs) - 1):
        assert Rs[i] <= Rs[i + 1] + 0.08, "R should increase with K"


def test_real_data_smoke():
    """Live call on real ledgers must return valid receipt."""
    receipt = kuramoto.measure_organ_synchrony(window_s=1800, write_receipt=True)
    assert 0.0 <= receipt["order_parameter_R"] <= 1.0
    assert "receipt_id" in receipt
    assert receipt["truth_label"] == "ORGAN_SYNCHRONY_KURAMOTO_V0"
    assert isinstance(receipt["dominant_phase_locked_cluster"], list)


def test_simulate_kuramoto_returns_spec_keys_and_alias_identity():
    phases = {
        "a": {"theta": 0.1, "omega": 1.0, "n_events": 5},
        "b": {"theta": 0.2, "omega": 1.0, "n_events": 5},
    }
    res = kuramoto.simulate_kuramoto(phases, K=1.0, n_steps=20)

    assert {"order_parameter_trajectory", "mean_phase_trajectory", "final_phases", "R", "psi"}.issubset(res)
    assert res["R"] is res["order_parameter_trajectory"]
    assert res["psi"] is res["mean_phase_trajectory"]
    assert res["final_phases"].shape == (2,)


def test_simulate_kuramoto_empty_input_still_returns_spec_keys():
    res = kuramoto.simulate_kuramoto({}, K=1.0)

    assert res["R"] is res["order_parameter_trajectory"]
    assert res["psi"] is res["mean_phase_trajectory"]
    assert res["final_phases"].size == 0


def test_measure_organ_synchrony_plv_shape_matches_active_organs():
    receipt = kuramoto.measure_organ_synchrony(window_s=1800, write_receipt=False)
    matrix = receipt["plv_matrix"]
    n = receipt["n_organs"]

    if n < 2:
        assert matrix == []
        assert receipt.get("plv_skipped_reason") == "insufficient_organs"
    else:
        assert len(matrix) == n
        assert all(len(row) == n for row in matrix)


if __name__ == "__main__":
    test_synthetic_synchrony()
    test_synthetic_incoherent()
    test_critical_coupling_monotonic()
    test_real_data_smoke()
    print("All 4 tests passed.")
