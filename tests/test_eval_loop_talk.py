#!/usr/bin/env python3
"""Acceptance tests for EVAL-2 Talk-outcome golden turns + human verdicts."""

from __future__ import annotations

import json
from pathlib import Path

from System.swarm_eval_loop import load_golden_turns, run_talk_eval


GOLDEN = Path("data/eval/cs153_talk_turns.jsonl")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def _turns() -> list:
    return load_golden_turns(GOLDEN)


def test_talk_golden_has_sequential_real_local_refs():
    turns = _turns()
    assert len(turns) >= 10
    assert [t.turn_id for t in turns] == [f"t{i:02d}" for i in range(1, len(turns) + 1)]
    assert all(t.target == "talk_outcome" for t in turns)
    assert all(t.conversation_ref.startswith("alice_conversation.jsonl#event:") for t in turns)
    assert all("#hash:" in t.conversation_ref for t in turns)


def test_turn_without_verdict_is_unverifiable(tmp_path):
    report = run_talk_eval(
        golden_path=GOLDEN,
        verdicts_path=tmp_path / "empty_verdicts.jsonl",
        write_receipt=False,
    )

    assert report["unverifiable"] == len(_turns())
    assert report["passed"] == 0
    assert report["failed"] == 0
    assert all(t["status"] == "unverifiable" for t in report["turns"])


def test_verdict_pass_fail_and_effector_truth_gates(tmp_path):
    turns = _turns()
    verdicts = tmp_path / "eval_verdicts.jsonl"
    _write_jsonl(verdicts, [
        {
            "turn_id": turns[0].turn_id,
            "conversation_ref": turns[0].conversation_ref,
            "verdict": "correct",
            "failed_rubric_keys": [],
            "labeled_by": "GEORGE",
            "trace_id": "trace-good",
        },
        {
            "turn_id": turns[1].turn_id,
            "conversation_ref": turns[1].conversation_ref,
            "verdict": "incorrect",
            "failed_rubric_keys": ["answer_correct"],
            "labeled_by": "GEORGE",
            "trace_id": "trace-fail",
        },
        {
            "turn_id": turns[2].turn_id,
            "conversation_ref": turns[2].conversation_ref,
            "verdict": "correct",
            "failed_rubric_keys": [],
            "labeled_by": "GEORGE",
        },
        {
            "turn_id": turns[3].turn_id,
            "conversation_ref": turns[3].conversation_ref,
            "verdict": "correct",
            "failed_rubric_keys": [],
            "labeled_by": "AGENT",
            "trace_id": "trace-not-human",
        },
        {
            "turn_id": turns[4].turn_id,
            "conversation_ref": "alice_conversation.jsonl#event:wrong#hash:wrong",
            "verdict": "correct",
            "failed_rubric_keys": [],
            "labeled_by": "GEORGE",
            "trace_id": "trace-wrong-ref",
        },
    ])

    report = run_talk_eval(golden_path=GOLDEN, verdicts_path=verdicts, write_receipt=False)
    by_id = {row["turn_id"]: row for row in report["turns"]}

    assert report["passed"] == 1
    assert report["failed"] == 1
    assert report["unverifiable"] == len(turns) - 2
    assert by_id["t01"]["passed"] is True
    assert by_id["t02"]["passed"] is False
    assert by_id["t03"]["detail"]["reason"] == "missing verdict trace_id"
    assert by_id["t04"]["detail"]["reason"] == "verdict not labeled by required human"
    assert by_id["t05"]["detail"]["reason"] == "conversation_ref mismatch"


def test_talk_receipt_uses_eval_run_talk_and_injected_paths(tmp_path):
    turns = _turns()
    verdicts = tmp_path / "eval_verdicts.jsonl"
    receipts = tmp_path / "work_receipts.jsonl"
    metrics = tmp_path / "talk_metrics.jsonl"
    _write_jsonl(verdicts, [{
        "turn_id": turns[0].turn_id,
        "conversation_ref": turns[0].conversation_ref,
        "verdict": "correct",
        "failed_rubric_keys": [],
        "labeled_by": "GEORGE",
        "trace_id": "trace-good",
    }])

    report = run_talk_eval(
        golden_path=GOLDEN,
        verdicts_path=verdicts,
        metrics_path=metrics,
        receipts_path=receipts,
        write_receipt=True,
    )
    last = json.loads(receipts.read_text(encoding="utf-8").splitlines()[-1])

    assert report["work_type"] == "EVAL_RUN_TALK"
    assert last["work_type"] == "EVAL_RUN_TALK"
    assert last["verdicts_seen"] == 1
    assert last["unverifiable"] == len(turns) - 1
    assert last["metrics_path"] == str(metrics)


def test_core_ledgers_untouched_when_receipt_disabled(tmp_path):
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
    ]
    before = {str(p): (len(p.read_text(encoding="utf-8", errors="replace").splitlines()) if p.exists() else 0) for p in watch}

    _ = run_talk_eval(
        golden_path=GOLDEN,
        verdicts_path=tmp_path / "v.jsonl",
        receipts_path=tmp_path / "r.jsonl",
        metrics_path=tmp_path / "m.jsonl",
        write_receipt=False,
    )

    after = {str(p): (len(p.read_text(encoding="utf-8", errors="replace").splitlines()) if p.exists() else 0) for p in watch}
    delta = {k: after[k] - before[k] for k in before}
    assert all(v == 0 for v in delta.values()), f"Core ledgers contaminated: {delta}"
