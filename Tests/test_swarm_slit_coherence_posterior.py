from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from System import swarm_slit_coherence_posterior as slit


@pytest.fixture(autouse=True)
def _allow_thermodynamics(monkeypatch):
    monkeypatch.setattr(
        slit,
        "_processing_clearance",
        lambda process_kind, payload, expected_value, write_ledger: {
            "allowed": True,
            "action": "allow",
            "receipt_hash": "thermo-test",
            "body": {"thermal_warning_level": 0, "budget_multiplier": 1.0},
        },
    )


def test_slit_coherence_posterior_recovers_equal_slit_gamma():
    x_axis, observed = slit.simulate_detector_pattern(
        gamma=0.72,
        noise_sigma=0.002,
        seed=7,
    )

    result = slit.infer_coherence_posterior(
        x_axis,
        observed,
        planted_gamma=0.72,
        write_ledger=False,
    )

    assert result.truth_label == "SIFTA_SLIT_COHERENCE_POSTERIOR_V0"
    assert result.thermodynamic_clearance["allowed"] is True
    assert result.swimmer_census["all_swimmers_accounted"] is True
    assert result.swimmer_census["unaccounted_swimmers"] == 0
    assert result.swimmer_census["swimmer_count"] == result.n_swimmers
    assert result.gamma_abs_error is not None
    assert result.gamma_abs_error < 0.06
    assert 0.65 <= result.posterior_mean_gamma <= 0.79
    assert result.posterior_std_gamma < 0.08


def test_slit_coherence_posterior_separates_low_and_high_visibility():
    x_low, observed_low = slit.simulate_detector_pattern(gamma=0.05, noise_sigma=0.001, seed=1)
    x_high, observed_high = slit.simulate_detector_pattern(gamma=0.95, noise_sigma=0.001, seed=2)

    low = slit.infer_coherence_posterior(x_low, observed_low, write_ledger=False)
    high = slit.infer_coherence_posterior(x_high, observed_high, write_ledger=False)

    assert low.posterior_mean_gamma < 0.15
    assert high.posterior_mean_gamma > 0.85
    assert high.posterior_mean_gamma - low.posterior_mean_gamma > 0.70


def test_slit_coherence_posterior_can_search_phase_when_unknown():
    phase = 0.40
    x_axis, observed = slit.simulate_detector_pattern(
        gamma=0.60,
        phase_rad=phase,
        noise_sigma=0.001,
        seed=3,
    )
    phase_grid = np.linspace(-0.6, 0.6, 25)

    result = slit.infer_coherence_posterior(
        x_axis,
        observed,
        phase_grid_rad=phase_grid,
        planted_gamma=0.60,
        write_ledger=False,
    )

    assert abs(result.posterior_mean_gamma - 0.60) < 0.08
    assert abs(result.posterior_map_phase_rad - phase) <= 0.06


def test_survival_visibility_discovery_learns_linear_rule():
    cases = []
    for i, p_survive in enumerate((0.20, 0.40, 0.65, 0.90)):
        x_axis, observed = slit.simulate_detector_pattern(
            gamma=p_survive,
            noise_sigma=0.001,
            seed=100 + i,
        )
        cases.append(
            slit.CoherenceCase(
                p_survive=p_survive,
                x_m=x_axis,
                observed_intensity=observed,
                label=f"case-{i}",
            )
        )

    result = slit.discover_survival_visibility_rule(cases, write_ledger=False)

    assert result.truth_label == "SIFTA_SLIT_COHERENCE_POSTERIOR_V0"
    assert 0.88 <= result.posterior_mean_scale <= 1.12
    assert abs(result.posterior_mean_exponent - 1.0) < 0.18
    assert result.posterior_std_exponent < 0.20


def test_slit_coherence_receipts_are_truth_labeled(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(slit, "_PHEROMONE_LEDGER", tmp_path / "pheromone.jsonl")
    monkeypatch.setattr(slit, "_CENSUS_LEDGER", tmp_path / "census.jsonl")
    monkeypatch.setattr(slit, "_RECEIPTS_LEDGER", tmp_path / "receipts.jsonl")
    monkeypatch.setattr(slit, "_DISCOVERY_LEDGER", tmp_path / "discovery.jsonl")
    monkeypatch.setattr(slit, "_request_clearance", lambda lane, cost="feather": {"clearance_hash": f"test:{lane}"})
    monkeypatch.setattr(
        slit,
        "_processing_clearance",
        lambda process_kind, payload, expected_value, write_ledger: {
            "allowed": True,
            "action": "allow",
            "receipt_hash": "thermo-test",
            "body": {"thermal_warning_level": 0, "budget_multiplier": 1.0},
        },
    )
    monkeypatch.setattr(slit, "_qualia_marker", lambda lane, note="": {"lane": lane, "note": note})

    x_axis, observed = slit.simulate_detector_pattern(gamma=0.50, noise_sigma=0.0)
    result = slit.infer_coherence_posterior(
        x_axis,
        observed,
        gamma_grid=np.linspace(0.0, 1.0, 21),
        ticks=2,
        planted_gamma=0.50,
        write_ledger=True,
    )

    receipt_rows = [
        json.loads(line)
        for line in (tmp_path / "receipts.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    pheromone_rows = [
        json.loads(line)
        for line in (tmp_path / "pheromone.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    census_rows = [
        json.loads(line)
        for line in (tmp_path / "census.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert receipt_rows[-1]["receipt_id"] == result.receipt_id
    assert receipt_rows[-1]["truth_label"] == "SIFTA_SLIT_COHERENCE_POSTERIOR_V0"
    assert receipt_rows[-1]["equal_intensity_boundary"].startswith("Michelson V")
    assert receipt_rows[-1]["thermodynamic_clearance"]["receipt_hash"] == "thermo-test"
    assert receipt_rows[-1]["swimmer_census"]["swimmer_count"] == 21
    assert receipt_rows[-1]["swimmer_census"]["unaccounted_swimmers"] == 0
    assert receipt_rows[-1]["swimmer_census"]["all_swimmers_accounted"] is True
    assert receipt_rows[-1]["clearance_hash"] == "test:slit.coherence.posterior"
    assert census_rows[-1]["swimmer_count"] == 21
    assert len(census_rows[-1]["swimmers"]) == 21
    assert pheromone_rows
    assert all(row["swimmer_id"].startswith("slit-") for row in pheromone_rows)
