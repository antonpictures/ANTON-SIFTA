#!/usr/bin/env python3
"""Round 60 — verifier smoke tests for the Round 59 WiFi sensing organ.

Grok-the-doctor (registration 81b2e9b1) landed System/swarm_wifi_sensing.py
without test coverage. Per the verifier chain "George -> CLAUDE verifies",
this file closes the test gap.

The organ writes to two ledgers (alice_hardware_touch.jsonl,
wifi_sensing.jsonl). These tests redirect the module's module-level path
constants to tmp_path so REAL ledgers are never touched.

What we verify:
  - ingest_csi_sample writes one row with the right kind + sensor_id
  - sample_basic_wifi writes one row with kind=wifi_basic_telemetry,
    returns {data, receipt_id}, handles missing _basic_wifi gracefully
  - latest_sensing_snapshot composes basic + latest CSI
  - receipt_id is non-empty
  - real .sifta_state/ ledgers untouched (covenant §6 isolation)
  - rapid successive writes do not silently lose rows
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_wifi_sensing as ws


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


@pytest.fixture
def tmp_ledgers(tmp_path, monkeypatch):
    """Redirect ledger paths to tmp_path. Returns the redirected paths."""
    new_basic = tmp_path / "alice_hardware_touch.jsonl"
    new_sensing = tmp_path / "wifi_sensing.jsonl"
    monkeypatch.setattr(ws, "_BASIC_TOUCH_LEDGER", new_basic)
    monkeypatch.setattr(ws, "_SENSING_LEDGER", new_sensing)
    return new_basic, new_sensing


# ─── ingest_csi_sample ──────────────────────────────────────────────────────


def test_ingest_csi_sample_writes_one_row(tmp_ledgers):
    _, sensing = tmp_ledgers
    sample = {
        "presence": True,
        "persons": 2,
        "breathing_bpm": 14.5,
        "heart_rate_bpm": 72.0,
        "rssi": -55,
        "confidence": 0.87,
    }
    rid = ws.ingest_csi_sample(sample, sensor_id="esp32_test")
    assert isinstance(rid, str) and rid != ""
    rows = _read_jsonl(sensing)
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "wifi_csi_sensing"
    assert row["sensor_id"] == "esp32_test"
    assert row["data"]["presence"] is True
    assert row["data"]["persons"] == 2
    assert row["receipt_id"] == rid
    assert "ts" in row


def test_ingest_csi_sample_default_sensor_id(tmp_ledgers):
    _, sensing = tmp_ledgers
    ws.ingest_csi_sample({"presence": False})
    rows = _read_jsonl(sensing)
    assert rows[0]["sensor_id"] == "esp32_csi"


# ─── sample_basic_wifi ──────────────────────────────────────────────────────


def test_sample_basic_wifi_writes_basic_ledger_row(tmp_ledgers):
    basic, _ = tmp_ledgers
    result = ws.sample_basic_wifi()
    assert "data" in result
    assert "receipt_id" in result and result["receipt_id"]
    rows = _read_jsonl(basic)
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "wifi_basic_telemetry"
    assert row["source"] == "alice_hardware_body.wifi"
    assert row["receipt_id"] == result["receipt_id"]


def test_sample_basic_wifi_graceful_when_hardware_body_missing(tmp_ledgers, monkeypatch):
    """If alice_hardware_body.wifi can't import, the organ still records an
    error receipt instead of raising."""
    basic, _ = tmp_ledgers
    monkeypatch.setattr(ws, "_basic_wifi", None)
    result = ws.sample_basic_wifi()
    assert result["data"]["ok"] is False
    assert "error" in result["data"]
    rows = _read_jsonl(basic)
    assert len(rows) == 1
    assert rows[0]["data"]["ok"] is False


# ─── latest_sensing_snapshot ────────────────────────────────────────────────


def test_latest_sensing_snapshot_no_csi_yet(tmp_ledgers):
    """Before any CSI sample, snapshot returns basic_wifi + csi=None."""
    snap = ws.latest_sensing_snapshot()
    assert "ts" in snap
    assert "basic_wifi" in snap
    assert "basic_receipt" in snap
    assert snap["csi"] is None


def test_latest_sensing_snapshot_includes_latest_csi_row(tmp_ledgers):
    """After ingesting CSI samples, snapshot surfaces the most recent."""
    ws.ingest_csi_sample({"persons": 1, "marker": "first"})
    ws.ingest_csi_sample({"persons": 3, "marker": "second"})
    snap = ws.latest_sensing_snapshot()
    assert snap["csi"] is not None
    assert snap["csi"]["marker"] == "second"
    assert snap["csi"]["persons"] == 3
    assert "csi_receipt" in snap


def test_latest_sensing_snapshot_handles_malformed_csi_ledger(tmp_ledgers):
    """A corrupt last line should land csi_error, not crash."""
    _, sensing = tmp_ledgers
    sensing.parent.mkdir(parents=True, exist_ok=True)
    sensing.write_text("not json at all\n", encoding="utf-8")
    snap = ws.latest_sensing_snapshot()
    # Module reads last line as JSON; failure path sets csi_error
    assert "csi_error" in snap


# ─── Rapid-write integrity ──────────────────────────────────────────────────


def test_rapid_successive_writes_do_not_lose_rows(tmp_ledgers):
    """If id()+ts collide, rows could silently overlap on receipt_id. The row
    itself should still land — append is line-by-line. This guards file
    integrity even if receipt_id ends up non-unique (flagged in §59.1)."""
    _, sensing = tmp_ledgers
    for i in range(20):
        ws.ingest_csi_sample({"persons": i})
    rows = _read_jsonl(sensing)
    assert len(rows) == 20
    # All 20 unique persons values survived
    persons_set = {r["data"]["persons"] for r in rows}
    assert persons_set == set(range(20))


# ─── Real-ledger isolation (covenant §6) ────────────────────────────────────


def test_real_ledgers_untouched(tmp_path, monkeypatch):
    """Hard invariant: with the module's ledger paths redirected to tmp,
    every public function leaves the real .sifta_state/* files untouched."""
    new_basic = tmp_path / "alice_hardware_touch.jsonl"
    new_sensing = tmp_path / "wifi_sensing.jsonl"
    monkeypatch.setattr(ws, "_BASIC_TOUCH_LEDGER", new_basic)
    monkeypatch.setattr(ws, "_SENSING_LEDGER", new_sensing)

    state = Path(".sifta_state")
    watch = [
        state / "alice_hardware_touch.jsonl",
        state / "wifi_sensing.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
    ]
    before = {str(p): (p.stat().st_size if p.exists() else 0) for p in watch}

    ws.sample_basic_wifi()
    ws.ingest_csi_sample({"presence": True, "persons": 1})
    ws.latest_sensing_snapshot()

    after = {str(p): (p.stat().st_size if p.exists() else 0) for p in watch}
    for k in before:
        assert before[k] == after[k], (
            f"wifi sensing mutated {k}: {before[k]} -> {after[k]}"
        )
