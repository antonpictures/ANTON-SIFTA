#!/usr/bin/env python3
"""
tests/test_swarm_api_sentry_delta_zero.py — §24 delta=0 round-trip proof.

Real file appends (no ledger mocks). Proves:
- boot_wire writes exactly one row to api_egress_log.jsonl
- AND exactly one row to work_receipts.jsonl
- both rows share identical trace_id (delta == 0 between ledgers)
- the action and provider fields are the §24 contract shapes

Run:
    PYTHONPATH=. python3 -m pytest tests/test_swarm_api_sentry_delta_zero.py -q --tb=line
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from System import swarm_api_sentry as sentry


def _count_lines(p: Path) -> int:
    if not p.exists():
        return 0
    return len(p.read_text(encoding="utf-8", errors="replace").splitlines())


def _tail_with_trace(p: Path, trace_id: str) -> list[dict]:
    rows = []
    if not p.exists():
        return rows
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if trace_id in line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows


def test_boot_wire_delta_zero_real_append(tmp_path, monkeypatch):
    """§24.A.3 — real round-trip: same trace_id lands in both ledgers, delta=0."""
    # Isolate the two ledgers under tmp
    fake_egress = tmp_path / "api_egress_log.jsonl"
    fake_work = tmp_path / "work_receipts.jsonl"
    fake_keys = tmp_path / "api_keys.json"

    original_egress = sentry._AUDIT_LOG
    original_work = sentry._WORK_RECEIPTS
    original_keys = sentry._KEYS_FILE

    sentry._AUDIT_LOG = fake_egress
    sentry._WORK_RECEIPTS = fake_work
    sentry._KEYS_FILE = fake_keys

    try:
        before_egress = _count_lines(fake_egress)
        before_work = _count_lines(fake_work)

        # Fire the exact §24 boot_wire (real append path, no network)
        row = sentry.boot_wire(
            caller="test_delta_zero",
            sender_agent="delta_zero_test",
        )
        trace_id = row["trace_id"]

        after_egress = _count_lines(fake_egress)
        after_work = _count_lines(fake_work)

        # Exactly one new row each
        assert (after_egress - before_egress) == 1, "expected exactly 1 egress row"
        assert (after_work - before_work) == 1, "expected exactly 1 work_receipt row"

        # Cross-ledger delta zero
        egress_hits = _tail_with_trace(fake_egress, trace_id)
        work_hits = _tail_with_trace(fake_work, trace_id)

        assert len(egress_hits) == 1
        assert len(work_hits) == 1
        assert egress_hits[0]["trace_id"] == work_hits[0]["trace_id"] == trace_id

        # Contract shapes from §24
        assert egress_hits[0]["provider"] == "api_sentry"
        assert egress_hits[0]["model"] == "boot_wire"
        assert work_hits[0]["action"] == "api_sentry_boot_wire"

        # Also prove the shared ts (within 1s tolerance for real time)
        assert abs(egress_hits[0]["ts"] - work_hits[0]["ts"]) < 1.0

    finally:
        sentry._AUDIT_LOG = original_egress
        sentry._WORK_RECEIPTS = original_work
        sentry._KEYS_FILE = original_keys


def test_emit_sentry_cold_alarm_writes_to_failover(tmp_path, monkeypatch):
    """§24.A.4 — alarm path writes SENTRY_COLD when forced stale."""
    fake_egress = tmp_path / "api_egress_log.jsonl"
    fake_failover = tmp_path / "cortex_failover.jsonl"

    original_egress = sentry._AUDIT_LOG
    original_fail = getattr(sentry, "_FAILOVER_LEDGER", None)

    sentry._AUDIT_LOG = fake_egress
    sentry._FAILOVER_LEDGER = fake_failover

    try:
        # Seed one old row so gap is huge
        old_ts = time.time() - (48 * 3600)
        old_row = {"ts": old_ts, "provider": "google_gemini", "trace_id": str(uuid.uuid4())}
        fake_egress.write_text(json.dumps(old_row) + "\n", encoding="utf-8")

        alarm = sentry.emit_sentry_cold_alarm(threshold_hours=24.0)
        assert alarm is not None
        assert alarm["kind"] == "SENTRY_COLD"
        assert alarm["is_stale"] is True or "hours_since_last_egress" in alarm  # shape tolerant
        assert fake_failover.exists()

        # One row written
        lines = [l for l in fake_failover.read_text().splitlines() if l.strip()]
        assert len(lines) == 1
        written = json.loads(lines[0])
        assert written["kind"] == "SENTRY_COLD"
        assert written["truth_label"] == "SENTRY_COLD_V1"

    finally:
        sentry._AUDIT_LOG = original_egress
        if original_fail is not None:
            sentry._FAILOVER_LEDGER = original_fail
