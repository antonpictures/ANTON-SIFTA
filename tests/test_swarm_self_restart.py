#!/usr/bin/env python3
"""Tests for swarm_self_restart — self-restart lobe (tranche 2 organ 3/12).

Upgraded contract: zero delta on core 4 + the organ's own output ledger
(restart_events.jsonl).

Focus: restart_app / restart_mac (dry-run + mocked paths), logging contract,
CLI surface. Never actually restart anything.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from System import swarm_self_restart as restart


class _RunResult:
    def __init__(self, stdout: str = ""):
        self.stdout = stdout


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def test_running_os_pids_matches_absolute_and_relative_python_desktop(monkeypatch):
    def fake_run(*_args, **_kwargs):
        return _RunResult(
            "\n".join(
                [
                    " 111 /opt/homebrew/bin/python3.14 sifta_os_desktop.py",
                    f" 222 /opt/homebrew/bin/python3.14 {restart._OS_DESKTOP}",
                    " 333 /bin/zsh -c rg sifta_os_desktop.py",
                    " 444 /usr/bin/python3 other_tool.py",
                ]
            )
        )

    monkeypatch.setattr(restart.subprocess, "run", fake_run)
    monkeypatch.setattr(restart.os, "getpid", lambda: 999)

    assert restart._running_os_pids() == [111, 222]


def test_spawn_launcher_uses_macos_open_for_tcc_launch_path(tmp_path, monkeypatch):
    launcher = tmp_path / "SIFTA OS.command"
    launcher.write_text("#!/bin/bash\n", encoding="utf-8")
    calls = []

    class FakePopen:
        pid = 555

        def __init__(self, argv, **kwargs):
            calls.append((argv, kwargs))

    monkeypatch.setattr(restart, "_LAUNCHER", launcher)
    monkeypatch.setattr(restart.subprocess, "Popen", FakePopen)

    assert restart._spawn_launcher() == 555
    assert calls[0][0] == ["/usr/bin/open", str(launcher)]
    assert "env" not in calls[0][1]


def test_restart_app_dry_run_logs_and_returns_zero(tmp_path, monkeypatch):
    """Dry-run path for app restart exercises logging without side effects."""
    original_ledger = restart._LEDGER
    restart._LEDGER = tmp_path / "restart_events.jsonl"

    try:
        before = _count_lines(restart._LEDGER)

        with patch("System.swarm_self_restart._speak_farewell"), \
             patch("System.swarm_self_restart._emit_sleep_pulse"), \
             patch("System.swarm_self_restart.time.sleep"):
            rc = restart.restart_app(reason="test coverage", dry_run=True)

        after = _count_lines(restart._LEDGER)
        assert (after - before) == 1
        assert rc == 0
    finally:
        restart._LEDGER = original_ledger


def test_restart_mac_dry_run_logs_and_returns_zero(tmp_path, monkeypatch):
    """Dry-run path for mac restart."""
    original_ledger = restart._LEDGER
    restart._LEDGER = tmp_path / "restart_events.jsonl"

    try:
        before = _count_lines(restart._LEDGER)

        with patch("System.swarm_self_restart._speak_farewell"), \
             patch("System.swarm_self_restart._emit_sleep_pulse"), \
             patch("System.swarm_self_restart.time.sleep"):
            rc = restart.restart_mac(reason="test coverage mac", dry_run=True)

        after = _count_lines(restart._LEDGER)
        assert (after - before) == 1
        assert rc == 0
    finally:
        restart._LEDGER = original_ledger


def test_real_ledgers_untouched_including_organ_own(tmp_path, monkeypatch):
    """Explicit isolation gate (core 4 + organ own restart_events.jsonl)."""
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
        state / "restart_events.jsonl",
    ]
    before = {str(p): _count_lines(p) for p in watch}

    original_ledger = restart._LEDGER
    restart._LEDGER = tmp_path / "restart_events.jsonl"

    try:
        with patch("System.swarm_self_restart._quit_app") as mock_quit, \
             patch("System.swarm_self_restart._spawn_launcher") as mock_spawn, \
             patch("System.swarm_self_restart._speak_farewell"), \
             patch("System.swarm_self_restart._emit_sleep_pulse"), \
             patch("System.swarm_self_restart.time.sleep"):

            mock_quit.return_value = True
            mock_spawn.return_value = 12345

            restart.restart_app(reason="isolation test", dry_run=False)
            restart.restart_mac(reason="isolation mac test", dry_run=False)
    finally:
        restart._LEDGER = original_ledger

    after = {str(p): _count_lines(p) for p in watch}
    delta = {k: after[k] - before[k] for k in before}

    assert all(v == 0 for v in delta.values()), f"Real ledgers (incl. organ own) contaminated: {delta}"
