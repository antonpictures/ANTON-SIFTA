#!/usr/bin/env python3
"""Tests for r536 + r1073 endurance harness modes."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "tools" / "sifta_endurance_harness.py"


def _run_harness(extra_args: list[str], *, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO) + (
        ":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env.setdefault("SIFTA_ENDURANCE_LIVE_TIMEOUT_S", "3")
    cmd = [sys.executable, str(HARNESS), *extra_args]
    return subprocess.run(
        cmd,
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_endurance_harness_short_healthy_run():
    proc = _run_harness(["--turns", "5", "--report"])
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, f"expected exit 0\n{out[:2000]}"
    assert "ENDURANCE SCORE:" in out
    assert "receipts_fanned:" in out
    assert "BREACHES:" not in out


def test_endurance_minutes_budget_short():
    proc = _run_harness(["--turns", "20", "--minutes", "0.05", "--report"])
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, f"minutes mode failed\n{out[:2000]}"
    assert "minutes_budget:" in out
    assert "latency_series:" in out


def test_endurance_chaos_short():
    proc = _run_harness(["--turns", "4", "--chaos", "--report"])
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, f"chaos mode failed\n{out[:2000]}"
    assert "chaos: True" in out


def test_endurance_audit_receipts_short():
    proc = _run_harness(["--turns", "3", "--audit-receipts", "--report"])
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, f"audit mode failed\n{out[:2000]}"
    assert "audit_receipts: True" in out
    assert "receipt_fan_rate:" in out


def test_endurance_live_cortex_short_or_honest_fallback():
    proc = _run_harness(
        ["--turns", "2", "--live-cortex", "--report"],
        timeout=300,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, f"live-cortex mode failed\n{out[:3000]}"
    assert "live_cortex: True" in out
    assert any(
        p in out
        for p in (
            "live_cortex",
            "live_cortex_timeout_recovery",
            "live_cortex_unavailable_honest",
            "live_cortex_chaos_timeout_recovery",
        )
    )


def test_endurance_inject_breach_exits_nonzero():
    proc = _run_harness(["--turns", "3", "--inject-breach-at", "1", "--report"])
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0, f"expected breach exit non-zero\n{out[:2000]}"
    assert "BREACHES:" in out
    assert "turn 1:" in out


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
