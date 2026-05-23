#!/usr/bin/env python3
"""Regression guard for Alice's ledger-first agent-arm recall path."""

from pathlib import Path
import json
import sys

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System import swarm_stigmergic_query_router as qr


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_agent_arm_query_reads_briefing_before_llm(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(qr, "_STATE", tmp_path)
    monkeypatch.setattr(qr, "_REPAIR_LOG", tmp_path / "repair_log.jsonl")
    _append_jsonl(
        tmp_path / "alice_agent_arm_briefings.jsonl",
        {
            "briefing_id": "brief-123",
            "topic": "Hermes Agent arm usage",
            "status": "HERMES_CONFIGURED_NOT_AUTONOMOUS",
            "arm_id": "hermes_agent",
        },
    )
    _append_jsonl(
        tmp_path / "agent_arm_receipts.jsonl",
        {
            "receipt_id": "receipt-456",
            "arm_id": "hermes_agent",
            "truth_label": "ALICE_HERMES_BRIEFING_RECEIPT",
        },
    )

    reply = qr.route_organ_query("Alice, what is Hermes and how do you use that new arm?")

    assert "I read my agent-arm ledgers before answering" in reply
    assert "Hermes is a candidate tool arm, not my identity" in reply
    assert "agent_arm_receipts.jsonl" in reply
    assert "brief-123" in reply
    assert "receipt-456" in reply
    assert "What is the tool" not in reply
    assert "provide more details" not in reply.casefold()
