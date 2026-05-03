"""Event 124 - multi-gate replay policy receipts."""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_multi_gate_replay_policy as mg


def test_compute_sets_multiple_gates_from_replay() -> None:
    gates = mg.compute_multi_gate_bias(
        "Alice, can you tell if the video is paused?",
        "The owner and Alice watched a YouTube video together for hours.",
    )
    assert gates["co_watch_suggestion"] >= 0.7
    assert gates["question_followup"] >= 0.5
    assert gates["session_persistence"] >= 0.55
    assert gates["media_context_sensitivity"] >= 0.55
    assert all(0.0 <= v <= 1.0 for v in gates.values())


def test_prior_decays_without_new_evidence() -> None:
    prior = {k: 0.50 for k in mg.BASE_GATES}
    gates = mg.compute_multi_gate_bias("quiet", "ambient", prior_gates=prior, decay=0.05)
    assert gates == {k: 0.45 for k in mg.BASE_GATES}


def test_apply_writes_locked_receipt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mg, "state_dir", lambda explicit=None: tmp_path)
    monkeypatch.delenv("SIFTA_MULTI_GATE_REPLAY_DISABLE", raising=False)
    gates = mg.apply_multi_gate_bias(
        "opening video",
        "YouTube together with owner, research paper after",
        root=tmp_path,
        force_write=True,
    )
    assert gates["co_watch_suggestion"] > 0
    assert gates["research_depth"] > 0

    path = mg.multi_gate_log_path(tmp_path)
    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["truth_label"] == "MULTI_GATE_REPLAY_POLICY"
    assert row["gate_biases"] == gates
    assert row["total_adaptation_strength"] > 0


def test_disable_skips_ledger(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mg, "state_dir", lambda explicit=None: tmp_path)
    monkeypatch.setenv("SIFTA_MULTI_GATE_REPLAY_DISABLE", "1")
    gates = mg.apply_multi_gate_bias("youtube", "youtube together", root=tmp_path)
    assert gates == mg.BASE_GATES
    assert not mg.multi_gate_log_path(tmp_path).exists()


def test_summary_and_class_facade(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mg, "state_dir", lambda explicit=None: tmp_path)
    gates = mg.MultiGateReplayPolicy.apply_multi_gate_bias(
        ["shared YouTube video with owner"],
        root=tmp_path,
        force_write=True,
    )
    assert gates["co_watch_suggestion"] > 0
    assert mg.MultiGateReplayPolicy.get_current_gate_state(root=tmp_path) == gates
    summary = mg.summary_for_prompt(root=tmp_path)
    assert "MULTI-GATE REPLAY POLICY" in summary
    assert "co_watch_suggestion=" in summary
