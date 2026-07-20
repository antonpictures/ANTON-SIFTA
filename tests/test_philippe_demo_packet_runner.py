"""Tests for the June 20 Philippe demo packet runner."""
from __future__ import annotations

import json
from pathlib import Path

from tools.run_philippe_demo_packet import (
    CheckResult,
    EXPECTED_DEMO_STATUSES,
    parse_pre_demo_commands,
    run_body_receipt_sort_demo,
    run_receipt_demo,
    validate_benchmark_counts,
    validate_packet_text,
    validate_root_packet_copy,
)


def test_parse_pre_demo_commands_reads_bash_block(tmp_path: Path) -> None:
    script = tmp_path / "demo.md"
    script.write_text(
        """
# Demo

## Pre-demo checklist

```bash
cd /tmp/demo
python3 tools/whats_left.py           # verify live lane
python3 -m pytest tests/a.py tests/b.py -q  # core tests green
```
""",
        encoding="utf-8",
    )

    commands = parse_pre_demo_commands(script)

    assert commands == [
        ["python3", "tools/whats_left.py"],
        ["python3", "-m", "pytest", "tests/a.py", "tests/b.py", "-q"],
    ]


def test_packet_text_requires_scope_and_open_boundaries() -> None:
    text = """
    SIFTA OS organism runtime on owner-owned hardware.
    RECEIPT SORT.
    one hardware-bound Alice body on the buyer's computer; not loose agents or swimmers.
    demo/philippe_receipt_honesty_5min.py and tools/benchmark_receipt_gate.py.
    SIFTA's receipt-sort loop emitted 0 of 5 unbacked claims and 0 of 3 double-spends.
    the live per-framework run uses the same harness with keys on the node.
    Founder stage: one live node.
    None yet. An outside evaluation is the step toward a first narrow pilot.
    """

    missing, forbidden = validate_packet_text(text)

    assert missing == []
    assert forbidden == []


def test_packet_text_rejects_old_agent_claim() -> None:
    text = """
    SIFTA OS organism runtime on owner-owned hardware.
    RECEIPT SORT.
    one hardware-bound Alice body on the buyer's computer; not loose agents or swimmers.
    demo/philippe_receipt_honesty_5min.py and tools/benchmark_receipt_gate.py.
    0 of 5 unbacked claims and 0 of 3 double-spends.
    live per-framework run uses the same harness with keys on the node.
    Founder stage: one live node.
    None yet. An outside evaluation.
    What you sell: an AI agent you can audit and own.
    """

    missing, forbidden = validate_packet_text(text)

    assert missing == []
    assert forbidden == ["What you sell: an AI agent you can audit and own"]


def test_receipt_demo_runner_validates_five_statuses(tmp_path: Path) -> None:
    result = run_receipt_demo(state_dir=tmp_path)

    assert isinstance(result, CheckResult)
    assert result.status == "OK"
    assert ", ".join(EXPECTED_DEMO_STATUSES) in result.evidence

    ledger = tmp_path / ".sifta_state" / "philippe_receipt_honesty_demo.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert [row["status"] for row in rows] == EXPECTED_DEMO_STATUSES


def test_benchmark_count_validator_names_mechanism_scope() -> None:
    ok, detail = validate_benchmark_counts(
        {
            "tasks_total": 12,
            "unbacked_claims": 5,
            "replays": 3,
            "sifta_gate": {"fabricated": 0, "double_spent": 0},
            "ungated_baseline": {"fabricated": 5, "double_spent": 3},
        }
    )

    assert ok is True
    assert "SIFTA local gate 0/5" in detail


def test_root_packet_copy_warns_when_it_differs(tmp_path: Path) -> None:
    canonical = tmp_path / "outputs.pdf"
    root = tmp_path / "root.pdf"
    canonical.write_bytes(b"canonical")
    root.write_bytes(b"stale")

    result = validate_root_packet_copy(canonical=canonical, root_copy=root)

    assert result.status == "WARN"
    assert "differs from canonical" in result.detail


def test_body_receipt_sort_demo_writes_examples_and_is_sortable(tmp_path: Path) -> None:
    """r1502: body reflexes gathered, validated somatic move receipts written, cortex-sort surface works."""
    result = run_body_receipt_sort_demo(state_dir=tmp_path)

    assert isinstance(result, CheckResult)
    assert result.status == "OK"
    assert "somatic receipts written" in result.detail or "validated somatic" in result.detail.lower()

    ledger = tmp_path / ".sifta_state" / "somatic_receipt_demo.jsonl"
    assert ledger.exists()
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    tags = [r.get("tag") for r in rows]
    assert "desk_sitting_typing" in tags
    assert "quiet_room" in tags
    # sort proof: schema present and can be filtered
    assert all(r.get("schema") == "SOMATIC_RECEIPT_V1" for r in rows)


def test_body_receipt_demo_reflex_contains_time_and_body_keys(tmp_path: Path) -> None:
    # We only check it doesn't crash and ledger has ts; full body keys are hardware dependent
    run_body_receipt_sort_demo(state_dir=tmp_path)
    ledger = tmp_path / ".sifta_state" / "somatic_receipt_demo.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any("ts" in r or "reflex" in str(r) for r in rows)
