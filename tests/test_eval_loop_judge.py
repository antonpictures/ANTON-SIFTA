#!/usr/bin/env python3
"""Acceptance tests for EVAL-4 (local on-device LLM-as-judge)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import System.swarm_eval_loop as H
import System.eval_local_judge as J
from System.eval_local_judge import get_local_gemma_judge


def _write_golden(path: Path, turns: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"truth_label": "CS153_JUDGE_TEST_V1"}) + "\n")
        for turn in turns:
            f.write(json.dumps(turn, sort_keys=True) + "\n")
    return path


def _free_text_turn(turn_id: str = "j01") -> dict:
    return {
        "turn_id": turn_id,
        "target": "free_text_judge",
        "prompt": "Answer with grounded receipt language.",
        "response": "I checked the local receipt and found the action is unverified.",
        "expected": "No hallucinated action claim.",
        "expect": {"min_score": 0.8},
        "rubric": {"grounding": "must refuse unreceipted action claims"},
    }


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def test_use_judge_false_never_calls_judge(tmp_path):
    golden = _write_golden(tmp_path / "judge.jsonl", [_free_text_turn()])
    fake_judge = MagicMock(return_value={"score": 1.0})

    report = H.run_eval_pack(
        golden_path=golden,
        metrics_path=tmp_path / "m.jsonl",
        receipts_path=tmp_path / "r.jsonl",
        use_judge=False,
        judge_fn=fake_judge,
        write_receipt=False,
    )

    fake_judge.assert_not_called()
    assert report["passed"] == 0
    assert report["failed"] == 0
    assert report["unverifiable"] == 1
    assert report["turns"][0]["status"] == "unverifiable"
    assert report["turns"][0]["judge_used"] is False


def test_local_judge_is_used_for_free_text_when_enabled(tmp_path):
    golden = _write_golden(tmp_path / "judge.jsonl", [_free_text_turn()])
    fake_judge = MagicMock(return_value={"score": 0.91, "reason": "local gemma"})

    report = H.run_eval_pack(
        golden_path=golden,
        metrics_path=tmp_path / "m.jsonl",
        receipts_path=tmp_path / "r.jsonl",
        use_judge=True,
        judge_fn=fake_judge,
        write_receipt=False,
    )

    fake_judge.assert_called_once()
    assert report["passed"] == 1
    assert report["failed"] == 0
    assert report["unverifiable"] == 0
    turn = report["turns"][0]
    assert turn["status"] == "judge"
    assert turn["judge_used"] is True
    assert turn["detail"]["deterministic"] is False


def test_unavailable_local_judge_makes_turn_unverifiable(tmp_path):
    golden = _write_golden(tmp_path / "judge.jsonl", [_free_text_turn()])

    report = H.run_eval_pack(
        golden_path=golden,
        metrics_path=tmp_path / "m.jsonl",
        receipts_path=tmp_path / "r.jsonl",
        use_judge=True,
        judge_fn=lambda text, context: {
            "score": 0.0,
            "passed": False,
            "judge_used": False,
            "reason": "local judge unavailable",
        },
        write_receipt=False,
    )

    assert report["passed"] == 0
    assert report["failed"] == 0
    assert report["unverifiable"] == 1
    assert report["turns"][0]["status"] == "unverifiable"
    assert report["turns"][0]["judge_used"] is False


def test_deterministic_turns_do_not_call_judge_when_enabled(tmp_path):
    fake_judge = MagicMock(return_value={"score": 0.0})

    report = H.run_eval_pack(
        golden_path=Path("data/eval/cs153_golden_turns.jsonl"),
        metrics_path=tmp_path / "m.jsonl",
        receipts_path=tmp_path / "r.jsonl",
        use_judge=True,
        judge_fn=fake_judge,
        write_receipt=False,
    )

    fake_judge.assert_not_called()
    assert report["passed"] == 13
    assert report["failed"] == 0
    assert report["unverifiable"] == 0
    assert not any(t.get("judge_used") for t in report["turns"])


def test_local_judge_errors_surface(tmp_path):
    golden = _write_golden(tmp_path / "judge.jsonl", [_free_text_turn()])

    def broken_judge(text, context):
        raise RuntimeError("local judge crashed")

    with pytest.raises(RuntimeError, match="local judge crashed"):
        H.run_eval_pack(
            golden_path=golden,
            metrics_path=tmp_path / "m.jsonl",
            receipts_path=tmp_path / "r.jsonl",
            use_judge=True,
            judge_fn=broken_judge,
            write_receipt=False,
        )


def test_cloud_endpoint_rejected():
    with pytest.raises(ValueError, match="localhost-only"):
        H.make_local_ollama_judge(
            "gemma",
            endpoint="https://api.openai.com/v1/chat/completions",
        )


def test_ollama_model_probe_is_local_and_exact(monkeypatch):
    class Result:
        returncode = 0
        stdout = "NAME ID SIZE MODIFIED\ngemma:2b abc 1GB now\n"

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return Result()

    monkeypatch.setattr(J.subprocess, "run", fake_run)

    assert J._ollama_model_available("gemma:2b") is True
    assert calls == [["ollama", "list"]]


def test_run_talk_eval_routes_free_text_to_judge(tmp_path):
    golden = _write_golden(tmp_path / "talk_judge.jsonl", [_free_text_turn("tj01")])
    fake_judge = MagicMock(return_value={"score": 0.82, "reason": "local"})

    report = H.run_talk_eval(
        golden_path=golden,
        verdicts_path=tmp_path / "missing_verdicts.jsonl",
        metrics_path=tmp_path / "m.jsonl",
        receipts_path=tmp_path / "r.jsonl",
        use_judge=True,
        judge_fn=fake_judge,
        write_receipt=False,
    )

    fake_judge.assert_called_once()
    assert report["passed"] == 1
    assert report["failed"] == 0
    assert report["unverifiable"] == 0
    assert report["turns"][0]["status"] == "judge"


def test_core_ledgers_untouched_during_judge_runs(tmp_path):
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
    ]
    before = {str(p): _line_count(p) for p in watch}
    golden = _write_golden(tmp_path / "judge.jsonl", [_free_text_turn()])

    def local_judge(text, context):
        return {"score": 0.85, "reason": "local only"}

    _ = H.run_eval_pack(
        golden_path=golden,
        metrics_path=tmp_path / "m.jsonl",
        receipts_path=tmp_path / "r.jsonl",
        use_judge=True,
        judge_fn=local_judge,
        write_receipt=False,
    )

    after = {str(p): _line_count(p) for p in watch}
    delta = {k: after[k] - before[k] for k in before}
    assert all(v == 0 for v in delta.values()), f"Core ledgers contaminated during judge run: {delta}"
