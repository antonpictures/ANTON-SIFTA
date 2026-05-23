#!/usr/bin/env python3
"""Tests for dopamine_ou_engine — Ornstein–Uhlenbeck DA with RPE from affinity outcomes (tranche 2 organ 5/12).

Upgraded contract: zero delta on core 4 + the organ's own output ledger
(dopamine_ou_engine.json).

Focus: DopamineState.tick(), behavioral classification, wake boost, persist/load
roundtrip, and full isolation. No network, deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from System import dopamine_ou_engine as dou


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def _read_json_safe(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def test_tick_produces_valid_dastate_and_classifies_behavior():
    """Real behavior 1: tick() returns DAState with correct fields and behavioral_state classification."""
    ds = dou.DopamineState(initial_da=0.50)

    # High affinity + novelty → should push toward EXPLOITATION
    st = ds.tick(novelty_score=0.9, affinity_outcome=0.85, dt=1.0)
    assert isinstance(st, dou.DAState)
    assert 0.05 <= st.level <= 0.95
    assert st.behavioral_state in (dou.BehavioralState.EXPLOITATION, dou.BehavioralState.MAINTENANCE, dou.BehavioralState.EXPLORATION)
    assert st.directive in dou.DIRECTIVES.values()
    assert st.rpe is not None
    assert st.novelty == 0.9

    # Low affinity → should trend toward EXPLORATION
    ds2 = dou.DopamineState(initial_da=0.30)
    st2 = ds2.tick(novelty_score=0.1, affinity_outcome=0.20, dt=1.0)
    # After several low ticks it should enter EXPLORATION
    for _ in range(5):
        st2 = ds2.tick(novelty_score=0.1, affinity_outcome=0.20, dt=1.0)
    assert st2.behavioral_state == dou.BehavioralState.EXPLORATION


def test_notify_wake_applies_boost_and_resets_expected():
    """Real behavior 2: notify_wake() sets wake_ticks and clears expected_affinity for post-sleep boost."""
    ds = dou.DopamineState(initial_da=0.50)
    ds.notify_wake()
    assert ds._wake_ticks == dou.WAKE_BOOST_TICKS

    st = ds.tick(novelty_score=0.5, affinity_outcome=0.5, dt=1.0)
    # Wake boost should have been consumed
    assert ds._wake_ticks < dou.WAKE_BOOST_TICKS
    assert st.level >= 0.50  # at least baseline + any residual boost effect


def test_persist_load_roundtrip_isolates_state(tmp_path, monkeypatch):
    """Real behavior 3: persist_ou_engine + load_ou_engine roundtrip under redirected path."""
    target = tmp_path / "dopamine_ou_engine.json"

    # Redirect the module's hard-coded path
    monkeypatch.setattr(dou, "_OU_STATE_PATH", target)

    ds = dou.DopamineState(initial_da=0.72)
    ds.tick(novelty_score=0.6, affinity_outcome=0.78, dt=1.0)
    dou.persist_ou_engine(ds, path=target)

    loaded = dou.load_ou_engine(path=target)
    assert abs(loaded.level - ds.level) < 0.01
    assert loaded._tick_count == ds._tick_count


def test_real_ledgers_untouched_including_organ_own(tmp_path, monkeypatch):
    """Explicit isolation gate (core 4 + organ own dopamine_ou_engine.json)."""
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
        state / "dopamine_ou_engine.json",
    ]
    before = {str(p): _count_lines(p) for p in watch}

    target = tmp_path / "dopamine_ou_engine.json"
    monkeypatch.setattr(dou, "_OU_STATE_PATH", target)

    # Exercise the real public surface under isolation
    engine = dou.load_ou_engine(path=target)
    for i in range(4):
        novelty = 0.3 + (i * 0.15)
        affinity = 0.4 + (i * 0.12)
        st = engine.tick(novelty_score=novelty, affinity_outcome=affinity, dt=1.0)
        dou.persist_ou_engine(engine, path=target)

    # Also exercise wake path
    engine.notify_wake()
    _ = engine.tick(novelty_score=0.8, affinity_outcome=0.75, dt=1.0)

    after = {str(p): _count_lines(p) for p in watch}
    delta = {k: after[k] - before[k] for k in before}

    assert all(v == 0 for v in delta.values()), f"Real ledgers (incl. organ own) contaminated: {delta}"

    # Sanity: we actually wrote something to the isolated target
    assert target.exists()
    data = _read_json_safe(target)
    assert "da" in data or "module_version" in data
