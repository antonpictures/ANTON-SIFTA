"""Tests for the HYPOTHESIS TTL/decay helper.

These pin:
  - Rows older than ttl_seconds with truth_class HYPOTHESIS get
    demoted via a FORBIDDEN_STALE decay receipt.
  - Rows still within ttl_seconds are left alone.
  - OBSERVED / ARCHITECT_DOCTRINE rows are never decayed.
  - The decay ledger is append-only and parent_trace_id-linked.
  - Re-running the helper does not double-decay the same parent row.
  - decay_many runs across multiple ledgers and reports each.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_hypothesis_ttl_decay import (  # noqa: E402
    DEFAULT_TTL_SECONDS,
    DECAY_LEDGER,
    TRUTH_LABEL,
    decay_hypothesis_rows,
    decay_many,
)


def _write_rows(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


# ── core decay behaviour ──────────────────────────────────────────────────


def test_old_hypothesis_row_gets_decay_receipt(tmp_path):
    ledger = tmp_path / "fake.jsonl"
    now = time.time()
    old_ts = now - DEFAULT_TTL_SECONDS - 3600  # 1 hour past TTL
    _write_rows(ledger, [
        {"ts": old_ts, "trace_id": "old-hypothesis", "truth_class": "HYPOTHESIS", "kind": "TEST"},
    ])
    report = decay_hypothesis_rows(ledger, write=True, now=now)
    assert report.scanned == 1
    assert report.hypothesis_rows == 1
    assert report.expired_rows == 1
    decay_path = tmp_path / DECAY_LEDGER
    rows = [json.loads(ln) for ln in decay_path.read_text().splitlines() if ln.strip()]
    assert len(rows) == 1
    assert rows[0]["kind"] == "HYPOTHESIS_DECAYED"
    assert rows[0]["truth_class"] == "FORBIDDEN_STALE"
    assert rows[0]["parent_trace_id"] == "old-hypothesis"


def test_recent_hypothesis_row_not_decayed(tmp_path):
    ledger = tmp_path / "fake.jsonl"
    now = time.time()
    _write_rows(ledger, [
        {"ts": now - 60, "trace_id": "fresh-hypothesis", "truth_class": "HYPOTHESIS", "kind": "TEST"},
    ])
    report = decay_hypothesis_rows(ledger, write=True, now=now)
    assert report.scanned == 1
    assert report.hypothesis_rows == 1
    assert report.expired_rows == 0


def test_observed_rows_never_decayed(tmp_path):
    ledger = tmp_path / "fake.jsonl"
    now = time.time()
    old_ts = now - DEFAULT_TTL_SECONDS - 3600
    _write_rows(ledger, [
        {"ts": old_ts, "trace_id": "old-observed", "truth_class": "OBSERVED", "kind": "TEST"},
        {"ts": old_ts, "trace_id": "old-architect", "truth_class": "ARCHITECT_DOCTRINE", "kind": "TEST"},
    ])
    report = decay_hypothesis_rows(ledger, write=True, now=now)
    assert report.scanned == 2
    assert report.hypothesis_rows == 0
    assert report.expired_rows == 0
    assert not (tmp_path / DECAY_LEDGER).exists()


def test_decay_is_idempotent(tmp_path):
    """Re-running decay should not produce a second receipt for the
    same parent row."""
    ledger = tmp_path / "fake.jsonl"
    now = time.time()
    old_ts = now - DEFAULT_TTL_SECONDS - 3600
    _write_rows(ledger, [
        {"ts": old_ts, "trace_id": "x", "truth_class": "HYPOTHESIS", "kind": "TEST"},
    ])
    r1 = decay_hypothesis_rows(ledger, write=True, now=now)
    r2 = decay_hypothesis_rows(ledger, write=True, now=now)
    assert r1.expired_rows == 1
    assert r2.expired_rows == 0
    decay_path = tmp_path / DECAY_LEDGER
    rows = [json.loads(ln) for ln in decay_path.read_text().splitlines() if ln.strip()]
    assert len(rows) == 1


def test_truth_label_string_containing_hypothesis_also_qualifies(tmp_path):
    """Rows that use the older convention (truth_label="*_HYPOTHESIS")
    should also be detected — not only the §7.11 truth_class field."""
    ledger = tmp_path / "fake.jsonl"
    now = time.time()
    old_ts = now - DEFAULT_TTL_SECONDS - 3600
    _write_rows(ledger, [
        {"ts": old_ts, "trace_id": "legacy", "truth_label": "STIGMERGIC_HYPOTHESIS_V1", "kind": "TEST"},
    ])
    report = decay_hypothesis_rows(ledger, write=True, now=now)
    assert report.expired_rows == 1


def test_decay_receipt_records_parent_metadata(tmp_path):
    ledger = tmp_path / "fake.jsonl"
    now = time.time()
    old_ts = now - DEFAULT_TTL_SECONDS - 3600
    _write_rows(ledger, [
        {
            "ts": old_ts,
            "trace_id": "parent-trace",
            "truth_class": "HYPOTHESIS",
            "truth_label": "ORIGINAL_LABEL",
            "kind": "ORIGINAL_KIND",
        },
    ])
    decay_hypothesis_rows(ledger, write=True, now=now)
    rows = [json.loads(ln) for ln in (tmp_path / DECAY_LEDGER).read_text().splitlines() if ln.strip()]
    r = rows[0]
    assert r["parent_truth_label"] == "ORIGINAL_LABEL"
    assert r["parent_kind"] == "ORIGINAL_KIND"
    assert r["parent_ts"] == old_ts
    assert r["age_seconds"] > DEFAULT_TTL_SECONDS


def test_decay_many_runs_across_multiple_ledgers(tmp_path):
    now = time.time()
    old_ts = now - DEFAULT_TTL_SECONDS - 3600
    l1 = tmp_path / "a.jsonl"
    l2 = tmp_path / "b.jsonl"
    _write_rows(l1, [{"ts": old_ts, "trace_id": "h1", "truth_class": "HYPOTHESIS"}])
    _write_rows(l2, [{"ts": old_ts, "trace_id": "h2", "truth_class": "HYPOTHESIS"}])
    reports = decay_many([l1, l2], write=True)
    assert len(reports) == 2
    assert all(r.expired_rows == 1 for r in reports)


def test_short_ttl_decays_everything_old_enough(tmp_path):
    ledger = tmp_path / "fake.jsonl"
    now = time.time()
    _write_rows(ledger, [
        {"ts": now - 10, "trace_id": "h1", "truth_class": "HYPOTHESIS"},
        {"ts": now - 100, "trace_id": "h2", "truth_class": "HYPOTHESIS"},
    ])
    # TTL = 30s → h2 expires, h1 does not
    report = decay_hypothesis_rows(ledger, ttl_seconds=30, write=True, now=now)
    assert report.expired_rows == 1
    rows = [json.loads(ln) for ln in (tmp_path / DECAY_LEDGER).read_text().splitlines() if ln.strip()]
    assert rows[0]["parent_trace_id"] == "h2"


def test_truth_label_present_on_report():
    """Sanity: the module exports its TRUTH_LABEL constant correctly."""
    assert TRUTH_LABEL == "SIFTA_HYPOTHESIS_TTL_DECAY_V1"
