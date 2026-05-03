"""Event 133 - active inference world model."""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_active_inference_world_model as wm


def _state() -> dict:
    return {"locus": "desk", "energy": 0.4, "attention": 0.6}


def _context(name: str = "conversation") -> dict:
    return {"task_family": name, "cpu_load_bucket": "idle", "hour_bucket": "afternoon"}


def test_predict_defaults_without_writing(tmp_path: Path) -> None:
    pred = wm.predict(_state(), {"name": "ask_followup"}, _context(), root=tmp_path)

    assert pred["truth_label"] == "WORLD_MODEL_PREDICTION"
    assert pred["predicted_next_state"] == {}
    assert pred["predicted_reward"] == 0.0
    assert pred["predicted_harm"] == 0.0
    assert pred["uncertainty"] == 1.0
    assert not wm.trace_path(tmp_path).exists()


def test_observe_updates_prediction_receipt_and_model(tmp_path: Path) -> None:
    row = wm.observe(
        _state(),
        {"name": "ask_followup"},
        _context(),
        {"energy": 0.6, "attention": 0.8},
        reward=0.75,
        harm=0.1,
        cost=0.2,
        root=tmp_path,
        now=100.0,
    )

    assert row["truth_label"] == "WORLD_MODEL_OBSERVATION"
    assert row["reward_error"] == 0.75
    assert row["harm_error"] == 0.1
    assert row["state_prediction_error"] is None
    assert row["updated_model"]["reward_mu"] == 0.75
    assert row["updated_model"]["harm_mu"] == 0.1
    assert row["updated_model"]["cost_mu"] == 0.2
    assert row["updated_model"]["next_state_mu"]["energy"] == 0.6

    pred = wm.predict(_state(), {"name": "ask_followup"}, _context(), root=tmp_path)
    assert pred["predicted_reward"] == 0.75
    assert pred["predicted_harm"] == 0.1
    assert pred["predicted_cost"] == 0.2
    assert pred["predicted_next_state"]["attention"] == 0.8

    trace = json.loads(wm.trace_path(tmp_path).read_text(encoding="utf-8").strip())
    assert trace["trace_id"]
    assert trace["truth_label"] == "WORLD_MODEL_OBSERVATION"


def test_holdout_seed_observation_logs_without_training(tmp_path: Path) -> None:
    context = dict(_context(), holdout_seed="wm-eval-001")
    row = wm.observe(
        _state(),
        {"name": "ask_followup"},
        context,
        {"energy": 0.9, "attention": 0.9},
        reward=0.95,
        root=tmp_path,
        now=101.0,
    )

    assert row["truth_label"] == "WORLD_MODEL_HOLDOUT_OBSERVATION"
    assert row["training_skipped"] is True
    assert row["holdout_seed"] == "wm-eval-001"
    assert wm.load_models(tmp_path) == {}

    trace = json.loads(wm.trace_path(tmp_path).read_text(encoding="utf-8").strip())
    assert trace["guard_reason"] == "holdout_seed_guard"


def test_second_observation_updates_from_prediction_error(tmp_path: Path) -> None:
    action = {"name": "continue_topic"}
    wm.observe(_state(), action, _context(), {"energy": 1.0}, reward=0.5, root=tmp_path, now=1.0)
    row = wm.observe(_state(), action, _context(), {"energy": 3.0}, reward=0.0, root=tmp_path, now=2.0)

    assert row["state_prediction_error"] == 2.0
    assert row["alpha"] == 0.5
    assert row["updated_model"]["next_state_mu"]["energy"] == 2.0
    assert row["updated_model"]["reward_mu"] == 0.25


def test_contexts_do_not_bleed_for_same_state_action(tmp_path: Path) -> None:
    action = {"name": "co_watch_prompt"}
    quiet = _context("quiet_cowatch")
    noisy = _context("noisy_cowatch")

    quiet_row = wm.observe(_state(), action, quiet, {"attention": 0.9}, reward=0.9, root=tmp_path, now=10.0)
    noisy_row = wm.observe(_state(), action, noisy, {"attention": 0.2}, reward=0.1, root=tmp_path, now=11.0)

    quiet_pred = wm.predict(_state(), action, quiet, root=tmp_path)
    noisy_pred = wm.predict(_state(), action, noisy, root=tmp_path)

    assert quiet_row["model_key"] != noisy_row["model_key"]
    assert quiet_pred["predicted_reward"] == 0.9
    assert noisy_pred["predicted_reward"] == 0.1


def test_score_actions_selects_lowest_expected_free_energy(tmp_path: Path) -> None:
    state = _state()
    context = _context()
    good = {"name": "direct_answer"}
    bad = {"name": "generic_menu"}

    wm.observe(state, good, context, {"attention": 0.9}, reward=0.9, harm=0.0, root=tmp_path, now=20.0)
    wm.observe(state, bad, context, {"attention": 0.2}, reward=0.1, harm=0.7, root=tmp_path, now=21.0)

    row = wm.score_actions(state, [bad, good], context, root=tmp_path, now=22.0)

    assert row["truth_label"] == "WORLD_MODEL_ACTION_SCORE"
    assert row["selected_action_name"] == "direct_answer"
    assert row["candidates"][0]["expected_free_energy"] < row["candidates"][1]["expected_free_energy"]
    assert "selected=direct_answer" in wm.summary_for_prompt(root=tmp_path)


def test_disable_returns_observation_without_writing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SIFTA_WORLD_MODEL_DISABLE", "1")
    row = wm.observe(
        _state(),
        {"name": "blocked"},
        _context(),
        {"attention": 1.0},
        reward=1.0,
        root=tmp_path,
        now=30.0,
    )

    assert row["disabled"] is True
    assert row["reward_error"] == 1.0
    assert not wm.model_path(tmp_path).exists()
    assert not wm.trace_path(tmp_path).exists()
