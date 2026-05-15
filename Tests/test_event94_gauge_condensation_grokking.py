#!/usr/bin/env python3
"""Tests for Event 94 gauge / condensation / grokking scaffolding."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from System.swarm_field_primary_research_spine import verified_source_ids
from System.swarm_gauge_condensation_grokking import (
    EVENT94_TRUTH_GUARD,
    TRUTH_LABEL,
    CondensationParams,
    GaugeLatticeConfig,
    U1GaugeLattice,
    condensation_ladder,
    condensation_transition_step,
    detect_grokking_epoch,
    dominant_fourier_mode,
    event94_payload,
    gl_equilibrium_amplitude,
    write_event94_receipt,
)


def test_event94_research_anchors_are_in_field_primary_spine():
    ids = set(verified_source_ids())
    for source_id in (
        "yang_mills_1954_gauge_invariance",
        "wilson_1974_lattice_gauge",
        "bcs_1957_superconductivity",
        "higgs_1964_broken_symmetries",
        "power_2022_grokking",
        "nanda_2023_grokking_mech_interp",
    ):
        assert source_id in ids


def test_truth_guard_is_sim_only_and_payload_names_surfaces():
    payload = event94_payload()
    assert payload["truth_label"] == TRUTH_LABEL
    assert "SIM_ONLY" in EVENT94_TRUTH_GUARD
    assert "u1_lattice_audit_loops" in payload["surfaces"]
    assert "grokking_delay_detector" in payload["surfaces"]


def test_pure_gauge_has_zero_plaquette_and_energy():
    lattice = U1GaugeLattice(GaugeLatticeConfig(height=5, width=6))
    rng = np.random.default_rng(7)
    alpha = rng.uniform(-math.pi, math.pi, size=(5, 6))
    transformed = lattice.gauge_transform(alpha)
    assert np.allclose(transformed.plaquette_angles(), 0.0, atol=1e-10)
    assert transformed.field_strength_energy() == pytest.approx(0.0, abs=1e-10)


def test_plaquettes_and_wilson_loop_are_gauge_invariant():
    cfg = GaugeLatticeConfig(height=8, width=8)
    lattice = U1GaugeLattice.with_uniform_flux(0.08, cfg)
    rng = np.random.default_rng(42)
    shifted = lattice.gauge_transform(rng.uniform(-math.pi, math.pi, size=(8, 8)))
    assert np.allclose(lattice.plaquette_angles(), shifted.plaquette_angles(), atol=1e-10)
    assert lattice.wilson_loop_phase(1, 2, 3, 4) == pytest.approx(
        shifted.wilson_loop_phase(1, 2, 3, 4), abs=1e-10
    )
    assert lattice.field_strength_energy() > 0.0


def test_condensation_ladder_crosses_after_alpha_turns_negative():
    schedule = [0.6, 0.4, 0.2, 0.05, -0.1, -0.4, -0.8, -1.0, -1.0]
    rows = condensation_ladder(
        schedule,
        params=CondensationParams(beta=1.0, relaxation=0.6),
    )
    assert rows[0]["condensate_density"] == pytest.approx(0.0)
    assert rows[-1]["condensate_density"] > rows[4]["condensate_density"]
    assert condensation_transition_step(rows, threshold=0.25) is not None
    assert gl_equilibrium_amplitude(-1.0, beta=1.0) == pytest.approx(1.0)


def test_condensation_params_validate():
    with pytest.raises(ValueError):
        CondensationParams(beta=0.0)
    with pytest.raises(ValueError):
        CondensationParams(relaxation=1.5)


def test_grokking_detector_finds_delayed_generalization():
    train = [1.0, 0.5, 0.2, 0.08, 0.04, 0.03, 0.025, 0.02, 0.018, 0.017, 0.016]
    val = [1.0, 0.98, 0.97, 0.96, 0.95, 0.93, 0.88, 0.75, 0.5, 0.28, 0.12]
    score = [0.0, 0.02, 0.05, 0.08, 0.10, 0.15, 0.25, 0.45, 0.65, 0.85, 0.95]
    result = detect_grokking_epoch(train, val, score, min_delay=5)
    assert result.grokking_detected is True
    assert result.train_fit_epoch == 2
    assert result.generalization_epoch == 9
    assert result.algorithmic_score_gain > 0.2


def test_grokking_detector_rejects_no_delay_case():
    train = [1.0, 0.2, 0.05, 0.03, 0.02, 0.02]
    val = [1.0, 0.3, 0.15, 0.1, 0.08, 0.06]
    score = [0.0, 0.3, 0.5, 0.7, 0.8, 0.9]
    result = detect_grokking_epoch(train, val, score, min_delay=4)
    assert result.grokking_detected is False


def test_dominant_fourier_mode_detects_constructed_mode():
    x = np.arange(64)
    signal = np.sin(2.0 * math.pi * 5 * x / len(x))
    result = dominant_fourier_mode(signal)
    assert result["mode"] == 5
    assert result["mode_fraction"] > 0.99


def test_write_event94_receipt_round_trips(tmp_path: Path):
    path = tmp_path / "event94.jsonl"
    row = write_event94_receipt(
        state_root=tmp_path,
        receipt_path=path,
        extra={"test": True},
    )
    parsed = json.loads(path.read_text(encoding="utf-8").strip())
    assert parsed["trace_id"] == row["trace_id"]
    assert parsed["truth_label"] == TRUTH_LABEL
    assert parsed["kind"] == "EVENT94_GAUGE_CONDENSATION_GROKKING_RECEIPT"
    assert len(parsed["sha256"]) == 64
