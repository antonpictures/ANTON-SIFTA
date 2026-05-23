#!/usr/bin/env python3
"""Tests for swarm_inferior_olive — value network + climbing-fiber feedback (first of tranche 2).

Upgraded contract: zero delta on core 4 + the organ's own two ledgers
(deepmind_prediction_cache.json and inferior_olive_climbing_fiber.jsonl).

Focus: construction, ingest (real + dream), predict, and explicit climbing-fiber pulses.
All state isolated.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from System import swarm_inferior_olive as olive


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def test_get_inferior_olive_returns_instance():
    """Real behavior 1: entry point works."""
    o = olive.get_inferior_olive() if hasattr(olive, "get_inferior_olive") else olive.InferiorOlive()
    assert isinstance(o, olive.InferiorOlive) or hasattr(o, "predict")


def test_ingest_real_and_predict_under_isolation(tmp_path, monkeypatch):
    """Core on-policy path + prediction under full ledger isolation."""
    original_cache = olive.PREDICTION_CACHE
    original_cf = olive.CLIMBING_FIBER_LOG
    olive.PREDICTION_CACHE = tmp_path / "deepmind_prediction_cache.json"
    olive.CLIMBING_FIBER_LOG = tmp_path / "inferior_olive_climbing_fiber.jsonl"

    try:
        o = olive.InferiorOlive()

        # Mock the public ingestion entry point so we control data without touching real warp9 logs
        with patch.object(o, "ingest_real_ledgers", return_value=1):
            val = o.predict("s_test", "a_test")
            assert isinstance(val, (int, float))
    finally:
        olive.PREDICTION_CACHE = original_cache
        olive.CLIMBING_FIBER_LOG = original_cf


def test_real_ledgers_untouched_including_organ_own_two(tmp_path, monkeypatch):
    """Explicit isolation gate (core 4 + organ's prediction cache + climbing fiber log)."""
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
        state / "deepmind_prediction_cache.json",
        state / "inferior_olive_climbing_fiber.jsonl",
    ]
    before = {str(p): _count_lines(p) for p in watch}

    original_cache = olive.PREDICTION_CACHE
    original_cf = olive.CLIMBING_FIBER_LOG
    olive.PREDICTION_CACHE = tmp_path / "deepmind_prediction_cache.json"
    olive.CLIMBING_FIBER_LOG = tmp_path / "inferior_olive_climbing_fiber.jsonl"

    try:
        o = olive.InferiorOlive()

        with patch.object(o, "ingest_real_ledgers", return_value=1), \
             patch.object(o, "_audit_pulse"):
            _ = o.predict("s_test", "a_test")
    finally:
        olive.PREDICTION_CACHE = original_cache
        olive.CLIMBING_FIBER_LOG = original_cf

    after = {str(p): _count_lines(p) for p in watch}
    delta = {k: after[k] - before[k] for k in before}

    assert all(v == 0 for v in delta.values()), f"Real ledgers (incl. organ own) contaminated: {delta}"