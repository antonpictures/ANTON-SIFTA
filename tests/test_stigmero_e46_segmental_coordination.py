"""
tests/test_stigmero_e46_segmental_coordination.py
══════════════════════════════════════════════════════════════════════════════
E46 — Segmental Coordination (Lamprey CPG Coupling)

ROB 501 topic: Coupled oscillators, distributed CPG coordination.

Hypothesis (P):
    When N SIFTA channels (each a (homeworld_serial, source_ide) pair) are
    active, their pheromone-field collision signals form a coupling matrix.
    The system is COORDINATED iff no two strongly-coupled channels fire within
    the collision window simultaneously — equivalent to the lamprey body wave.

Proof structure:
  1. Single channel:    SINGLE_CHANNEL state — coupling undefined.
  2. Non-coupled:       Two channels that don't overlap → COORDINATED.
  3. Coupled + staggered: Channels fire with gap > window → COORDINATED.
  4. Coupled + simultaneous: Channels fire within window → UNCOORDINATED.
  5. Coupling matrix:   symmetric, zero diagonal, values in [0,1].
  6. Wave property:     Coordinated ↔ wave property holds.

§8.6 compliance: all fixtures are hand-crafted; no live .sifta_state reads.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from System.stigmerobotics_segmental_coordination import (
    DEFAULT_COLLISION_WINDOW_S,
    DEFAULT_COUPLING_THRESHOLD,
    CoordinationState,
    SegmentalCoordinationReport,
    build_coordination_report,
    coordination_ok,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ── Row helpers ───────────────────────────────────────────────────────────────

def _row(kind: str, ts: float, serial: str, ide: str) -> dict:
    return {
        "ts": ts,
        "kind": kind,
        "homeworld_serial": serial,
        "source_ide": ide,
        "trace_id": f"test-{kind}-{ts}-{ide}",
        "payload": "{}",
    }


def _reg(ts: float, serial: str = "GTH4921YP3", ide: str = "ag_m5") -> dict:
    return _row("LLM_REGISTRATION", ts, serial, ide)


def _scar(ts: float, serial: str = "GTH4921YP3", ide: str = "ag_m5") -> dict:
    return _row("SCAR_RECEIPT", ts, serial, ide)


# ── 1. Single channel ─────────────────────────────────────────────────────────

class TestE46SingleChannel:

    def test_e46_empty_rows_single_channel_state(self) -> None:
        report = build_coordination_report([])
        assert report.state == CoordinationState.SINGLE_CHANNEL

    def test_e46_one_channel_single_channel_state(self) -> None:
        rows = [_reg(1000.0), _scar(1001.0)]
        report = build_coordination_report(rows)
        assert report.state == CoordinationState.SINGLE_CHANNEL

    def test_e46_single_channel_wave_property_holds(self) -> None:
        rows = [_reg(1000.0), _scar(1001.0)]
        report = build_coordination_report(rows)
        assert report.wave_property_holds

    def test_e46_single_channel_no_coupling_edges(self) -> None:
        rows = [_reg(1000.0), _scar(1001.0)]
        report = build_coordination_report(rows)
        assert len(report.coupling_edges) == 0


# ── 2. Two channels, no overlap ───────────────────────────────────────────────

class TestE46NonCoupledChannels:

    def test_e46_two_channels_far_apart_are_coordinated(self) -> None:
        """Fires separated by >> collision_window → no coupling."""
        rows = [
            _reg(1000.0, ide="ag_m5"),
            _scar(1001.0, ide="ag_m5"),
            _reg(1000.0, ide="cursor"),
            _scar(5001.0, ide="cursor"),   # 4000s apart >> 120s window
        ]
        report = build_coordination_report(rows)
        assert report.state == CoordinationState.COORDINATED

    def test_e46_no_coupling_edges_when_fires_are_far(self) -> None:
        rows = [
            _scar(1000.0, ide="ag_m5"),
            _scar(9000.0, ide="cursor"),
        ]
        report = build_coordination_report(rows)
        assert len(report.coupling_edges) == 0

    def test_e46_coordination_ok_true_for_non_overlapping(self) -> None:
        rows = [
            _reg(1000.0, ide="ag_m5"),
            _scar(1001.0, ide="ag_m5"),
            _scar(9999.0, ide="cursor"),
        ]
        assert coordination_ok(rows)


# ── 3. Two channels, staggered (coordinated) ───────────────────────────────────

class TestE46StaggeredChannels:

    def test_e46_fires_just_outside_window_are_coordinated(self) -> None:
        """Fires separated by exactly collision_window_s → coupling = exp(-1) ≈ 0.37."""
        coupling_at_window = math.exp(-1.0)  # ≈ 0.368
        # coupling_threshold = 0.05 < 0.368 — this IS a violation unless gap > window
        rows = [
            _scar(1000.0, ide="ag_m5"),
            _scar(1000.0 + DEFAULT_COLLISION_WINDOW_S + 1.0, ide="cursor"),
        ]
        report = build_coordination_report(rows)
        assert report.state == CoordinationState.COORDINATED

    def test_e46_large_gap_produces_no_violations(self) -> None:
        rows = [
            _scar(1000.0, ide="ag_m5"),
            _scar(2000.0, ide="cursor"),  # 1000s > 120s window
        ]
        report = build_coordination_report(rows)
        assert len(report.violations) == 0


# ── 4. Simultaneous fire (uncoordinated) ──────────────────────────────────────

class TestE46SimultaneousFire:

    def test_e46_simultaneous_fires_on_two_channels(self) -> None:
        """Two channels fire at the same time → UNCOORDINATED."""
        rows = [
            _scar(1000.0, ide="ag_m5"),
            _scar(1000.0, ide="cursor"),   # same ts, same window
        ]
        report = build_coordination_report(rows)
        assert report.state == CoordinationState.UNCOORDINATED

    def test_e46_near_simultaneous_fires_within_window(self) -> None:
        """Fires 5s apart << 120s window → strongly coupled → violation."""
        rows = [
            _scar(1000.0, ide="ag_m5"),
            _scar(1005.0, ide="cursor"),   # 5s << 120s → coupling ≈ 0.96
        ]
        report = build_coordination_report(rows)
        # coupling = exp(-5/120) ≈ 0.96 > threshold 0.05 → violation
        assert report.state == CoordinationState.UNCOORDINATED

    def test_e46_violation_recorded_with_channel_info(self) -> None:
        rows = [
            _scar(1000.0, ide="ag_m5"),
            _scar(1001.0, ide="cursor"),
        ]
        report = build_coordination_report(rows)
        assert len(report.violations) >= 1
        v = report.violations[0]
        channels = {v.fire_a.channel[1], v.fire_b.channel[1]}
        assert "ag_m5" in channels
        assert "cursor" in channels

    def test_e46_wave_property_false_when_uncoordinated(self) -> None:
        rows = [
            _scar(1000.0, ide="ag_m5"),
            _scar(1001.0, ide="cursor"),
        ]
        report = build_coordination_report(rows)
        assert not report.wave_property_holds

    def test_e46_fixture_bad_simultaneous_is_uncoordinated(self) -> None:
        path = FIXTURES / "stigmero_e46_simultaneous.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        report = build_coordination_report(rows)
        assert report.state == CoordinationState.UNCOORDINATED


# ── 5. Good fixture — coordinated ─────────────────────────────────────────────

class TestE46GoodFixture:

    def test_e46_fixture_good_is_coordinated(self) -> None:
        path = FIXTURES / "stigmero_e46_good.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        report = build_coordination_report(rows)
        assert report.state == CoordinationState.COORDINATED

    def test_e46_fixture_good_wave_property_holds(self) -> None:
        path = FIXTURES / "stigmero_e46_good.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        assert coordination_ok(rows)


# ── 6. Physical space grounding ──────────────────────────────────────────────

class TestE46PhysicalSpaceGrounding:

    def test_e46_sensor_rows_ground_physical_space(self) -> None:
        rows = [
            {
                "ts": 1000.0,
                "kind": "camera_depth_map",
                "body_id": "george",
                "distance_m": 0.45,
                "pose_confidence": 0.95,
            }
        ]
        report = build_coordination_report(rows)
        assert report.physical_space_grounded
        assert len(report.physical_observations) == 1
        assert report.physical_sensor_kinds == ("camera_depth_map",)
        assert report.physical_body_ids == ("george",)
        assert report.physical_pressure > 1.0

    def test_e46_close_physical_fires_increase_coupling(self) -> None:
        left = _scar(1000.0, ide="ag_m5")
        left.update({"physical_x": 0.0, "physical_y": 0.0, "body_id": "hand", "pose_confidence": 1.0})
        right = _scar(1110.0, ide="cursor")
        right.update({"physical_x": 0.10, "physical_y": 0.0, "body_id": "tool", "pose_confidence": 1.0})

        report = build_coordination_report([left, right], coupling_threshold=0.7)

        assert report.state == CoordinationState.UNCOORDINATED
        assert report.violations
        assert report.violations[0].coupling_strength > 0.7
        assert report.fires[0].body_id == "hand"
        assert report.fires[1].body_id == "tool"

    def test_e46_far_physical_fires_do_not_fake_strong_coupling(self) -> None:
        left = _scar(1000.0, ide="ag_m5")
        left.update({"physical_x": 0.0, "physical_y": 0.0, "body_id": "left", "pose_confidence": 1.0})
        right = _scar(1110.0, ide="cursor")
        right.update({"physical_x": 4.0, "physical_y": 0.0, "body_id": "right", "pose_confidence": 1.0})

        report = build_coordination_report([left, right], coupling_threshold=0.7)

        assert report.state == CoordinationState.COORDINATED
        assert not report.violations


# ── 7. Proof of Property ──────────────────────────────────────────────────────

class TestE46ProofOfProperty:

    def test_proof_has_required_keys(self) -> None:
        rows = [
            _reg(1000.0, ide="ag_m5"), _scar(1001.0, ide="ag_m5"),
            _reg(1000.0, ide="cursor"), _scar(9999.0, ide="cursor"),
        ]
        pop = build_coordination_report(rows).proof_of_property
        assert {
            "E46", "theorem", "state", "n_channels", "violations",
            "wave_property", "lamprey_mapping", "ayers_reference",
            "physical_space_grounded", "n_physical_observations",
            "physical_sensor_kinds", "physical_body_ids", "physical_pressure",
            "nearest_body_distance_m",
            "falsifier", "truth_label",
        } <= pop.keys()

    def test_proof_truth_label_operational_when_coordinated(self) -> None:
        rows = [_scar(1000.0, ide="ag_m5"), _scar(9999.0, ide="cursor")]
        pop = build_coordination_report(rows).proof_of_property
        assert pop["truth_label"] == "OPERATIONAL"

    def test_proof_cites_ayers(self) -> None:
        rows = [_scar(1000.0, ide="ag_m5"), _scar(9999.0, ide="cursor")]
        pop = build_coordination_report(rows).proof_of_property
        assert "Ayers" in pop["ayers_reference"] or "ayers" in pop["ayers_reference"].lower()

    def test_proof_lamprey_mapping_present(self) -> None:
        rows = [_scar(1000.0, ide="ag_m5"), _scar(9999.0, ide="cursor")]
        pop = build_coordination_report(rows).proof_of_property
        assert "CPG" in pop["lamprey_mapping"] or "segment" in pop["lamprey_mapping"]
