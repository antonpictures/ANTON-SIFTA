from __future__ import annotations

import json
from pathlib import Path

from System import swarm_planning_mode as planning


def _valid_plan_text() -> str:
    return """```json
{
  "goal": "Improve Alice chat readability",
  "success_criteria": "Tests pass and the renderer remains readable",
  "steps": [
    {
      "step_id": "s1",
      "title": "Inspect current renderer",
      "actor": "alice_cortex",
      "action": "Read the current renderer and identify the next safe patch",
      "expected_receipt": "alice_plans.jsonl",
      "status": "pending"
    },
    {
      "step_id": "s2",
      "title": "Patch renderer",
      "actor": "codex_agent",
      "action": "Implement the scoped renderer patch and run tests",
      "expected_receipt": "work_receipts.jsonl action=round63_s2",
      "status": "pending"
    }
  ],
  "risks": ["Do not rewrite the whole widget in one patch"],
  "next_receipt_expected": "alice_plans.jsonl plan_write"
}
```"""


def _rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_valid_plan_parses_and_writes_one_append_only_row(tmp_path):
    plan = planning.parse_plan(_valid_plan_text())

    assert plan is not None
    assert plan.goal == "Improve Alice chat readability"
    assert [step.actor for step in plan.steps] == ["alice_cortex", "codex_agent"]

    row = planning.write_plan(plan, state_dir=tmp_path)

    ledger = tmp_path / "alice_plans.jsonl"
    rows = _rows(ledger)
    assert len(rows) == 1
    assert rows[0] == row
    assert row["plan_id"].startswith("plan_")
    assert row["truth_label"] == "ALICE_STIGMERGIC_PLAN_V1"
    for key in ("plan_id", "ts", "goal", "mode", "status", "steps", "metabolic_mode", "receipt_refs"):
        assert key in row


def test_malformed_plan_is_rejected_without_ledger_mutation(tmp_path):
    assert planning.parse_plan("not json and not a plan") is None

    ledger = tmp_path / "alice_plans.jsonl"
    assert not ledger.exists()


def test_invalid_actor_rejected_without_ledger_mutation(tmp_path):
    text = _valid_plan_text().replace('"codex_agent"', '"unreceipted_robot"')

    assert planning.parse_plan(text) is None
    assert not (tmp_path / "alice_plans.jsonl").exists()


def test_step_update_appends_new_row_and_preserves_history(tmp_path):
    plan = planning.parse_plan(_valid_plan_text())
    assert plan is not None
    first = planning.write_plan(plan, state_dir=tmp_path)

    update = planning.update_plan_step(
        first["plan_id"],
        "s2",
        "ok",
        receipt_ref="work-r63-s2",
        note="renderer patch tested",
        state_dir=tmp_path,
    )

    rows = _rows(tmp_path / "alice_plans.jsonl")
    assert len(rows) == 2
    assert rows[0] == first
    assert rows[1] == update
    assert rows[1]["event"] == "step_update"
    assert rows[1]["receipt_refs"] == ["work-r63-s2"]
    assert [s for s in rows[1]["steps"] if s["step_id"] == "s2"][0]["status"] == "ok"


def test_planning_prompt_block_includes_latest_active_plan_and_receipt_refs(tmp_path):
    plan = planning.parse_plan(_valid_plan_text())
    assert plan is not None
    first = planning.write_plan(plan, state_dir=tmp_path)
    planning.update_plan_step(
        first["plan_id"],
        "s1",
        "in_progress",
        receipt_ref="plan-read-r63",
        state_dir=tmp_path,
    )

    block = planning.planning_prompt_block(state_dir=tmp_path)

    assert "ALICE STIGMERGIC PLANNING MODE" in block
    assert "not an owner approval gate" in block
    assert first["plan_id"] in block
    assert "Improve Alice chat readability" in block
    assert "plan-read-r63" in block
    assert "codex_agent" in block
