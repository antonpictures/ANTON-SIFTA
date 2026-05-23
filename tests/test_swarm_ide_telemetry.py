from __future__ import annotations

import json
from pathlib import Path

from System.swarm_ide_cost_ledger import IDECostSample, append_sample
from System.swarm_ide_telemetry import (
    emit_summary_trace,
    summarize_cost_rows,
    summary_for_alice,
)


def _write_sample(ledger: Path, **overrides):
    data = {
        "surface": "cursor",
        "agent_id": "C47H",
        "model_label": "claude-opus-4-7-thinking-high",
        "plan_name": "Ultra $200/mo",
        "source_unit": "tokens",
        "observed_quantity": 70_000_000.0,
        "evidence_kind": "dashboard_screenshot",
        "evidence_ref": "screenshot:test",
        "stigauth_status": "STIGAUTH_ACTIVE",
    }
    data.update(overrides)
    return append_sample(IDECostSample(**data), ledger_path=ledger)


def test_summary_preserves_native_units_without_normalizing(tmp_path: Path):
    ledger = tmp_path / "ide_cost_ledger.jsonl"
    _write_sample(ledger)
    _write_sample(
        ledger,
        surface="codex",
        agent_id="C55M",
        model_label="gpt-5.4-medium",
        plan_name="Codex weekly",
        source_unit="percent_quota",
        observed_quantity=10.0,
    )

    rows = [
        json.loads(line)
        for line in ledger.read_text().splitlines()
        if line.strip()
    ]
    summary = summarize_cost_rows(rows)

    assert summary["sample_count"] == 2
    assert summary["by_surface"]["cursor"]["units"] == {"tokens": 70_000_000.0}
    assert summary["by_surface"]["codex"]["units"] == {"percent_quota": 10.0}


def test_summary_for_alice_states_boundary(tmp_path: Path):
    ledger = tmp_path / "ide_cost_ledger.jsonl"
    _write_sample(ledger)

    block = summary_for_alice(ledger_path=ledger, max_age_s=None)

    assert "IDE METABOLISM" in block
    assert "70,000,000 tokens" in block
    assert "not vendor-normalized" in block
    assert "not a unified exchange rate" in block


def test_empty_summary_is_silent(tmp_path: Path):
    assert summary_for_alice(ledger_path=tmp_path / "missing.jsonl") == ""


def test_emit_summary_trace_writes_pheromone_row(tmp_path: Path):
    ledger = tmp_path / "ide_cost_ledger.jsonl"
    trace = tmp_path / "ide_stigmergic_trace.jsonl"
    _write_sample(ledger)

    row = emit_summary_trace(
        ledger_path=ledger,
        trace_path=trace,
        source_ide="C55M",
        homeworld_serial="TEST_SERIAL",
        max_age_s=None,
    )

    rows = [
        json.loads(line)
        for line in trace.read_text().splitlines()
        if line.strip()
    ]
    assert rows == [row]
    assert rows[0]["kind"] == "ide_metabolism_summary"
    assert rows[0]["meta"]["sample_count"] == 1
    assert "70,000,000 tokens" in rows[0]["payload"]
