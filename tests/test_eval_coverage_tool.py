#!/usr/bin/env python3
"""Acceptance tests for EVAL-6 coverage/dashboard tooling."""

from __future__ import annotations

import json
from pathlib import Path

import tools.eval_coverage as C


def test_parse_trace_cover_text_counts_real_markers():
    text = """\
    1: import json
>>>>>> missing_call()
   12: executed_call()
plain comment
"""
    report = C.parse_trace_cover_text(text)
    assert report["executed_lines"] == 2
    assert report["missing_lines"] == 1
    assert report["total_lines"] == 3
    assert report["percent"] == 66.67


def test_coverage_gate_runs_real_trace_on_eval_loop():
    report = C.run_coverage_gate(
        tests=["tests/test_eval_loop_judge.py"],
        threshold=1.0,
    )
    assert report["tool"] == "stdlib_trace"
    assert report["pytest_returncode"] == 0
    assert report["tests_passed"] >= 7
    assert report["executed_lines"] > 0
    assert report["total_lines"] > 0
    assert report["percent"] > 1.0
    assert report["ok"] is True


def test_dashboard_row_uses_real_shape_and_appends(tmp_path):
    report = {
        "tests_passed": 37,
        "percent": 84.38,
        "ok": True,
        "tool": "stdlib_trace",
    }
    row = C.build_dashboard_row(report)
    path = tmp_path / "company_dashboard.jsonl"
    C.append_dashboard_row(row, path)

    saved = json.loads(path.read_text(encoding="utf-8").strip())
    assert saved["tests_passed"] == 37
    assert saved["coverage_percent"] == 84.38
    assert saved["coverage_ok"] is True
    assert isinstance(saved["commits"], int)
    assert isinstance(saved["eval_pass_rate"], float)
    assert isinstance(saved["stgm_burn"], float)


def test_organ_coverage_gate_writes_canonical_rows(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "visual_stigmergy.jsonl").write_text('{"ts": 1, "event": "FRAME", "ok": true}\n', encoding="utf-8")

    report = C.run_organ_coverage_gate(
        state_dir=state,
        max_age_days=999999,
        out_path=tmp_path / "organ_coverage.jsonl",
        write_receipt=True,
    )
    rows = [
        json.loads(line)
        for line in (tmp_path / "organ_coverage.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    vision = next(row for row in rows if row["organ_id"] == "vision_lane")

    assert report["canonical_organs"] == 13
    assert len(rows) == 13
    assert vision["ledger_exists"] is True
    assert vision["fresh_ledger"] is True
    assert vision["outcome_bearing_row"] is True


def test_main_writes_dashboard_to_requested_path(tmp_path, capsys):
    dashboard = tmp_path / "dashboard.jsonl"
    code = C.main([
        "--threshold",
        "1.0",
        "--dashboard-path",
        str(dashboard),
        "--append-dashboard",
        "tests/test_eval_loop_judge.py",
    ])

    assert code == 0
    assert dashboard.exists()
    payload = json.loads(capsys.readouterr().out)
    assert payload["coverage"]["tests_passed"] >= 7
    assert payload["dashboard_path"] == str(dashboard)
