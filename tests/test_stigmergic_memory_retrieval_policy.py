#!/usr/bin/env python3
"""Tests for bounded, receipt-aware stigmergic memory retrieval."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System.swarm_stigmergic_memory_retrieval_policy import (
    rank_stigmergic_memory,
    render_stigmergic_memory_retrieval_block,
)


def _append(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def test_rank_stigmergic_memory_prefers_receipted_matching_rows(tmp_path):
    state = tmp_path / ".sifta_state"
    now = 1_000_000.0
    _append(
        state / "ide_stigmergic_trace.jsonl",
        {
            "ts": now - 120,
            "summary": "MiMo swimmer self evolution changed body inventory",
            "truth_label": "OPERATIONAL",
            "receipt_id": "r-good",
            "round_id": "r-test",
            "tests_green": "1 passed",
            "files_touched": ["System/example.py"],
            "source_ide": "codex",
            "action_oracle_signature": "abc123",
        },
    )
    _append(
        state / "ide_stigmergic_trace.jsonl",
        {
            "ts": now - 60,
            "summary": "MiMo self evolution idea but no receipt evidence",
        },
    )
    _append(
        state / "work_receipts.jsonl",
        {
            "ts": now - 30,
            "summary": "unrelated weather note",
            "truth_label": "OBSERVED",
            "receipt_id": "r-other",
        },
    )

    hits = rank_stigmergic_memory(
        "mimo swimmer self evolution body inventory",
        state_dir=state,
        now=now,
        limit=3,
    )

    assert hits
    assert hits[0]["receipt_id"] == "r-good"
    assert hits[0]["round_id"] == "r-test"
    assert "tests_green" in hits[0]["reasons"]
    assert "files_touched" in hits[0]["reasons"]


def test_render_retrieval_block_is_bounded_not_unlimited(tmp_path):
    state = tmp_path / ".sifta_state"
    block = render_stigmergic_memory_retrieval_block("mimo context", state_dir=state)
    assert "not unlimited context" in block.lower()
    assert "no matching ledger rows" in block
