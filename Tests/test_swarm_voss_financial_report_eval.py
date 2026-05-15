"""Tests for the fixture-only Voss financial-report eval harness."""
from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_voss_financial_report_eval import (  # noqa: E402
    EVAL_LEDGER_NAME,
    TRUTH_LABEL,
    analyze_trace,
    fixture_research_findings,
    fixture_task,
    instrument_research_turn,
    run_fixture_eval,
    run_write_turn,
)


def test_turn2_blocks_without_turn1_research_receipt(tmp_path):
    task = fixture_task()

    outcome = run_write_turn(task, "TSLA report without research.", state_dir=tmp_path)

    assert outcome.ok is False
    assert outcome.reason == "missing_turn1_research_receipt"
    assert outcome.row["status"] == "TURN2_BLOCKED_MISSING_TURN1"
    assert outcome.row["truth_class"] == "FORBIDDEN"
    assert outcome.row["code_eval"]["checks"]["turn1_receipt_present"] is False


def test_turn1_research_receipt_allows_sourced_turn2(tmp_path):
    task = fixture_task()
    turn1 = instrument_research_turn(task, fixture_research_findings(), state_dir=tmp_path)

    outcome = run_write_turn(
        task,
        "TSLA robotaxi margin risk uses fixture:tesla_ir_2026q1 as evidence.",
        state_dir=tmp_path,
    )

    assert turn1.ok is True
    assert outcome.ok is True
    assert outcome.row["status"] == "TURN2_WRITE_ALLOWED"
    assert outcome.row["truth_class"] == "OBSERVED"
    assert outcome.row["parent_research_trace_id"] == turn1.row["trace_id"]
    assert outcome.row["code_eval"]["checks"]["turn1_receipt_present"] is True


def test_wrong_task_receipt_does_not_authorize_turn2(tmp_path):
    other_task = fixture_task()
    requested_task = type(other_task)(ticker="AAPL", focus=other_task.focus, as_of=other_task.as_of)
    instrument_research_turn(other_task, fixture_research_findings(), state_dir=tmp_path)

    outcome = run_write_turn(
        requested_task,
        "AAPL report with fixture:tesla_ir_2026q1 evidence.",
        state_dir=tmp_path,
    )

    assert outcome.ok is False
    assert outcome.row["status"] == "TURN2_BLOCKED_MISSING_TURN1"
    assert outcome.row["parent_research_trace_id"] is None


def test_dual_judge_rows_are_present_on_both_turns(tmp_path):
    task = fixture_task()
    instrument_research_turn(task, fixture_research_findings(), state_dir=tmp_path)
    run_write_turn(
        task,
        "TSLA report cites fixture:analyst_consensus_2026.",
        state_dir=tmp_path,
    )

    rows = [
        json.loads(line)
        for line in (tmp_path / EVAL_LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 2
    for row in rows:
        assert row["truth_label"] == TRUTH_LABEL
        assert "code_eval" in row
        assert "judge_eval" in row
        assert "sha256" in row


def test_analyze_trace_confirms_all_allowed_turn2_are_receipt_gated(tmp_path):
    task = fixture_task()
    run_write_turn(task, "blocked first", state_dir=tmp_path)
    instrument_research_turn(task, fixture_research_findings(), state_dir=tmp_path)
    run_write_turn(task, "TSLA report cites fixture:tesla_ir_2026q1.", state_dir=tmp_path)
    rows = [
        json.loads(line)
        for line in (tmp_path / EVAL_LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]

    summary = analyze_trace(rows)

    assert summary["rows"] == 3
    assert summary["turn2_attempts"] == 2
    assert summary["blocked_missing_turn1"] == 1
    assert summary["all_turn2_receipt_gated"] is True


def test_fixture_eval_blocked_scenario_returns_promptfoo_visible_status(tmp_path):
    report = run_fixture_eval(state_dir=tmp_path, scenario="blocked_without_turn1")

    assert report["status"] == "TURN2_BLOCKED_MISSING_TURN1"
    assert report["ok"] is False


def test_fixture_eval_allowed_scenario_returns_promptfoo_visible_status(tmp_path):
    report = run_fixture_eval(state_dir=tmp_path, scenario="allowed_with_turn1")

    assert report["status"] == "TURN2_WRITE_ALLOWED"
    assert report["ok"] is True


def test_cli_runs_fixture_without_network(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "System.swarm_voss_financial_report_eval",
            "--scenario",
            "blocked_without_turn1",
            "--state-dir",
            str(tmp_path),
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "TURN2_BLOCKED_MISSING_TURN1" in result.stdout


def test_promptfoo_fixture_row_blocks_turn2_without_turn1():
    repo_root = Path(__file__).resolve().parent.parent
    cfg = repo_root / "tests" / "voss_financial_report_eval" / "promptfooconfig.yaml"
    body = cfg.read_text(encoding="utf-8")

    assert "blocked_without_turn1" in body
    assert "TURN2_BLOCKED_MISSING_TURN1" in body
    assert "not-icontains" in body
    assert "TURN2_WRITE_ALLOWED" in body
    assert "file://sifta_voss_provider.py" in body


def test_promptfoo_provider_is_local_and_returns_block_status():
    repo_root = Path(__file__).resolve().parent.parent
    provider_path = repo_root / "tests" / "voss_financial_report_eval" / "sifta_voss_provider.py"
    spec = importlib.util.spec_from_file_location("sifta_voss_provider", provider_path)
    assert spec and spec.loader
    provider = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provider)

    result = provider.call_api("blocked_without_turn1", {}, {})

    assert result["output"].startswith("TURN2_BLOCKED_MISSING_TURN1")
    assert "SIFTA_VOSS_FINANCIAL_REPORT_EVAL_V1" in result["output"]
