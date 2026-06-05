"""Tests for System/swarm_gemma_rlhf_ears_gates.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# r283 verifier hygiene: this organ is not on disk on this node. Skip cleanly instead
# of erroring the whole collection; the test revives automatically if the organ lands.
g = pytest.importorskip("System.swarm_gemma_rlhf_ears_gates")


def test_create_training_example_append_locked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(g, "_STATE", tmp_path)
    monkeypatch.setattr(g, "LEDGER", tmp_path / "gemma_rlhf_training_data.jsonl")
    row = g.create_training_example(
        "hey alice what is 2+2",
        "Two plus two is four. Here is a direct answer without a service menu tail.",
        raw_reply="Two plus two is four. Would you like me to elaborate with the following options:",
        stt_conf=0.72,
        state_dir=tmp_path,
    )
    assert row["truth_label"] == g.TRUTH_LABEL
    assert row["example_id"]
    assert row["quality_score"] > 0.0
    assert row["acoustic_context"]
    data = (tmp_path / "gemma_rlhf_training_data.jsonl").read_text(encoding="utf-8").strip()
    loaded = json.loads(data.splitlines()[-1])
    assert loaded["preferred_output"].startswith("Two plus two")


def test_stats_empty_and_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(g, "_STATE", tmp_path)
    assert g.get_clean_training_stats(state_dir=tmp_path)["examples"] == 0
    g.create_training_example("a", "b" * 40, state_dir=tmp_path)
    g.create_training_example("c", "d" * 40, state_dir=tmp_path)
    st = g.get_clean_training_stats(state_dir=tmp_path)
    assert st["examples"] == 2
