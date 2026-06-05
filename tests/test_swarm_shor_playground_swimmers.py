#!/usr/bin/env python3
from pathlib import Path

from System.swarm_shor_playground_swimmers import (
    analyze_shor_playground_script,
    format_shor_playground_swimmers,
    send_shor_playground_swimmers,
)


def test_shor_script_analysis_says_15_passes_guard():
    row = analyze_shor_playground_script(n=15, vector_size=16)

    assert row["guard_expression"] == "N < 15"
    assert row["passes_guard"] is True
    assert row["n15_is_invalid"] is False
    assert row["width"] == 4
    assert row["twidth"] == 11


def test_shor_swimmers_factor_15_and_write_receipt(tmp_path: Path):
    row = send_shor_playground_swimmers(state_dir=tmp_path, write_receipt=True)

    assert row["truth_label"] == "SHOR_PLAYGROUND_SWIMMER_V1"
    assert row["success"] is True
    assert {3, 5}.issubset(set(row["factors"]))
    assert row["script_analysis"]["passes_guard"] is True
    assert "not a browser VM execution" in row["claim_boundary"]
    ledger = tmp_path / "shor_playground_swimmers.jsonl"
    assert ledger.exists()
    assert "shor_playground_swimmer_experiment" in ledger.read_text(encoding="utf-8")


def test_shor_format_contains_truth_boundary(tmp_path: Path):
    send_shor_playground_swimmers(state_dir=tmp_path, write_receipt=True)

    line = format_shor_playground_swimmers(state_dir=tmp_path)

    assert "Shor Playground swimmers" in line
    assert "passes_guard=True" in line
    assert "factors=[3, 5]" in line
    assert "local_proxy_not_qpu" in line
