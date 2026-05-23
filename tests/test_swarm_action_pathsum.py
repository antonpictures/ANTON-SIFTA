#!/usr/bin/env python3
"""Tests for Event 94.5 action/path-sum scaffolding."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from System.swarm_action_pathsum import (
    TRUTH_GUARD,
    TRUTH_LABEL,
    ActionPathConfig,
    constructor_constraint_report,
    enumerate_discrete_paths,
    event94_action_payload,
    mass_energy_invariant,
    path_action,
    path_sum_report,
    phase_sum,
    photoelectric_gate,
    write_action_pathsum_receipt,
)
from System.swarm_field_primary_research_spine import verified_source_ids


def test_event94_action_anchors_are_in_field_primary_spine():
    ids = set(verified_source_ids())
    for source_id in (
        "planck_1901_quantum_action",
        "einstein_1905_light_quantum",
        "feynman_1948_path_integral",
        "einstein_1905_mass_energy",
        "everett_1957_relative_state",
        "deutsch_marletto_2012_constructor_theory",
        "koch_meinhardt_1994_biological_pattern",
    ):
        assert source_id in ids


def test_payload_and_truth_guard_are_explicitly_sim_only():
    payload = event94_action_payload()
    assert payload["truth_label"] == TRUTH_LABEL
    assert "SIM_ONLY" in TRUTH_GUARD
    assert "discrete_action_paths" in payload["surfaces"]
    assert "photoelectric_threshold_gate" in payload["surfaces"]


def test_path_enumeration_starts_and_ends_correctly():
    cfg = ActionPathConfig(start=0, end=2, steps=2, max_step=1)
    paths = enumerate_discrete_paths(cfg)
    assert paths == [[0, 1, 2]]


def test_least_action_prefers_smooth_path_over_zigzag():
    smooth = [0, 1, 2, 3, 4]
    zigzag = [0, 2, 0, 2, 4]
    assert path_action(smooth) < path_action(zigzag)


def test_phase_sum_constructive_and_destructive_cases():
    constructive = phase_sum([0.0, 0.0, 0.0], hbar=1.0)
    destructive = phase_sum([0.0, math.pi], hbar=1.0)
    assert constructive["probability_proxy"] == pytest.approx(1.0)
    assert destructive["probability_proxy"] == pytest.approx(0.0, abs=1e-12)


def test_path_sum_report_exposes_least_action_and_phase_sum():
    report = path_sum_report(ActionPathConfig(start=0, end=0, steps=4, max_step=1))
    assert report["truth_label"] == TRUTH_LABEL
    assert report["path_count"] > 1
    assert report["least_action"] == pytest.approx(0.0)
    assert report["least_action_path"] == [0, 0, 0, 0, 0]
    assert report["phase_sum"]["count"] == report["path_count"]


def test_photoelectric_gate_is_energy_threshold_not_intensity_threshold():
    blocked = photoelectric_gate(1.9, 2.0, intensity=10_000.0)
    emitted = photoelectric_gate(2.5, 2.0, intensity=0.01)
    assert blocked["emitted"] is False
    assert blocked["electron_kinetic_energy_ev"] == 0.0
    assert emitted["emitted"] is True
    assert emitted["electron_kinetic_energy_ev"] == pytest.approx(0.5)


def test_mass_energy_invariant_distinguishes_timelike_and_spacelike():
    timelike = mass_energy_invariant(energy=5.0, momentum=3.0, c=1.0)
    spacelike = mass_energy_invariant(energy=5.0, momentum=6.0, c=1.0)
    assert timelike["invariant_mass"] == pytest.approx(4.0)
    assert timelike["timelike"] is True
    assert spacelike["invariant_mass"] is None
    assert spacelike["timelike"] is False


def test_constructor_constraint_report_is_constraint_first():
    report = constructor_constraint_report(
        possible=["append_receipt", "verify_loop"],
        impossible=["claim_unreceipted_effector"],
    )
    assert report["constraint_first"] is True
    assert "claim_unreceipted_effector" in report["impossible_transformations"]


def test_write_action_pathsum_receipt_round_trips(tmp_path: Path):
    path = tmp_path / "action_pathsum.jsonl"
    row = write_action_pathsum_receipt(
        state_root=tmp_path,
        receipt_path=path,
        extra={"test": True},
    )
    parsed = json.loads(path.read_text(encoding="utf-8").strip())
    assert parsed["trace_id"] == row["trace_id"]
    assert parsed["truth_label"] == TRUTH_LABEL
    assert parsed["kind"] == "EVENT94_ACTION_PATHSUM_RECEIPT"
    assert len(parsed["sha256"]) == 64
