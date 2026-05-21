#!/usr/bin/env python3
"""Tests for the exterior-to-interior organism health eval."""

from __future__ import annotations

import json
from pathlib import Path

import System.swarm_organism_health_eval as health
from System.swarm_organism_health_eval import cross_check, run_health_eval


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _seed_state(root: Path) -> Path:
    state = root / "state"
    _append(
        state / "ide_stigmergic_trace.jsonl",
        {
            "ts": 1.0,
            "trace_id": "reg1",
            "action": "LLM_REGISTRATION",
            "doctor": "Codex desktop",
        },
    )
    _append(
        state / "work_receipts.jsonl",
        {
            "ts": 2.0,
            "receipt_id": "receipt1",
            "agent_id": "IDE_DOCTOR_CODEX_GPT_5_CODEX",
            "work_type": "VERIFICATION",
        },
    )
    _append(
        state / "memory_ledger.jsonl",
        {
            "trace_id": "mem1",
            "architect_id": "IOAN_M5",
            "app_context": "talk_to_alice",
            "raw_text": "real launch Tuesday",
            "epistemic_label": "OBSERVED",
            "links": ["trace_id:reg1"],
        },
    )
    _append(state / "execution_traces.jsonl", {"trace_id": "exec1", "ok": True})
    return state


def _run_tmp(state: Path, tmp_path: Path):
    return run_health_eval(
        state_dir=state,
        metrics_path=tmp_path / "out" / "organism_health_metrics.jsonl",
        receipts_path=tmp_path / "out" / "work_receipts.jsonl",
        report_path=tmp_path / "out" / "health_report.json",
    )


def test_run_health_eval_returns_all_vitals(tmp_path):
    state = _seed_state(tmp_path)
    report = _run_tmp(state, tmp_path)

    assert set(report["vitals"]) == {
        "receipt_chain",
        "ledger_integrity",
        "epistemic_hygiene",
        "organ_static_health",
        "coverage",
        "fiction_leak",
    }
    assert 0 <= report["overall_score"] <= 1
    assert report["read_only_ok"] is True
    assert all(0 <= vital["score"] <= 1 for vital in report["vitals"].values())


def test_orphan_links_are_detected(tmp_path):
    state = _seed_state(tmp_path)
    _append(
        state / "memory_ledger.jsonl",
        {
            "trace_id": "mem_orphan",
            "architect_id": "IOAN_M5",
            "app_context": "talk_to_alice",
            "raw_text": "orphan evidence claim",
            "epistemic_label": "OBSERVED",
            "links": ["trace_id:missing", "receipt:work_receipts.jsonl#missing"],
        },
    )

    report = _run_tmp(state, tmp_path)
    assert report["vitals"]["ledger_integrity"]["orphan_links"] >= 2


def test_unlabeled_fiction_contamination_is_flagged(tmp_path):
    state = _seed_state(tmp_path)
    _append(
        state / "memory_ledger.jsonl",
        {
            "trace_id": "leak1",
            "architect_id": "IOAN_M5",
            "app_context": "talk_to_alice",
            "raw_text": "dragon attacks Tuesday",
        },
    )

    report = _run_tmp(state, tmp_path)
    assert report["vitals"]["epistemic_hygiene"]["contamination_flags"] >= 1


def test_run_health_eval_does_not_mutate_live_ledgers(tmp_path):
    paths = health._state_paths(health._STATE)
    before = {name: health._line_count(path) for name, path in paths.items()}
    run_health_eval(
        state_dir=health._STATE,
        metrics_path=tmp_path / "metrics.jsonl",
        receipts_path=tmp_path / "receipts.jsonl",
        report_path=tmp_path / "health_report.json",
    )
    after = {name: health._line_count(path) for name, path in paths.items()}
    assert after == before


def test_health_receipt_and_report_are_written(tmp_path):
    state = _seed_state(tmp_path)
    metrics = tmp_path / "out" / "metrics.jsonl"
    receipts = tmp_path / "out" / "receipts.jsonl"
    report_path = tmp_path / "out" / "health_report.json"

    report = run_health_eval(
        state_dir=state,
        metrics_path=metrics,
        receipts_path=receipts,
        report_path=report_path,
    )

    assert report_path.exists()
    assert "source_hash" in json.loads(report_path.read_text())
    receipt = json.loads(receipts.read_text().splitlines()[-1])
    assert receipt["work_type"] == "HEALTH_EVAL_RUN"
    assert receipt["trace_id"] == report["health_receipt_id"]
    assert metrics.exists()


def test_cross_check_agreement_and_dispute():
    interior_ok = {"pass_rate": 1.0}
    exterior_ok = {"read_only_ok": True, "vitals": {"fiction_leak": {"score": 1.0}}}
    assert cross_check(interior_ok, exterior_ok)["agreement"] is True

    exterior_bad = {"read_only_ok": True, "vitals": {"fiction_leak": {"score": 0.0}}}
    disputed = cross_check(interior_ok, exterior_bad)
    assert disputed["agreement"] is False
    assert disputed["findings"]
