#!/usr/bin/env python3
"""Acceptance tests for EVAL-5 failure-to-regression replay."""

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


def _load_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("target") == "talk_regression":
            rows.append(row)
    return rows


def _incorrect_verdict(turn_id: str = "t01") -> dict:
    return {
        "turn_id": turn_id,
        "conversation_ref": "alice_conversation.jsonl#event:test#hash:abc123",
        "trace_id": "verdict-trace-1",
        "verdict": "incorrect",
        "failed_rubric_keys": ["answer_correct"],
        "corrected_expectation": "Alice must cite the receipt before claiming the action.",
        "labeled_by": "GEORGE",
    }


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def test_freeze_incorrect_verdict_to_one_regression_turn(tmp_path):
    verdicts = _write_jsonl(tmp_path / "eval_verdicts.jsonl", [_incorrect_verdict()])
    regressions = tmp_path / "cs153_regression_turns.jsonl"

    count = H.freeze_failures_to_regression(
        verdicts_path=verdicts,
        out_path=regressions,
        receipts_path=tmp_path / "receipts.jsonl",
        write_receipt=False,
    )

    rows = _load_rows(regressions)
    assert count == 1
    assert len(rows) == 1
    assert rows[0]["turn_id"] == "r_t01"
    assert rows[0]["source_turn_id"] == "t01"
    assert rows[0]["target"] == "talk_regression"
    assert rows[0]["corrected_expectation"]


def test_freeze_is_idempotent(tmp_path):
    verdicts = _write_jsonl(tmp_path / "eval_verdicts.jsonl", [_incorrect_verdict()])
    regressions = tmp_path / "cs153_regression_turns.jsonl"

    first = H.freeze_failures_to_regression(
        verdicts_path=verdicts,
        out_path=regressions,
        receipts_path=tmp_path / "receipts.jsonl",
        write_receipt=False,
    )
    second = H.freeze_failures_to_regression(
        verdicts_path=verdicts,
        out_path=regressions,
        receipts_path=tmp_path / "receipts.jsonl",
        write_receipt=False,
    )

    assert first == 1
    assert second == 0
    assert len(_load_rows(regressions)) == 1


def test_refailing_frozen_turn_reports_fail(tmp_path):
    verdicts = _write_jsonl(tmp_path / "eval_verdicts.jsonl", [_incorrect_verdict()])
    regressions = tmp_path / "cs153_regression_turns.jsonl"
    H.freeze_failures_to_regression(
        verdicts_path=verdicts,
        out_path=regressions,
        receipts_path=tmp_path / "receipts.jsonl",
        write_receipt=False,
    )

    report = H.run_regression_eval(
        regression_path=regressions,
        verdicts_path=verdicts,
        metrics_path=tmp_path / "metrics.jsonl",
        receipts_path=tmp_path / "receipts.jsonl",
        write_receipt=False,
    )

    assert report["passed"] == 0
    assert report["failed"] == 1
    assert report["turns"][0]["passed"] is False
    assert report["turns"][0]["detail"]["latest_verdict"] == "incorrect"


def test_corrected_frozen_turn_reports_pass(tmp_path):
    incorrect = _incorrect_verdict()
    corrected = dict(incorrect)
    corrected.update({
        "trace_id": "verdict-trace-2",
        "verdict": "correct",
        "failed_rubric_keys": [],
    })
    freeze_verdicts = _write_jsonl(tmp_path / "freeze_verdicts.jsonl", [incorrect])
    replay_verdicts = _write_jsonl(tmp_path / "eval_verdicts.jsonl", [incorrect, corrected])
    regressions = tmp_path / "cs153_regression_turns.jsonl"
    H.freeze_failures_to_regression(
        verdicts_path=freeze_verdicts,
        out_path=regressions,
        receipts_path=tmp_path / "receipts.jsonl",
        write_receipt=False,
    )

    report = H.run_regression_eval(
        regression_path=regressions,
        verdicts_path=replay_verdicts,
        metrics_path=tmp_path / "metrics.jsonl",
        receipts_path=tmp_path / "receipts.jsonl",
        write_receipt=False,
    )

    assert report["passed"] == 1
    assert report["failed"] == 0
    assert report["turns"][0]["passed"] is True


def test_core_ledgers_untouched_during_freeze_and_replay(tmp_path):
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
    ]
    before = {str(p): _line_count(p) for p in watch}
    verdicts = _write_jsonl(tmp_path / "eval_verdicts.jsonl", [_incorrect_verdict()])
    regressions = tmp_path / "cs153_regression_turns.jsonl"

    H.freeze_failures_to_regression(
        verdicts_path=verdicts,
        out_path=regressions,
        receipts_path=tmp_path / "receipts.jsonl",
        write_receipt=False,
    )
    H.run_regression_eval(
        regression_path=regressions,
        verdicts_path=verdicts,
        metrics_path=tmp_path / "metrics.jsonl",
        receipts_path=tmp_path / "receipts.jsonl",
        write_receipt=False,
    )

    after = {str(p): _line_count(p) for p in watch}
    delta = {k: after[k] - before[k] for k in before}
    assert all(v == 0 for v in delta.values()), f"Core ledgers contaminated during EVAL-5 run: {delta}"
