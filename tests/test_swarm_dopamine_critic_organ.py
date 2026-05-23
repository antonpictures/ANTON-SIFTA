"""Event 125 - dopamine critic proxy (locked ledger)."""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_dopamine_critic_organ as dc


def test_score_positive() -> None:
    assert dc.score_owner_outcome_heuristic("Yes thanks that was great") > 0.3


def test_score_negative() -> None:
    assert dc.score_owner_outcome_heuristic("No stop that was wrong") < -0.2


def test_score_is_phrase_safe() -> None:
    assert dc.score_owner_outcome_heuristic("now tell me what you know") == 0.0
    assert dc.score_owner_outcome_heuristic("not good") < 0.0


def test_apply_updates_and_logs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(dc, "state_dir", lambda explicit=None: tmp_path)
    monkeypatch.delenv("SIFTA_DOPAMINE_CRITIC_DISABLE", raising=False)
    prev = {"co_watch_suggestion": 0.5, "owner_continuity": 0.3}
    out = dc.apply_critic_to_bias_vector(
        "co_watch_suggestion",
        "thanks love it",
        prev,
        root=tmp_path,
    )
    assert out["co_watch_suggestion"] >= prev["co_watch_suggestion"]
    p = dc.critic_log_path(tmp_path)
    assert p.exists()
    row = json.loads(p.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["truth_label"] == "DOPAMINE_CRITIC_PROXY"
    assert row["outcome_score"] > 0
    assert "research_depth" in out

    from System.swarm_multi_gate_replay_policy import (
        BASE_GATES,
        current_gate_state,
        multi_gate_log_path,
    )

    mg = multi_gate_log_path(tmp_path)
    assert mg.exists()
    mg_row = json.loads(mg.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert mg_row["truth_label"] == "MULTI_GATE_REPLAY_POLICY"
    assert mg_row["source_truth_label"] == "DOPAMINE_CRITIC_PROXY"
    assert set(mg_row["gate_biases"]) == set(BASE_GATES)
    assert current_gate_state(root=tmp_path)["co_watch_suggestion"] == out["co_watch_suggestion"]


def test_negative_structured_score_reverses_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(dc, "state_dir", lambda explicit=None: tmp_path)
    monkeypatch.delenv("SIFTA_DOPAMINE_CRITIC_DISABLE", raising=False)
    prev = {"owner_continuity": 0.7}
    out = dc.apply_critic_to_bias_vector(
        "owner_continuity",
        "structured downvote",
        prev,
        root=tmp_path,
        structured_score=-1.0,
        learning_rate=0.2,
    )
    assert out["owner_continuity"] == 0.5


def test_kill_switch_skips_ledger(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(dc, "state_dir", lambda explicit=None: tmp_path)
    monkeypatch.setenv("SIFTA_DOPAMINE_CRITIC_DISABLE", "1")
    prev = {"owner_continuity": 0.7}
    out = dc.apply_critic_to_bias_vector("x", "good", prev, root=tmp_path)
    assert out["owner_continuity"] == 0.7
    assert not dc.critic_log_path(tmp_path).exists()


def test_process_architect_reaction_updates_critic_gate(tmp_path: Path, monkeypatch) -> None:
    import System.dopamine_reward_loop as drl
    import System.swarm_multi_gate_replay_policy as mg

    monkeypatch.setattr(drl, "_STATE", tmp_path)
    monkeypatch.setattr(drl, "_REWARD_LEDGER", tmp_path / "dopamine_reward_ledger.jsonl")
    monkeypatch.setattr(drl, "_LAST_ACTION_FILE", tmp_path / "last_action_register.json")
    monkeypatch.setattr(drl, "_CONVERSATION", tmp_path / "alice_conversation.jsonl")
    monkeypatch.setattr(dc, "state_dir", lambda explicit=None: tmp_path)
    monkeypatch.setattr(mg, "state_dir", lambda explicit=None: tmp_path)
    monkeypatch.delenv("SIFTA_DOPAMINE_CRITIC_DISABLE", raising=False)

    result = drl.process_architect_reaction(
        user_text="UI thumbs up",
        alice_preceding_text="Short answer.",
        structured_score=1.0,
    )

    assert result is not None
    assert result["marker"] == "UI_BUTTON"
    assert result["critic_result"] is not None
    assert mg.current_gate_state(root=tmp_path)["owner_continuity"] > 0.0


def test_learning_summary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(dc, "state_dir", lambda explicit=None: tmp_path)
    for _ in range(3):
        dc.apply_critic_to_bias_vector(
            "x",
            "good",
            {"co_watch_suggestion": 0.4},
            root=tmp_path,
        )
    s = dc.learning_summary(root=tmp_path)
    assert s["total_feedback"] == 3
    assert s["learning_active"] is True
