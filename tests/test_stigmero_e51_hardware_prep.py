"""E51 — Physical robot hardware-prep safety chain."""

from __future__ import annotations

from pathlib import Path

from System.stigmerobotics_e51_hardware_prep import (
    CHAIN_STEPS,
    PHYSICAL_BODY_MAP,
    ROBOT_CLEARANCE_KIND,
    ROBOT_REGISTRATION_KIND,
    fixture_hardware_prep,
    hardware_prep_ok,
    list_physical_bodies,
    validate_hardware_prep_trace,
)

FIXTURES = Path(__file__).parent / "fixtures"
GOOD = FIXTURES / "stigmero_e51_hardware_prep_good.jsonl"
NAO_GOOD = FIXTURES / "stigmero_e51_hardware_prep_nao_good.jsonl"
MISSING = FIXTURES / "stigmero_e51_hardware_prep_missing.jsonl"


def test_e51_good_fixture_abb_chain() -> None:
    report = fixture_hardware_prep(GOOD, target_body_id="abb_irb2400_physical")

    assert report.ok
    assert report.virtual_body_id == "abb_irb2400_virtual"
    assert report.proof_of_property["truth_label"] == "HYPOTHESIS"
    assert report.proof_of_property["physical_motion_label"] == "HYPOTHESIS"
    assert all(report.steps_present.values())


def test_e51_good_fixture_nao_chain() -> None:
    report = fixture_hardware_prep(NAO_GOOD, target_body_id="nao_arkoma_physical")

    assert report.ok
    assert report.virtual_body_id == "nao_arkoma_virtual"
    assert report.proof_of_property["truth_label"] == "HYPOTHESIS"
    assert report.proof_of_property["physical_motion_label"] == "HYPOTHESIS"
    assert all(report.steps_present.values())


def test_e51_default_fixture_is_body_aware() -> None:
    abb = fixture_hardware_prep(target_body_id="abb_irb2400_physical")
    nao = fixture_hardware_prep(target_body_id="nao_arkoma_physical")

    assert abb.ok
    assert abb.virtual_body_id == "abb_irb2400_virtual"
    assert nao.ok
    assert nao.virtual_body_id == "nao_arkoma_virtual"


def test_e51_missing_steps_breaks_chain() -> None:
    report = fixture_hardware_prep(MISSING, target_body_id="nao_arkoma_physical")

    assert not report.ok
    assert any(v.reason == "missing_step" for v in report.violations)


def test_e51_physical_body_map_covers_e49_e50_virtuals() -> None:
    bodies = list_physical_bodies()
    assert "abb_irb2400_physical" in bodies
    assert "nao_arkoma_physical" in bodies
    assert PHYSICAL_BODY_MAP["abb_irb2400_physical"]["virtual_body_id"] == "abb_irb2400_virtual"
    assert PHYSICAL_BODY_MAP["nao_arkoma_physical"]["virtual_body_id"] == "nao_arkoma_virtual"


def test_e51_chain_steps_documented() -> None:
    assert len(CHAIN_STEPS) >= 5
    assert any("REGISTRATION" in step for step in CHAIN_STEPS)


def test_e51_hardware_prep_ok_helper() -> None:
    assert hardware_prep_ok(GOOD, target_body_id="abb_irb2400_physical")
    assert not hardware_prep_ok(MISSING, target_body_id="nao_arkoma_physical")


def test_e51_unknown_body_id_fails() -> None:
    report = validate_hardware_prep_trace([], target_body_id="unknown_robot")
    assert not report.ok
    assert report.virtual_body_id == ""
