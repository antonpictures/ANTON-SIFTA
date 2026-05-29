"""Round 110 (§2.H) — tests for plan resume on cortex failover.

Proves: when the cortex switches (failover or owner choice), the active
plan continues across the body change — the new cortex sees the plan via
the memory card, and the planning ledger gets an audit row.

Pure-Python, no Ollama, no live cortex. Author: Cowork Claude.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_memory_card
from System import swarm_planning_mode as pm


def _write_active_plan(state_dir: Path, plan_id: str = "r110-test-plan") -> Path:
    plan = pm.Plan(
        plan_id=plan_id,
        goal="r110 test goal — wire clamp into homeostasis",
        steps=[
            pm.PlanStep(
                step_id="s1",
                title="NEW bridge module",
                actor="codex_agent",
                action="create swarm_stability_to_homeostasis_bridge.py",
                expected_receipt="work_receipts.jsonl",
                status="done",
            ),
            pm.PlanStep(
                step_id="s2",
                title="PATCH basal_ganglia consult clamp",
                actor="codex_agent",
                action="add stability_homeostasis sub-block",
                expected_receipt="work_receipts.jsonl",
                status="pending",
            ),
            pm.PlanStep(
                step_id="s3",
                title="§4.1 fan-out receipt",
                actor="codex_agent",
                action="call write_ide_surgery_receipt",
                expected_receipt="agent_arm_receipts.jsonl",
                status="pending",
            ),
        ],
    )
    pm.write_plan(plan, state_dir=state_dir)
    return state_dir / pm.LEDGER_NAME


# ─── read_active_plan_for_resume ──────────────────────────────────────────


def test_read_active_plan_returns_none_when_no_plan(tmp_path: Path) -> None:
    assert pm.read_active_plan_for_resume(tmp_path) is None


def test_read_active_plan_returns_latest_active(tmp_path: Path) -> None:
    _write_active_plan(tmp_path, plan_id="r110-test")
    plan = pm.read_active_plan_for_resume(tmp_path)
    assert plan is not None
    assert plan["plan_id"] == "r110-test"
    assert plan["status"] in {"active", "in_progress"}


# ─── mark_plan_resumed ────────────────────────────────────────────────────


def test_mark_plan_resumed_writes_audit_row(tmp_path: Path) -> None:
    _write_active_plan(tmp_path, plan_id="r110-resume-test")
    row = pm.mark_plan_resumed(
        "r110-resume-test",
        source="primary_cortex_switch:grok_timeout",
        switched_from="grok:grok-4.3",
        switched_to="alice-m5-cortex-8b-6.3gb:latest",
        state_dir=tmp_path,
    )
    assert row["event"] == "plan_resumed_on_cortex_switch"
    assert row["plan_id"] == "r110-resume-test"
    assert row["switched_from"] == "grok:grok-4.3"
    assert row["switched_to"] == "alice-m5-cortex-8b-6.3gb:latest"
    assert row["first_pending_step_id"] == "s2"
    ledger = tmp_path / pm.LEDGER_NAME
    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert any(
        json.loads(line).get("event") == "plan_resumed_on_cortex_switch"
        for line in lines
    )


def test_mark_plan_resumed_noop_for_unknown_plan(tmp_path: Path) -> None:
    assert pm.mark_plan_resumed("does-not-exist", source="x", state_dir=tmp_path) == {}


def test_mark_plan_resumed_noop_for_empty_plan_id(tmp_path: Path) -> None:
    assert pm.mark_plan_resumed("", source="x", state_dir=tmp_path) == {}


# ─── active_plan_block ────────────────────────────────────────────────────


def test_active_plan_block_returns_empty_when_no_plan(tmp_path: Path) -> None:
    assert pm.active_plan_block(tmp_path) == ""


def test_active_plan_block_contains_plan_id_goal_pending_step(tmp_path: Path) -> None:
    _write_active_plan(tmp_path, plan_id="r110-block-test")
    block = pm.active_plan_block(tmp_path)
    assert "r110-block-test" in block
    assert "r110 test goal" in block
    # The "s2" pending step should appear in the pending section.
    assert "s2" in block
    # The "s1" done step should appear in the completed section.
    assert "s1" in block
    # Header signals the failover doctrine.
    assert "ACTIVE PLAN" in block
    assert "resume" in block.lower()


# ─── memory card carries the active plan ──────────────────────────────────


def test_memory_card_surfaces_active_plan_block(tmp_path: Path) -> None:
    _write_active_plan(tmp_path, plan_id="r110-card-test")
    card = swarm_memory_card.compose_memory_card(
        ledgers_dir=tmp_path,
        token_budget=2000,
        user_text="resume",
        repo_root=tmp_path,
    )
    assert card.active_plan_block, "active_plan_block missing from MemoryCard"
    assert "r110-card-test" in card.active_plan_block
    rendered = swarm_memory_card.format_for_prompt(card)
    assert "ACTIVE PLAN" in rendered
    # And the plan block should be rendered BEFORE recent_actions so the
    # cortex sees it first on resume.
    plan_idx = rendered.find("ACTIVE PLAN")
    assert plan_idx >= 0
    # If recent_actions_block exists, it should come after.
    if card.recent_actions_block:
        ra_idx = rendered.find(card.recent_actions_block)
        assert ra_idx > plan_idx
