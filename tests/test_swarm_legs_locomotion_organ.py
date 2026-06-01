from __future__ import annotations

import json


def test_walking_laptop_plan_is_first_class_and_truthful_before_hardware():
    from System.swarm_legs_locomotion_organ import (
        ESTIMATED_PARTS_USD,
        TRUTH_LABEL,
        walking_laptop_plan,
    )

    plan = walking_laptop_plan(available_budget_usd=0)

    assert plan["truth_label"] == TRUTH_LABEL
    assert plan["estimated_parts_usd"] == ESTIMATED_PARTS_USD
    assert plan["budget_ready"] is False
    assert "SIFTA Alice laptop body" in plan["body_vision"]
    assert any("3D-printed LeRobot" in item for item in plan["hardware_stack"])
    assert any("MJLab" in item for item in plan["software_stack"])
    assert any("camera stability" in item for item in plan["experience_signals"])
    assert "private owner memory stays local" in plan["experience_inheritance"]


def test_legs_status_exposes_build_stack_and_budget_state(tmp_path):
    from System.swarm_legs_locomotion_organ import ESTIMATED_PARTS_USD, legs_status

    before = legs_status(state_dir=tmp_path, available_budget_usd=0)
    after = legs_status(state_dir=tmp_path, available_budget_usd=ESTIMATED_PARTS_USD)

    assert before["status"] == "PLAN_NO_HARDWARE"
    assert before["hardware_present"] is False
    assert before["budget_ready"] is False
    assert after["budget_ready"] is True
    assert "source or print the legs" in " ".join(after["build_sequence"])


def test_locomotion_request_logs_intent_not_fake_motion(tmp_path):
    from System.swarm_legs_locomotion_organ import request_locomotion

    row = request_locomotion("stand", reason="demo", state_dir=tmp_path, now=123.0)

    assert row["kind"] == "LOCOMOTION_INTENT"
    assert row["ok"] is False
    assert row["executed"] is False
    assert row["status"] == "no_hardware"

    ledger = tmp_path / ".sifta_state" / "alice_legs_locomotion.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["intent"] == "stand"
    assert rows[-1]["executed"] is False


def test_legs_context_block_names_walking_laptop():
    from System.swarm_legs_locomotion_organ import legs_context_block

    block = legs_context_block()

    assert "MY LEGS" in block
    assert "walking-laptop" in block
    assert "bench-verified" in block
