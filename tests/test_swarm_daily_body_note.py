#!/usr/bin/env python3
"""Tests for the self-query -> Writer body note cut."""
from __future__ import annotations

import json
from pathlib import Path

from System.swarm_daily_body_note import TRUTH_LABEL, write_daily_body_note


def test_write_daily_body_note_from_latest_self_query_report(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    report = {
        "kind": "SELF_QUERY_REPORT",
        "truth_label": "SIFTA_SELF_QUERY_SKILL_V1",
        "trace_id": "trace-123",
        "payload": {
            "trace_id": "trace-123",
            "ts": 1782220718.590622,
            "stgm_wallet_balance": 97.188,
            "stgm_recent_mints": 3,
            "organ_count": 7,
            "healthy_count": 5,
            "body_map_areas": [
                {
                    "status": "RED",
                    "name": "writer_documents",
                    "reason": "ledger silent 286h",
                },
                {
                    "status": "YELLOW",
                    "name": "owner correction signals",
                    "reason": "prioritize George's observed truth",
                },
            ],
            "needs": [
                "writer_documents: ledger silent 286h",
                "two_turn_receipt_gate: ledger silent 955h",
            ],
            "sha256": "abc",
        },
    }
    (state / "self_query_reports.jsonl").write_text(json.dumps(report) + "\n", encoding="utf-8")

    out = write_daily_body_note(root=tmp_path, state_dir=state, now=1782220800.0)

    assert out["ok"] is True
    path = Path(out["path"])
    assert path.name == "2026-06-23-body-note.sifta.md"
    text = path.read_text(encoding="utf-8")
    assert "Alice Body Note - 2026-06-23" in text
    assert "RED: writer_documents" in text
    assert "writer_documents: ledger silent 286h" in text
    assert TRUTH_LABEL in text

    rows = [
        json.loads(line)
        for line in (state / "writer_documents_receipts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[-1]["truth_label"] == TRUTH_LABEL
    assert rows[-1]["source_report_trace"] == "trace-123"
    assert rows[-1]["path"] == str(path)


def test_write_daily_body_note_refuses_without_report(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)

    out = write_daily_body_note(root=tmp_path, state_dir=state)

    assert out["ok"] is False
    assert out["reason"] == "no_self_query_report"
