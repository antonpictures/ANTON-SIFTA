"""Tests for the stigmergic arm fallback picker."""
from __future__ import annotations

import json
import time
from pathlib import Path

from System import swarm_stigmergic_arm_fallback as sf


def _write_receipts(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_arm_success_counts_empty_ledger(tmp_path: Path) -> None:
    out = sf.arm_success_counts(tmp_path)
    assert out == {}


def test_arm_success_counts_counts_ok_and_truth_label(tmp_path: Path) -> None:
    now = 100.0
    _write_receipts(tmp_path / "agent_arm_receipts.jsonl", [
        {"ts": now - 60, "arm_id": "codex_agent", "ok": True, "truth_label": "OPERATIONAL"},
        {"ts": now - 30, "arm_id": "codex_agent", "ok": False, "truth_label": "STABILITY_CLAMP_SUPPRESSED"},
        {"ts": now - 20, "arm_id": "claude_agent", "ok": True, "truth_label": "OPERATIONAL"},
        {"ts": now - 10, "arm_id": "claude_agent", "ok": True, "truth_label": "OPERATIONAL"},
        {"ts": now - 5, "arm_id": "grok_agent", "ok": False, "truth_label": "TIMEOUT"},
    ])
    out = sf.arm_success_counts(tmp_path, now=now)
    assert out["codex_agent"]["attempts"] == 2
    assert out["codex_agent"]["successes"] == 1
    assert out["codex_agent"]["success_rate"] == 0.5
    assert out["claude_agent"]["attempts"] == 2
    assert out["claude_agent"]["successes"] == 2
    assert out["claude_agent"]["success_rate"] == 1.0
    assert out["grok_agent"]["successes"] == 0


def test_arm_success_counts_window_drops_old_rows(tmp_path: Path) -> None:
    now = 1000.0
    _write_receipts(tmp_path / "agent_arm_receipts.jsonl", [
        {"ts": now - 99999, "arm_id": "codex_agent", "ok": True, "truth_label": "OPERATIONAL"},
        {"ts": now - 5, "arm_id": "claude_agent", "ok": True, "truth_label": "OPERATIONAL"},
    ])
    out = sf.arm_success_counts(tmp_path, max_age_s=60.0, now=now)
    assert "codex_agent" not in out
    assert out["claude_agent"]["successes"] == 1


def test_pick_fallback_picks_highest_success_rate(tmp_path: Path) -> None:
    now = 200.0
    _write_receipts(tmp_path / "agent_arm_receipts.jsonl", [
        {"ts": now - 30, "arm_id": "claude_agent", "ok": True, "truth_label": "OPERATIONAL"},
        {"ts": now - 25, "arm_id": "claude_agent", "ok": True, "truth_label": "OPERATIONAL"},
        {"ts": now - 20, "arm_id": "corvid_scout", "ok": True, "truth_label": "OPERATIONAL"},
        {"ts": now - 15, "arm_id": "corvid_scout", "ok": False, "truth_label": "TIMEOUT"},
    ])
    out = sf.pick_fallback_arm(
        tmp_path,
        exclude=("codex_agent",),
        available=("codex_agent", "claude_agent", "corvid_scout"),
        now=now,
    )
    assert out["arm_id"] == "claude_agent"
    assert out["reason"] == "stigmergic_recent_success_winner"
    assert out["success_rate"] == 1.0


def test_pick_fallback_excludes_the_timed_out_arm(tmp_path: Path) -> None:
    now = 300.0
    _write_receipts(tmp_path / "agent_arm_receipts.jsonl", [
        {"ts": now - 5, "arm_id": "claude_agent", "ok": True, "truth_label": "OPERATIONAL"},
    ])
    out = sf.pick_fallback_arm(
        tmp_path,
        exclude=("claude_agent",),
        available=("claude_agent", "corvid_scout"),
        now=now,
    )
    assert out["arm_id"] == "corvid_scout"


def test_pick_fallback_no_recent_success_still_picks(tmp_path: Path) -> None:
    now = 400.0
    _write_receipts(tmp_path / "agent_arm_receipts.jsonl", [
        {"ts": now - 5, "arm_id": "codex_agent", "ok": False, "truth_label": "TIMEOUT"},
    ])
    out = sf.pick_fallback_arm(
        tmp_path,
        exclude=("codex_agent",),
        available=("corvid_scout", "grok_agent"),
        now=now,
    )
    assert out["arm_id"] in {"corvid_scout", "grok_agent"}
    assert out["reason"] == "no_recent_success_in_window_using_first_available"


def test_pick_fallback_empty_available_returns_node_default(tmp_path: Path) -> None:
    out = sf.pick_fallback_arm(tmp_path, exclude=(), available=())
    assert out["arm_id"] == "corvid_scout"
    assert "no_available_arms_supplied" in out["reason"]


def test_pick_fallback_breaks_ties_by_recency(tmp_path: Path) -> None:
    now = 500.0
    _write_receipts(tmp_path / "agent_arm_receipts.jsonl", [
        {"ts": now - 60, "arm_id": "claude_agent", "ok": True, "truth_label": "OPERATIONAL"},
        {"ts": now - 5, "arm_id": "grok_agent", "ok": True, "truth_label": "OPERATIONAL"},
    ])
    out = sf.pick_fallback_arm(
        tmp_path,
        exclude=("codex_agent",),
        available=("claude_agent", "grok_agent"),
        now=now,
    )
    # Both have success_rate=1.0; grok_agent has the more recent success.
    assert out["arm_id"] == "grok_agent"
