#!/usr/bin/env python3
"""Tests for swarm_mirror_lock — Stigmergic Infinite Detector / mirror self-observation organ (tranche 2 organ 7/12).

Upgraded contract: zero delta on core 4 + the organ's own output ledgers
(mirror_lock_state.json and mirror_lock_events.jsonl).

Focus: evaluate_window + tick_once with synthetic data, state transitions,
public accessors, camera-liveness stale guard, and full isolation.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from System import swarm_mirror_lock as ml


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_evaluate_window_detects_lock_like_data():
    """Real behavior 1: evaluate_window returns True + metrics when all five conditions hold."""
    base_ts = time.time()
    rows = ml._make_lock_like_rows(n=10, base_ts=base_ts)
    in_lock, metrics = ml.evaluate_window(rows)
    assert in_lock is True
    assert metrics.saliency_stability >= 0.90


def test_tick_once_updates_state_and_mints_event_under_isolation(tmp_path, monkeypatch):
    """Real behavior 2: tick_once under redirected ledgers writes state and events correctly."""
    visual = tmp_path / "visual_stigmergy.jsonl"
    statef = tmp_path / "mirror_lock_state.json"
    events = tmp_path / "mirror_lock_events.jsonl"

    # Redirect all paths the organ touches
    monkeypatch.setattr(ml, "VISUAL_LEDGER", visual)
    monkeypatch.setattr(ml, "STATE_FILE", statef)
    monkeypatch.setattr(ml, "EVENTS_LEDGER", events)

    # Seed a lock-like window
    base = time.time() - 5
    rows = ml._make_lock_like_rows(n=12, base_ts=base)
    _write_jsonl(visual, rows)

    state = ml.tick_once(now=time.time())

    assert state.get("in_lock") is True
    assert statef.exists()

    # Second tick (still locked) should not explode
    state2 = ml.tick_once(now=time.time() + 1)
    assert state2.get("in_lock") is True


def test_is_in_mirror_lock_and_summary_are_isolated(tmp_path, monkeypatch):
    """Real behavior 3: public query functions read the redirected state."""
    statef = tmp_path / "mirror_lock_state.json"
    monkeypatch.setattr(ml, "STATE_FILE", statef)

    # Seed a locked state directly
    statef.parent.mkdir(parents=True, exist_ok=True)
    statef.write_text(json.dumps({
        "in_lock": True,
        "lock_started_ts": time.time() - 30,
        "latest_metrics": {"dominant_hue_deg": 210.0},
        "last_session": None
    }), encoding="utf-8")

    assert ml.is_in_mirror_lock() is True
    age = ml.lock_age_seconds()
    assert age is not None and age > 20

    s = ml.summary_for_alice()
    assert "MIRROR LOCK active" in s


def test_stale_camera_guard_prevents_false_lock(tmp_path, monkeypatch):
    """Camera-liveness guard: old visual rows must not trigger in_lock=True."""
    visual = tmp_path / "visual_stigmergy.jsonl"
    statef = tmp_path / "mirror_lock_state.json"
    events = tmp_path / "mirror_lock_events.jsonl"

    monkeypatch.setattr(ml, "VISUAL_LEDGER", visual)
    monkeypatch.setattr(ml, "STATE_FILE", statef)
    monkeypatch.setattr(ml, "EVENTS_LEDGER", events)

    # Very old rows (older than _MAX_FRAME_AGE_S)
    old = time.time() - 300
    rows = ml._make_lock_like_rows(n=8, base_ts=old)
    _write_jsonl(visual, rows)

    state = ml.tick_once(now=time.time())
    assert state.get("latest_metrics", {}).get("stale") is True
    assert state.get("in_lock") is False


def test_real_ledgers_untouched_including_organ_own(tmp_path, monkeypatch):
    """Explicit isolation gate (core 4 + organ own mirror_lock_* ledgers)."""
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
        state / "mirror_lock_state.json",
        state / "mirror_lock_events.jsonl",
    ]
    before = {str(p): _count_lines(p) for p in watch}

    # Fully isolated paths
    v = tmp_path / "v.jsonl"
    s = tmp_path / "s.json"
    e = tmp_path / "e.jsonl"
    monkeypatch.setattr(ml, "VISUAL_LEDGER", v)
    monkeypatch.setattr(ml, "STATE_FILE", s)
    monkeypatch.setattr(ml, "EVENTS_LEDGER", e)

    # Exercise real surface
    rows = ml._make_lock_like_rows(n=10, base_ts=time.time() - 2)
    _write_jsonl(v, rows)
    _ = ml.tick_once(now=time.time())
    _ = ml.current_state()
    _ = ml.summary_for_alice()

    after = {str(p): _count_lines(p) for p in watch}
    delta = {k: after[k] - before[k] for k in before}

    assert all(v == 0 for v in delta.values()), f"Real ledgers (incl. organ own) contaminated: {delta}"
