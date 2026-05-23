"""Event 126 - transfer evaluator proof receipts."""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_transfer_evaluator as te


def test_infers_source_skills() -> None:
    skills = te.infer_source_skills(
        "New task: prove a YouTube science video is background media while George asks a question."
    )
    assert "co_watch_suggestion" in skills
    assert "media_context_sensitivity" in skills
    assert "question_followup" in skills


def test_replay_informed_policy_beats_baseline_on_novel_task(tmp_path: Path) -> None:
    replay = {
        "co_watch_suggestion": 0.8,
        "media_context_sensitivity": 0.7,
        "question_followup": 0.6,
        "owner_continuity": 0.5,
    }
    row = te.evaluate_transfer_trial(
        "Novel task: while a YouTube documentary plays, answer George's live question without treating him as ambient audio.",
        replay_gates=replay,
        root=tmp_path,
    )

    assert row["truth_label"] == "GENERALIZATION_TRIAL"
    assert row["kind"] == "TRANSFER_TEST"
    assert row["novel_task"] is True
    assert row["transfer_gain"] > 0.0
    assert row["baseline_reward"] < row["transfer_reward"]
    assert "media_context_sensitivity" in row["source_skills"]

    path = te.transfer_log_path(tmp_path)
    written = json.loads(path.read_text(encoding="utf-8").strip())
    assert written["task_id"] == row["task_id"]
    assert written["transfer_gain"] == row["transfer_gain"]


def test_second_same_task_is_not_novel(tmp_path: Path) -> None:
    task = "Novel task: compare Alice's schedule with George's schedule and explain the mismatch."
    te.evaluate_transfer_trial(
        task,
        replay_gates={"owner_continuity": 0.8, "session_persistence": 0.7},
        root=tmp_path,
    )
    row = te.evaluate_transfer_trial(
        task,
        replay_gates={"owner_continuity": 0.8, "session_persistence": 0.7},
        root=tmp_path,
    )
    assert row["novel_task"] is False
    assert te.is_novel_task(task, root=tmp_path) is False


def test_architect_reward_can_record_failed_transfer(tmp_path: Path) -> None:
    row = te.evaluate_transfer_trial(
        "Novel task: use co-watch memory to classify a finance spreadsheet.",
        replay_gates={"co_watch_suggestion": 0.9},
        architect_reward=-0.4,
        actual_outcome={"owner_said": "wrong skill"},
        root=tmp_path,
    )
    assert row["transfer_reward"] == -0.4
    assert row["transfer_gain"] < 0.0
    assert row["actual_outcome"]["owner_said"] == "wrong skill"


def test_aggregate_stats_proves_positive_mean(tmp_path: Path) -> None:
    te.evaluate_transfer_trial(
        "Novel task: video plus live owner question",
        replay_gates={"co_watch_suggestion": 0.8, "question_followup": 0.8},
        root=tmp_path,
    )
    te.evaluate_transfer_trial(
        "Novel task: owner schedule plus overnight boot continuity",
        replay_gates={"owner_continuity": 0.8, "session_persistence": 0.8},
        root=tmp_path,
    )
    stats = te.aggregate_transfer_stats(root=tmp_path)
    assert stats["trial_count"] == 2
    assert stats["mean_transfer_gain"] > 0.0
    assert stats["positive_rate"] == 1.0
    assert stats["transfer_proven"] is True
    assert "TRANSFER EVALUATOR" in te.summary_for_prompt(root=tmp_path)


def test_disable_skips_ledger(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SIFTA_TRANSFER_EVALUATOR_DISABLE", "1")
    row = te.evaluate_transfer_trial(
        "Novel task: disabled evaluator should compute but not write.",
        replay_gates={"research_depth": 0.8},
        root=tmp_path,
    )
    assert row["truth_label"] == "GENERALIZATION_TRIAL"
    assert not te.transfer_log_path(tmp_path).exists()
