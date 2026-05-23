#!/usr/bin/env python3
"""Acceptance tests for Q6 run_all_evals orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import System.swarm_eval_loop as H


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    return path


def _memory_pack(path: Path) -> Path:
    return _write_jsonl(path, [
        {"truth_label": "TEST_MEMORY"},
        {
            "turn_id": "m01",
            "target": "hybrid_recall",
            "seed_memories": [{"text": "alpha receipt exists", "epistemic_label": "OBSERVED"}],
            "query": "alpha receipt",
            "expect": {"must_include_substring": "alpha receipt"},
        },
    ])


def _talk_pack(path: Path) -> Path:
    return _write_jsonl(path, [
        {"truth_label": "TEST_TALK"},
        {
            "turn_id": "t01",
            "target": "talk_outcome",
            "redacted_snippet": "Local Talk row event=test; role=alice; text_len=42.",
            "rubric": {"answer_correct": True},
        },
    ])


def _skill_pack(path: Path) -> Path:
    return _write_jsonl(path, [
        {"truth_label": "TEST_SKILL"},
        {
            "turn_id": "s01",
            "target": "skill_invoke",
            "skill_name": "memory_store",
            "expect": {"receipt_status_in": ["success"]},
        },
    ])


def test_run_all_evals_sums_packs_and_human_labels(tmp_path):
    memory = _memory_pack(tmp_path / "memory.jsonl")
    talk = _talk_pack(tmp_path / "talk.jsonl")
    skill = _skill_pack(tmp_path / "skill.jsonl")
    receipts = _write_jsonl(tmp_path / "skill_receipts.jsonl", [
        {"skill_name": "memory_store", "status": "success", "trace_id": "skill-trace"}
    ])
    verdicts = _write_jsonl(tmp_path / "eval_verdicts.jsonl", [
        {
            "turn_id": "t01",
            "trace_id": "human-trace",
            "verdict": "correct",
            "failed_rubric_keys": [],
            "labeled_by": "GEORGE",
        }
    ])

    report = H.run_all_evals(
        memory_golden_path=memory,
        talk_golden_path=talk,
        skill_golden_path=skill,
        regression_path=tmp_path / "empty_regression.jsonl",
        verdicts_path=verdicts,
        skill_receipts_path=receipts,
        metrics_dir=tmp_path / "metrics",
        receipts_path=tmp_path / "receipts.jsonl",
        write_receipt=False,
    )

    assert report["totals"]["passed"] == 3
    assert report["totals"]["failed"] == 0
    assert report["totals"]["unverifiable"] == 0
    assert report["totals"]["human_labeled"] == 1
    assert report["pack_summary"]["memory"]["passed"] == 1
    assert report["pack_summary"]["talk"]["passed"] == 1
    assert report["pack_summary"]["skill"]["passed"] == 1
    assert report["pack_summary"]["regression"]["turns"] == 0


def test_run_all_evals_surfaces_zero_human_labels(tmp_path):
    report = H.run_all_evals(
        memory_golden_path=_memory_pack(tmp_path / "memory.jsonl"),
        talk_golden_path=_talk_pack(tmp_path / "talk.jsonl"),
        skill_golden_path=_skill_pack(tmp_path / "skill.jsonl"),
        regression_path=tmp_path / "empty_regression.jsonl",
        verdicts_path=tmp_path / "missing_verdicts.jsonl",
        skill_receipts_path=_write_jsonl(tmp_path / "skill_receipts.jsonl", []),
        metrics_dir=tmp_path / "metrics",
        receipts_path=tmp_path / "receipts.jsonl",
        write_receipt=False,
    )

    assert report["totals"]["human_labeled"] == 0
    assert report["pack_summary"]["talk"]["unverifiable"] == 1
    assert report["pack_summary"]["skill"]["unverifiable"] == 1


def test_run_all_evals_writes_one_receipt(tmp_path):
    receipt_path = tmp_path / "receipts.jsonl"
    report = H.run_all_evals(
        memory_golden_path=_memory_pack(tmp_path / "memory.jsonl"),
        talk_golden_path=_talk_pack(tmp_path / "talk.jsonl"),
        skill_golden_path=_skill_pack(tmp_path / "skill.jsonl"),
        regression_path=tmp_path / "empty_regression.jsonl",
        verdicts_path=tmp_path / "missing_verdicts.jsonl",
        skill_receipts_path=_write_jsonl(tmp_path / "skill_receipts.jsonl", []),
        metrics_dir=tmp_path / "metrics",
        receipts_path=receipt_path,
        write_receipt=True,
    )

    rows = [json.loads(line) for line in receipt_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["work_type"] == "EVAL_RUN_ALL"
    assert rows[0]["trace_id"] == report["eval_receipt_id"]
    assert Path(report["rollup_path"]).exists()


def test_campaign_helpers_write_matrix_facing_ledgers(tmp_path):
    skill = _skill_pack(tmp_path / "skill.jsonl")
    skill_receipts = _write_jsonl(tmp_path / "skill_receipts.jsonl", [
        {"skill_name": "memory_store", "status": "success", "trace_id": "skill-trace"}
    ])
    free_text = _write_jsonl(tmp_path / "free_text.jsonl", [
        {"truth_label": "TEST_FREETEXT"},
        {
            "turn_id": "ft01",
            "target": "free_text",
            "prompt": "hello",
            "response": "grounded answer",
            "expect": {"min_score": 0.5},
        },
    ])
    verdicts = _write_jsonl(tmp_path / "eval_verdicts.jsonl", [
        {
            "turn_id": "t01",
            "conversation_ref": "alice_conversation.jsonl#event:test#hash:abc",
            "trace_id": "human-trace",
            "verdict": "incorrect",
            "failed_rubric_keys": ["answer_correct"],
            "labeled_by": "GEORGE",
        }
    ])
    regressions = tmp_path / "regressions.jsonl"
    H.freeze_failures_to_regression(verdicts_path=verdicts, out_path=regressions, write_receipt=False)

    skill_report = H.run_skill_campaign(
        golden_path=skill,
        skill_receipts_path=skill_receipts,
        runs_path=tmp_path / "cs153_skill_runs.jsonl",
        metrics_path=tmp_path / "skill_metrics.jsonl",
        receipts_path=tmp_path / "receipts.jsonl",
        write_receipt=False,
    )
    free_report = H.run_free_text_campaign(
        golden_path=free_text,
        runs_path=tmp_path / "cs153_free_text_runs.jsonl",
        metrics_path=tmp_path / "free_metrics.jsonl",
        receipts_path=tmp_path / "receipts.jsonl",
        judge_fn=lambda text, ctx: {"score": 0.9, "reason": "local", "judge_used": True},
        write_receipt=False,
    )
    regression_report = H.run_regression_campaign(
        regression_path=regressions,
        verdicts_path=verdicts,
        runs_path=tmp_path / "cs153_regression_runs.jsonl",
        metrics_path=tmp_path / "regression_metrics.jsonl",
        receipts_path=tmp_path / "receipts.jsonl",
        write_receipt=False,
    )

    assert Path(skill_report["runs_path"]).exists()
    assert Path(free_report["runs_path"]).exists()
    assert Path(regression_report["runs_path"]).exists()
    assert json.loads(Path(free_report["runs_path"]).read_text(encoding="utf-8").splitlines()[-1])["judge_used"] is True
