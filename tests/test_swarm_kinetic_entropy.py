#!/usr/bin/env python3
"""Tests for swarm_kinetic_entropy — kinetic-entropy proprioceptive sense (tranche 2 organ 4/12).

Upgraded contract: zero delta on core 4 + the organ's own output ledger
(kinetic_entropy_field.jsonl).

Focus: sense(), recent(), summarize(), and the core perception/actuation cycle
under full isolation. No long-running loops; bounded and deterministic.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from System import swarm_kinetic_entropy as ke


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def test_sense_writes_one_row_to_isolated_ledger(tmp_path):
    """Real behavior 1: sense() produces a well-formed packet and writes exactly one row."""
    target = tmp_path / "kinetic_entropy_field.jsonl"
    before = _count_lines(target)

    packet = ke.sense(node_density=4, source="test", ledger=target)

    after = _count_lines(target)
    assert (after - before) == 1

    assert isinstance(packet, dict)
    assert "terrain_map" in packet
    assert "motor_dilation_s" in packet
    assert 0.10 <= packet["motor_dilation_s"] <= 15.0
    assert packet["source"] == "test"


def test_recent_reads_back_isolated_rows(tmp_path):
    """Real behavior 2: recent() returns the rows that were just written under isolation."""
    target = tmp_path / "kinetic_entropy_field.jsonl"

    p1 = ke.sense(node_density=4, source="t1", ledger=target)
    p2 = ke.sense(node_density=4, source="t2", ledger=target)

    rows = ke.recent(n=5, ledger=target)
    assert len(rows) >= 2
    assert rows[-1]["source"] == "t2"
    assert rows[-2]["source"] == "t1"


def test_summarize_is_deterministic_and_safe():
    """Summary surface works on any valid packet and never crashes."""
    packet = {
        "ts": 1234567890.0,
        "density": 0.55,
        "motor_dilation_s": 1.23,
        "entropy_fingerprint": "abc123def456",
        "node_density": 8,
    }
    summary = ke.summarize(packet)
    assert isinstance(summary, str)
    assert len(summary) > 0

    # Empty packet edge
    empty_summary = ke.summarize({})
    assert isinstance(empty_summary, str)


def test_real_ledgers_untouched_including_organ_own(tmp_path, monkeypatch):
    """Explicit isolation gate (core 4 + organ own kinetic_entropy_field.jsonl)."""
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
        state / "kinetic_entropy_field.jsonl",
    ]
    before = {str(p): _count_lines(p) for p in watch}

    target = tmp_path / "kinetic_entropy_field.jsonl"

    # Run a few bounded operations under the redirected ledger
    ke.sense(node_density=4, source="isolation_a", ledger=target)
    ke.sense(node_density=4, source="isolation_b", ledger=target)
    rows = ke.recent(n=10, ledger=target)
    _ = ke.summarize(rows[0] if rows else {})

    after = {str(p): _count_lines(p) for p in watch}
    delta = {k: after[k] - before[k] for k in before}

    assert all(v == 0 for v in delta.values()), f"Real ledgers (incl. organ own) contaminated: {delta}"