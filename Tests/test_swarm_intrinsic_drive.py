"""Tests for swarm_intrinsic_drive (George Prior heartbeat)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_intrinsic_drive import (
    GEORGE_PRIOR,
    DriveReceipt,
    GeorgePriorDaemon,
    _circadian_weight,
    _epistemic_gap_score,
    _read_drive_weights,
    _read_recent_engram_topics,
    _sample_goal,
    get_current_drive,
    intrinsic_drive_tick,
    read_recent_drive_receipts,
    start_george_prior,
    stop_george_prior,
)


# ── George Prior weights ────────────────────────────────────────────────────────

def test_george_prior_sums_to_one():
    total = sum(GEORGE_PRIOR.values())
    assert abs(total - 1.0) < 0.01, f"George Prior should sum to ~1.0, got {total}"


def test_george_prior_all_positive():
    for topic, w in GEORGE_PRIOR.items():
        assert w > 0, f"Topic {topic!r} has non-positive weight {w}"


# ── Circadian weights ──────────────────────────────────────────────────────────

def test_circadian_night_boosts_biology():
    assert _circadian_weight("biology", 23) > 1.0
    assert _circadian_weight("biology", 2) > 1.0


def test_circadian_morning_boosts_code_quality():
    assert _circadian_weight("code_quality", 8) > 1.0


def test_circadian_night_dampens_code_quality():
    assert _circadian_weight("code_quality", 23) < 1.0


def test_circadian_neutral_hour():
    assert _circadian_weight("music", 14) == 1.0


# ── Epistemic gap scoring ──────────────────────────────────────────────────────

def test_epistemic_gap_unexplored_is_high():
    counts = {t: 0 for t in GEORGE_PRIOR}
    drives = {"curiosity": 0.9, "explore": 0.9, "repair": 0.5, "protect": 0.5, "rest": 0.2}
    score = _epistemic_gap_score("biology", counts, drives)
    assert score > 0.1, f"Unexplored biology should score high, got {score}"


def test_epistemic_gap_saturated_is_low():
    counts = {t: 200 for t in GEORGE_PRIOR}  # all very saturated
    drives = {"curiosity": 0.9, "explore": 0.9, "repair": 0.5, "protect": 0.5, "rest": 0.2}
    score = _epistemic_gap_score("biology", counts, drives)
    assert score < 0.01, f"Saturated biology should score low, got {score}"


# ── Goal sampling ─────────────────────────────────────────────────────────────

def test_sample_goal_returns_string():
    for topic in GEORGE_PRIOR:
        goal = _sample_goal(topic)
        assert isinstance(goal, str) and len(goal) > 5


def test_sample_goal_unknown_topic():
    goal = _sample_goal("unknown_topic_xyz")
    assert isinstance(goal, str)


# ── Single tick ───────────────────────────────────────────────────────────────

def test_intrinsic_drive_tick_returns_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr("System.swarm_intrinsic_drive._STATE", tmp_path)
    monkeypatch.setattr("System.swarm_intrinsic_drive._RECEIPT_LOG", tmp_path / "receipts.jsonl")
    monkeypatch.setattr("System.swarm_intrinsic_drive._ENGRAM_LOG", tmp_path / "engrams.jsonl")
    monkeypatch.setattr("System.swarm_intrinsic_drive._PLASTICITY", tmp_path / "plasticity.json")

    receipt = intrinsic_drive_tick()
    assert receipt is not None
    assert isinstance(receipt, DriveReceipt)
    assert receipt.topic in GEORGE_PRIOR
    assert len(receipt.goal) > 0
    assert receipt.score > 0
    assert 0.0 <= receipt.gap <= 1.0


def test_intrinsic_drive_tick_writes_receipt(tmp_path, monkeypatch):
    log = tmp_path / "receipts.jsonl"
    monkeypatch.setattr("System.swarm_intrinsic_drive._STATE", tmp_path)
    monkeypatch.setattr("System.swarm_intrinsic_drive._RECEIPT_LOG", log)
    monkeypatch.setattr("System.swarm_intrinsic_drive._ENGRAM_LOG", tmp_path / "e.jsonl")
    monkeypatch.setattr("System.swarm_intrinsic_drive._PLASTICITY", tmp_path / "p.json")

    intrinsic_drive_tick()
    assert log.exists()
    rows = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
    assert len(rows) == 1
    assert rows[0]["kind"] == "INTRINSIC_DRIVE_TICK"
    assert rows[0]["schema_version"].startswith("event99")


def test_receipt_schema_complete(tmp_path, monkeypatch):
    log = tmp_path / "receipts.jsonl"
    monkeypatch.setattr("System.swarm_intrinsic_drive._STATE", tmp_path)
    monkeypatch.setattr("System.swarm_intrinsic_drive._RECEIPT_LOG", log)
    monkeypatch.setattr("System.swarm_intrinsic_drive._ENGRAM_LOG", tmp_path / "e.jsonl")
    monkeypatch.setattr("System.swarm_intrinsic_drive._PLASTICITY", tmp_path / "p.json")

    receipt = intrinsic_drive_tick()
    d = receipt.as_dict()
    for required in ("kind", "schema_version", "receipt_id", "ts", "topic",
                     "goal", "score", "drive_weights", "hour",
                     "prior_weight", "gap", "circadian_factor", "source"):
        assert required in d, f"Missing field: {required}"


# ── Daemon ────────────────────────────────────────────────────────────────────

def test_daemon_starts_and_ticks(tmp_path, monkeypatch):
    monkeypatch.setattr("System.swarm_intrinsic_drive._STATE", tmp_path)
    monkeypatch.setattr("System.swarm_intrinsic_drive._RECEIPT_LOG", tmp_path / "r.jsonl")
    monkeypatch.setattr("System.swarm_intrinsic_drive._ENGRAM_LOG", tmp_path / "e.jsonl")
    monkeypatch.setattr("System.swarm_intrinsic_drive._PLASTICITY", tmp_path / "p.json")

    daemon = GeorgePriorDaemon(tick_interval=0.1)
    daemon.start()
    time.sleep(0.5)
    daemon.stop()
    daemon.join(timeout=1.0)
    assert daemon.ticks >= 1, "Daemon should have ticked at least once in 0.5s"


def test_start_george_prior_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr("System.swarm_intrinsic_drive._STATE", tmp_path)
    monkeypatch.setattr("System.swarm_intrinsic_drive._RECEIPT_LOG", tmp_path / "r.jsonl")
    monkeypatch.setattr("System.swarm_intrinsic_drive._ENGRAM_LOG", tmp_path / "e.jsonl")
    monkeypatch.setattr("System.swarm_intrinsic_drive._PLASTICITY", tmp_path / "p.json")
    monkeypatch.setattr("System.swarm_intrinsic_drive._daemon_instance", None)

    d1 = start_george_prior(tick_interval=0.1)
    d2 = start_george_prior(tick_interval=0.1)
    assert d1 is d2, "start_george_prior must be idempotent"
    stop_george_prior()


# ── Read API ──────────────────────────────────────────────────────────────────

def test_read_recent_drive_receipts_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("System.swarm_intrinsic_drive._RECEIPT_LOG", tmp_path / "r.jsonl")
    result = read_recent_drive_receipts(10)
    assert result == []


def test_read_recent_drive_receipts_returns_rows(tmp_path):
    log = tmp_path / "r.jsonl"
    # Write two synthetic receipts directly
    for _ in range(2):
        row = {"kind": "INTRINSIC_DRIVE_TICK", "topic": "biology", "goal": "test", "ts": time.time()}
        log.write_text("\n".join([json.dumps(row)] * 2) + "\n", encoding="utf-8")
    rows = read_recent_drive_receipts(5, log_path=log)
    assert len(rows) == 2
    assert all(r["kind"] == "INTRINSIC_DRIVE_TICK" for r in rows)
