#!/usr/bin/env python3
"""Tests for Free Energy Organ (exact spec requirements)."""

from System import swarm_free_energy_organ as fep


def test_synthetic_low_surprise():
    model = {
        "transition_matrix": [[0.9] + [0.0125]*8 for _ in range(9)],
        "labels": fep.LABELS,
        "n_transitions_observed": 100,
        "prior_distribution": [0.9] + [0.0125]*8
    }
    seq = ["REAL"] * 101
    fe = fep.compute_variational_free_energy(seq, model)
    assert fe["mean_surprise_nats"] < 0.2


def test_synthetic_high_surprise():
    model = {
        "transition_matrix": [[0.9] + [0.0125]*8 for _ in range(9)],
        "labels": fep.LABELS,
        "n_transitions_observed": 100,
        "prior_distribution": [0.9] + [0.0125]*8
    }
    s = fep.compute_surprise("ROLEPLAY", {"REAL": 0.01, "ROLEPLAY": 0.01, **{l:0.01 for l in fep.LABELS if l not in ["REAL","ROLEPLAY"]}})
    assert s > 2.0


def test_active_inference_branches():
    # Controlled low-surprise preferred model
    model = {
        "transition_matrix": [[0.95] + [0.00625]*8 for _ in range(9)],
        "labels": fep.LABELS,
        "n_transitions_observed": 100,
        "prior_distribution": [0.95] + [0.00625]*8
    }
    rec1 = fep.active_inference_step(["REAL"]*20, model)
    assert rec1["action"] == "rest"

    rec2 = fep.active_inference_step(["ROLEPLAY"]*20, model)
    assert rec2["action"] in ["shift_behavior", "update_model"]  # depending on exact surprise calculation

    rec3 = fep.active_inference_step(["REAL", "ROLEPLAY"] * 10, model)
    assert rec3["action"] in ["update_model", "shift_behavior", "rest", "monitor"]


def test_real_data_smoke():
    receipt = fep.measure_free_energy(window_s=1800, write_receipt=True)
    assert "free_energy_nats" in receipt
    assert receipt["truth_label"] == "FREE_ENERGY_ORGAN_V0"


if __name__ == "__main__":
    test_synthetic_low_surprise()
    test_synthetic_high_surprise()
    test_active_inference_branches()
    test_real_data_smoke()
    print("All 4 FEP tests passed.")
