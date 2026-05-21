#!/usr/bin/env python3
"""Tests for alice_hardware_body - direct hardware-touch organ (high in-degree).

Upgraded campaign contract: every organ's own output ledger (here
alice_hardware_touch.jsonl) must also end at delta 0, in addition to the
four core ledgers.

Tests focus on the logging contract + representative read surfaces.
Write surfaces are exercised under heavy mocking.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from System import alice_hardware_body as body


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def test_module_exports_many_surfaces():
    """Real behavior 1: the organ exposes a rich surface of named verbs."""
    assert hasattr(body, "power")
    assert hasattr(body, "thermal")
    assert hasattr(body, "cpu_load")
    assert hasattr(body, "memory")
    assert hasattr(body, "wifi")
    assert hasattr(body, "set_volume")
    assert hasattr(body, "clipboard_write")
    assert hasattr(body, "notify")


def test_read_surfaces_are_side_effect_free_under_mocked_hardware(tmp_path, monkeypatch):
    """Read surfaces return structured data without writing the touch ledger."""
    original_ledger = body._TOUCH_LEDGER
    body._TOUCH_LEDGER = tmp_path / "alice_hardware_touch.jsonl"

    try:
        with patch.object(body, "_run") as mock_run, \
             patch.object(body, "_log") as mock_log:   # prevent real write while still exercising the call

            mock_run.return_value = (0, "Battery 87%; discharging", "")

            power = body.power()
            thermal = body.thermal()

            assert power["ok"] is True
            assert thermal["ok"] is True
            assert mock_run.call_count == 2
            assert mock_log.call_count == 0
            assert not body._TOUCH_LEDGER.exists()
    finally:
        body._TOUCH_LEDGER = original_ledger


def test_power_surface_parses_reasonably(monkeypatch):
    """Real behavior: power() returns structured data under normal conditions."""
    with patch.object(body, "_run") as mock_run:
        mock_run.return_value = (0, "Now drawing from 'Battery Power'\n -InternalBattery-0\t87%; discharging; 2:14 remaining", "")

        result = body.power()

    assert isinstance(result, dict)
    assert "ok" in result
    assert result.get("source") in ("Battery Power", "AC Power", None)


def test_thermal_surface_returns_level(monkeypatch):
    """Real behavior: thermal() reports a pressure level."""
    with patch.object(body, "_run") as mock_run:
        mock_run.return_value = (0, "CPU Power limit: 0\nthermal pressure: 1", "")

        result = body.thermal()

    assert isinstance(result, dict)
    assert "ok" in result


def test_write_surfaces_are_logged_and_safe(monkeypatch, tmp_path):
    """Write surfaces must still log and never raise on mocked paths."""
    original_ledger = body._TOUCH_LEDGER
    body._TOUCH_LEDGER = tmp_path / "alice_hardware_touch.jsonl"

    try:
        with patch.object(body, "_run") as mock_run:
            mock_run.return_value = (0, "", "")

            before = _count_lines(body._TOUCH_LEDGER)

            _ = body.set_volume(50)
            _ = body.set_mute(True)
            _ = body.notify("Test", "Coverage")

            after = _count_lines(body._TOUCH_LEDGER)
            assert (after - before) == 3
    finally:
        body._TOUCH_LEDGER = original_ledger


def test_real_ledgers_untouched_including_organ_own_log(tmp_path, monkeypatch):
    """Explicit isolation gate under the upgraded contract."""
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
        state / "alice_hardware_touch.jsonl",
    ]
    before = {str(p): _count_lines(p) for p in watch}

    # Redirect the organ's own ledger for the entire test
    original_ledger = body._TOUCH_LEDGER
    body._TOUCH_LEDGER = tmp_path / "alice_hardware_touch.jsonl"

    try:
        with patch.object(body, "_run") as mock_run, \
             patch.object(body, "_log"):   # prevent any real append to the redirected ledger
            mock_run.return_value = (0, "mock output", "")

            _ = body.power()
            _ = body.cpu_load()
            _ = body.wifi()
            _ = body.set_brightness(0.5)

    finally:
        body._TOUCH_LEDGER = original_ledger

    after = {str(p): _count_lines(p) for p in watch}
    delta = {k: after[k] - before[k] for k in before}

    assert all(v == 0 for v in delta.values()), f"Real ledgers (incl. organ own touch log) contaminated: {delta}"


def test_clipboard_and_processes_are_bounded(monkeypatch):
    """Safety surfaces: clipboard is truncated, processes filtered to swarm-owned."""
    with patch.object(body, "_run") as mock_run:
        mock_run.return_value = (0, "very long clipboard content " * 50, "")

        clip = body.clipboard()
        assert isinstance(clip, dict)
        assert "ok" in clip

        mock_run.return_value = (0, "12345 AliceProcess\n99999 OtherProcess", "")
        procs = body.processes()
        assert isinstance(procs, dict)
