"""Event 123 - replay policy hook receipts."""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_replay_policy_hook as ph


def test_compute_bias_youtube_boost() -> None:
    b = ph.compute_replay_bias("idle", "We often watch YouTube together on this desk")
    assert b["co_watch_suggestion"] >= 0.6


def test_apply_writes_ledger(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ph, "state_dir", lambda explicit=None: tmp_path)
    monkeypatch.delenv("SIFTA_REPLAY_POLICY_DISABLE", raising=False)
    b = ph.apply_replay_bias(
        "opening YouTube",
        "collab video sessions are common here",
        write_ledger=True,
        root=tmp_path,
    )
    assert b["co_watch_suggestion"] > 0
    p = ph.policy_log_path(tmp_path)
    assert p.exists()
    row = json.loads(p.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["truth_label"] == "REPLAY_POLICY_BIAS"
    assert row["replay_influence"] == b


def test_disable_env_skips_ledger(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ph, "state_dir", lambda explicit=None: tmp_path)
    monkeypatch.setenv("SIFTA_REPLAY_POLICY_DISABLE", "1")
    ph.apply_replay_bias("x", "y", write_ledger=True, root=tmp_path)
    assert not ph.policy_log_path(tmp_path).exists()


def test_summary_for_prompt_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ph, "state_dir", lambda explicit=None: tmp_path)
    assert ph.summary_for_prompt(root=tmp_path) == ""


def test_throttle_second_write_skipped(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ph, "state_dir", lambda explicit=None: tmp_path)
    ph.apply_replay_bias("a", "youtube together", root=tmp_path, min_seconds_between_writes=999.0)
    ph.apply_replay_bias("b", "youtube together", root=tmp_path, min_seconds_between_writes=999.0)
    n = len(ph.policy_log_path(tmp_path).read_text(encoding="utf-8").strip().splitlines())
    assert n == 1
