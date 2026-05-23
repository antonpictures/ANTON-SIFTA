from System.swarm_causal_intervention_loop import (
    causal_intervention_log_path,
    compute_effect_size,
    run_intervention_trial,
    summary_for_prompt,
    tail_intervention_rows,
)


def test_compute_effect_size_positive():
    assert compute_effect_size({"reward": 0.2}, {"reward": 0.7}) == 0.5


def test_intervention_trial_positive_effect_writes_receipt(tmp_path):
    row = run_intervention_trial(
        variable="co_watch_suggestion",
        intervention_value=0.7,
        baseline_state={"gate": 0.1},
        intervened_state={"gate": 0.7},
        baseline_outcome={"reward": 0.2},
        intervention_outcome={"reward": 0.6},
        blocked_backdoors=["same_video"],
        assumptions=["owner feedback comparable"],
        root=tmp_path,
    )

    assert row["truth_label"] == "CAUSAL_INTERVENTION_TRIAL"
    assert row["direction"] == "positive"
    assert row["effect_size"] == 0.4
    assert row["do"] == {"co_watch_suggestion": 0.7}
    assert causal_intervention_log_path(tmp_path).exists()


def test_intervention_trial_negative_effect(tmp_path):
    row = run_intervention_trial(
        variable="question_followup",
        intervention_value=0.9,
        baseline_state={},
        intervened_state={},
        baseline_outcome={"reward": 0.8},
        intervention_outcome={"reward": 0.1},
        root=tmp_path,
    )

    assert row["direction"] == "negative"
    assert row["effect_size"] == -0.7


def test_intervention_disable_writes_no_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_CAUSAL_LOOP_DISABLE", "1")
    row = run_intervention_trial(
        variable="x",
        intervention_value=1,
        baseline_state={},
        intervened_state={},
        baseline_outcome={"reward": 0.0},
        intervention_outcome={"reward": 1.0},
        root=tmp_path,
    )

    assert row["disabled"] is True
    assert not causal_intervention_log_path(tmp_path).exists()


def test_intervention_tail_and_summary(tmp_path):
    run_intervention_trial(
        variable="owner_continuity",
        intervention_value=0.8,
        baseline_state={},
        intervened_state={},
        baseline_outcome={"reward": 0.1},
        intervention_outcome={"reward": 0.3},
        root=tmp_path,
    )

    assert len(tail_intervention_rows(root=tmp_path)) == 1
    assert "CAUSAL INTERVENTION LOOP" in summary_for_prompt(root=tmp_path)
