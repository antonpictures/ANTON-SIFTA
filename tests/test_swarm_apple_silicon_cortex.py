#!/usr/bin/env python3
"""Tests for swarm_apple_silicon_cortex — Apple Silicon hardware introspection lobe (tranche 2 organ 6/12).

Upgraded contract: zero delta on core 4 + the organ's own output ledger
(apple_silicon_specs.json).

Focus: refresh_silicon_topography(), get_substrate_summary(), the safe wrapper,
and cache write under full isolation on real M5 hardware.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from System import swarm_apple_silicon_cortex as asc


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


def test_refresh_writes_cache_and_returns_valid_specs(tmp_path):
    """Real behavior 1: refresh_silicon_topography writes the cache and returns the expected keys."""
    cortex = asc.AppleSiliconCortex()
    cortex.state_dir = tmp_path
    cortex.cache_file = tmp_path / "apple_silicon_specs.json"

    specs = cortex.refresh_silicon_topography()

    assert isinstance(specs, dict)
    assert "chip_type" in specs
    assert "number_processors" in specs
    assert "physical_memory" in specs
    assert "machine_model" in specs

    # Cache must have been written
    assert cortex.cache_file.exists()
    cached = _read_json_safe(cortex.cache_file)
    assert cached.get("chip_type") == specs.get("chip_type")


def test_get_substrate_summary_formats_and_uses_cache(tmp_path):
    """Real behavior 2: get_substrate_summary returns a readable string and prefers cache when present."""
    cortex = asc.AppleSiliconCortex()
    cortex.state_dir = tmp_path
    cortex.cache_file = tmp_path / "apple_silicon_specs.json"

    # Force a refresh first
    cortex.refresh_silicon_topography()

    summary = cortex.get_substrate_summary()
    assert isinstance(summary, str)
    assert "Hardware Substrate:" in summary
    # On real M5 it should contain Apple or M5 or the actual values
    assert "Apple" in summary or "M5" in summary or "Unknown" in summary


def test_safe_wrapper_does_not_crash():
    """Safe public entrypoint works and never raises."""
    summary = asc.get_silicon_cortex_summary()
    assert isinstance(summary, str)
    assert len(summary) > 0


def test_real_ledgers_untouched_including_organ_own(tmp_path, monkeypatch):
    """Explicit isolation gate (core 4 + organ own apple_silicon_specs.json)."""
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
        state / "apple_silicon_specs.json",
    ]
    before = {str(p): _count_lines(p) for p in watch}

    # Isolated instance
    cortex = asc.AppleSiliconCortex()
    cortex.state_dir = tmp_path
    cortex.cache_file = tmp_path / "apple_silicon_specs.json"

    # Exercise the real surface
    _ = cortex.refresh_silicon_topography()
    s1 = cortex.get_substrate_summary()
    s2 = asc.get_silicon_cortex_summary()

    after = {str(p): _count_lines(p) for p in watch}
    delta = {k: after[k] - before[k] for k in before}

    assert all(v == 0 for v in delta.values()), f"Real ledgers (incl. organ own) contaminated: {delta}"

    # Prove we actually did work on the isolated cache
    assert (tmp_path / "apple_silicon_specs.json").exists()
    cached = _read_json_safe(tmp_path / "apple_silicon_specs.json")
    assert "chip_type" in cached
