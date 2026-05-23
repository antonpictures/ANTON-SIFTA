#!/usr/bin/env python3
"""
tests/test_eval_loop.py — Gates for the EVAL loop (Slice EVAL)

Cowork runs these after Grok delivers.
Codex then re-verifies.
"""

import json
import time
from pathlib import Path

import pytest

import System.swarm_eval_loop as loop
from System.swarm_eval_loop import run_eval_pack


GOLDEN = Path("data/eval/cs153_golden_turns.jsonl")


@pytest.fixture(autouse=True)
def isolated_eval_ledgers(tmp_path, monkeypatch):
    monkeypatch.setattr(loop, "_METRICS", tmp_path / "skill_invoke_metrics.jsonl")
    monkeypatch.setattr(loop, "_RECEIPTS", tmp_path / "work_receipts.jsonl")


def test_run_eval_pack_returns_report_structure():
    report = run_eval_pack(golden_path=GOLDEN, use_judge=False)
    assert "pass_rate" in report
    assert "passed" in report and "failed" in report
    assert "turns" in report and isinstance(report["turns"], list)
    assert "golden_hash" in report
    assert report["use_judge"] is False


def test_fiction_exclusion_gate():
    # g03 explicitly tests fiction exclusion
    report = run_eval_pack(golden_path=GOLDEN, use_judge=False)
    g03 = next(t for t in report["turns"] if t["turn_id"] == "g03")
    assert g03["passed"] is True, "FICTION exclusion must pass"


def test_loop_can_fail():
    # Temporarily corrupt one expectation so the turn must fail
    bad_golden = Path("/tmp/cs153_bad_golden.jsonl")
    data = GOLDEN.read_text()
    # Change g01 to expect something impossible.
    data = data.replace(
        '"must_include_substring":"Tuesday"',
        '"must_include_substring":"IMPOSSIBLE_STRING_999"',
        1,
    )
    bad_golden.write_text(data)

    report = run_eval_pack(golden_path=bad_golden, use_judge=False)
    bad_turn = next(t for t in report["turns"] if t["turn_id"] == "g01")
    assert bad_turn["passed"] is False, "Loop must be able to report FAIL"
    bad_golden.unlink()


def test_metrics_rows_written():
    run_eval_pack(golden_path=GOLDEN, use_judge=False)
    assert loop._METRICS.exists()
    rows = [json.loads(l) for l in loop._METRICS.read_text().splitlines() if l.strip()]
    assert len(rows) >= 10
    assert all("turn_id" in r and "trace_id" in r for r in rows[-10:])


def test_no_network_when_use_judge_false(monkeypatch):
    called = []
    def fake_judge(*a, **k):
        called.append(True)
        return "fake"
    # Even if someone tries to call a judge, it should not be invoked
    report = run_eval_pack(golden_path=GOLDEN, use_judge=False)
    assert not called, "No judge should be called when use_judge=False"


def test_empty_result_gate_is_not_trivial():
    report = run_eval_pack(golden_path=GOLDEN, use_judge=False)
    g05 = next(t for t in report["turns"] if t["turn_id"] == "g05")
    assert g05["passed"] is True
    assert g05["detail"]["empty_ok"] is True


def test_golden_hash_changes_when_file_mutated(tmp_path):
    copy = tmp_path / "copy.jsonl"
    copy.write_bytes(GOLDEN.read_bytes())
    r1 = run_eval_pack(golden_path=copy, use_judge=False)
    # Mutate
    data = copy.read_text()
    copy.write_text(data.replace("Tuesday", "Wednesday"))
    r2 = run_eval_pack(golden_path=copy, use_judge=False)
    assert r1["golden_hash"] != r2["golden_hash"]


def test_eval_run_receipt_written():
    report = run_eval_pack(golden_path=GOLDEN, use_judge=False)
    assert "eval_receipt_id" in report
    # Last receipt should be EVAL_RUN
    last = json.loads(loop._RECEIPTS.read_text().splitlines()[-1])
    assert last["work_type"] == "EVAL_RUN"
    assert last["pass_rate"] == report["pass_rate"]
