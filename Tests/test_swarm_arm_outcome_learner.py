#!/usr/bin/env python3
"""Regression guards for receipt-backed agent-arm outcome learning."""

from pathlib import Path
import json
import sys

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_arm_outcome_learner import (
    learn_from_receipts,
    performance_snapshot,
    recommend_arm_for_task,
    summary_for_prompt,
    task_shape_for_text,
)


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _arm_result(
    *,
    receipt_id: str,
    arm_id: str,
    prompt: str,
    ok: bool,
    status: str,
    duration_s: float,
    output_tail: str = "useful evidence",
) -> dict:
    return {
        "ts": 1778330000.0,
        "receipt_id": receipt_id,
        "truth_label": "AGENT_ARM_LAUNCH_RESULT",
        "arm_id": arm_id,
        "mode": "evidence",
        "evidence_mode": True,
        "command": ["internal:agent", "--query", prompt],
        "ok": ok,
        "status": status,
        "duration_s": duration_s,
        "returncode": 0 if ok else None,
        "timed_out": status == "TIMEOUT",
        "output_tail": output_tail,
        "stderr_tail": "",
        "internal_arm": {"internal_runner": "test"} if arm_id == "corvid_scout" else {},
    }


def test_task_shape_matches_arm_router_families() -> None:
    assert task_shape_for_text("Review this repo patch and pytest failure.") == "code"
    assert task_shape_for_text("Summarize this log and extract next action.") == "scout"
    assert task_shape_for_text("Compare two research plans.") == "research"
    assert task_shape_for_text("hello there") == "general"


def test_learns_append_only_rows_and_snapshot_from_arm_receipts(tmp_path: Path) -> None:
    receipt_path = tmp_path / "agent_arm_receipts.jsonl"
    _append_jsonl(
        receipt_path,
        _arm_result(
            receipt_id="corvid-1",
            arm_id="corvid_scout",
            prompt="Summarize this log and extract next action.",
            ok=True,
            status="EVIDENCE_CAPTURED",
            duration_s=2.0,
        ),
    )
    _append_jsonl(
        receipt_path,
        _arm_result(
            receipt_id="hermes-1",
            arm_id="hermes_agent",
            prompt="Summarize this log and extract next action.",
            ok=False,
            status="TIMEOUT",
            duration_s=75.0,
            output_tail="",
        ),
    )

    result = learn_from_receipts(state_dir=tmp_path)

    assert result["learned"] == 2
    rows = (tmp_path / "arm_routing_weights.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 2
    snapshot = performance_snapshot(state_dir=tmp_path)
    assert snapshot["arms"]["corvid_scout"]["success_rate"] == 1.0
    assert snapshot["arms"]["hermes_agent"]["timeouts"] == 1
    assert snapshot["arms"]["corvid_scout"]["profitability"] > snapshot["arms"]["hermes_agent"]["profitability"]
    assert (tmp_path / "arm_performance_summary.json").exists()


def test_learning_deduplicates_source_receipts(tmp_path: Path) -> None:
    _append_jsonl(
        tmp_path / "agent_arm_receipts.jsonl",
        _arm_result(
            receipt_id="codex-1",
            arm_id="codex_agent",
            prompt="Review this repo patch.",
            ok=True,
            status="EVIDENCE_CAPTURED",
            duration_s=8.0,
        ),
    )

    first = learn_from_receipts(state_dir=tmp_path)
    second = learn_from_receipts(state_dir=tmp_path)

    assert first["learned"] == 1
    assert second["learned"] == 0
    assert len((tmp_path / "arm_routing_weights.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_recommendation_prefers_profitable_arm_for_matching_shape(tmp_path: Path) -> None:
    for row in [
        _arm_result(
            receipt_id="codex-good",
            arm_id="codex_agent",
            prompt="Review this repo patch.",
            ok=True,
            status="EVIDENCE_CAPTURED",
            duration_s=6.0,
        ),
        _arm_result(
            receipt_id="hermes-slow",
            arm_id="hermes_agent",
            prompt="Review this repo patch.",
            ok=False,
            status="TIMEOUT",
            duration_s=75.0,
            output_tail="",
        ),
        _arm_result(
            receipt_id="corvid-good",
            arm_id="corvid_scout",
            prompt="Summarize this log and extract next action.",
            ok=True,
            status="EVIDENCE_CAPTURED",
            duration_s=1.0,
        ),
    ]:
        _append_jsonl(tmp_path / "agent_arm_receipts.jsonl", row)
    learn_from_receipts(state_dir=tmp_path)

    assert recommend_arm_for_task("Review this code patch for bugs.", default_arm="hermes_agent", state_dir=tmp_path) == "codex_agent"
    assert recommend_arm_for_task("Summarize this trace and extract next action.", default_arm="hermes_agent", state_dir=tmp_path) == "corvid_scout"


def test_summary_for_prompt_exposes_weights_not_raw_receipts(tmp_path: Path) -> None:
    _append_jsonl(
        tmp_path / "agent_arm_receipts.jsonl",
        _arm_result(
            receipt_id="corvid-1",
            arm_id="corvid_scout",
            prompt="Classify this owner request.",
            ok=True,
            status="EVIDENCE_CAPTURED",
            duration_s=1.0,
        ),
    )
    learn_from_receipts(state_dir=tmp_path)

    summary = summary_for_prompt(state_dir=tmp_path)

    assert "ARM OUTCOME LEARNING" in summary
    assert "arm=corvid_scout" in summary
    assert "profitability=" in summary
