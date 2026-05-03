"""Event 128 - cerebellar forward model receipts."""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_cerebellar_forward_model as c


def test_predict_defaults_without_writing(tmp_path: Path) -> None:
    pred = c.predict("bash", root=tmp_path)
    assert pred["truth_label"] == "CEREBELLAR_FORWARD_PREDICTION"
    assert pred["predicted_latency_s"] == 1.0
    assert pred["predicted_success"] == 0.75
    assert pred["predicted_cost"] == 0.0
    assert pred["expected_observation"] is None
    assert not c.trace_path(tmp_path).exists()


def test_observe_updates_latency_success_cost_and_observation(tmp_path: Path) -> None:
    row = c.observe(
        "bash",
        started_at=98.0,
        success=True,
        root=tmp_path,
        actual_cost=0.4,
        actual_observation={"stdout_tail": "ok"},
        now=100.0,
    )

    assert row["truth_label"] == "CEREBELLAR_FORWARD_OBSERVATION"
    assert row["kind"] == "CEREBELLAR_PREDICTION"
    assert row["latency_error"] == 1.0
    updated = row["updated_tool_model"]["bash"]
    assert updated["latency_mu"] == 2.0
    assert updated["success_rate"] == 1.0
    assert updated["cost_mu"] == 0.4
    assert updated["expected_observation"] == {"stdout_tail": "ok"}
    assert updated["n"] == 1

    pred = c.predict("bash", root=tmp_path)
    assert pred["predicted_latency_s"] == 2.0
    assert pred["predicted_success"] == 1.0
    assert pred["predicted_cost"] == 0.4
    assert pred["expected_observation"] == {"stdout_tail": "ok"}

    trace = json.loads(c.trace_path(tmp_path).read_text(encoding="utf-8").strip())
    assert trace["trace_id"]
    assert trace["truth_label"] == "CEREBELLAR_FORWARD_OBSERVATION"


def test_second_observation_uses_ema(tmp_path: Path) -> None:
    c.observe("tool", started_at=99.0, success=True, root=tmp_path, now=100.0)
    row = c.observe("tool", started_at=96.0, success=False, root=tmp_path, now=100.0)

    updated = row["updated_tool_model"]["tool"]
    assert row["alpha"] == 0.5
    assert updated["latency_mu"] == 2.5
    assert updated["success_rate"] == 0.5
    assert updated["n"] == 2


def test_disable_returns_prediction_error_without_writing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SIFTA_CEREBELLUM_DISABLE", "1")
    row = c.observe("blocked", started_at=0.0, success=True, root=tmp_path, now=2.0)
    assert row["disabled"] is True
    assert row["latency_error"] == 1.0
    assert not c.state_path(tmp_path).exists()
    assert not c.trace_path(tmp_path).exists()


def test_predict_can_write_preflight_receipt(tmp_path: Path) -> None:
    pred = c.predict("camera", root=tmp_path, write_ledger=True)
    trace = json.loads(c.trace_path(tmp_path).read_text(encoding="utf-8").strip())
    assert trace["trace_id"] == pred["trace_id"]
    assert trace["truth_label"] == "CEREBELLAR_FORWARD_PREDICTION"


def test_context_conditioned_models_do_not_bleed(tmp_path: Path) -> None:
    high_load_code = {
        "cpu_load_bucket": "high",
        "task_family": "code_repair",
        "concurrent_tools": 2,
    }
    idle_media = {
        "cpu_load_bucket": "idle",
        "task_family": "media_research",
        "concurrent_tools": 0,
    }

    high_row = c.observe(
        "bash",
        started_at=96.0,
        success=True,
        root=tmp_path,
        now=100.0,
        context_features=high_load_code,
    )
    idle_row = c.observe(
        "bash",
        started_at=99.0,
        success=True,
        root=tmp_path,
        now=100.0,
        context_features=idle_media,
    )

    high_pred = c.predict("bash", root=tmp_path, context_features=high_load_code)
    idle_pred = c.predict("bash", root=tmp_path, context_features=idle_media)
    plain_pred = c.predict("bash", root=tmp_path)

    assert high_row["model_key"] != idle_row["model_key"]
    assert high_pred["context_hash"]
    assert idle_pred["context_hash"]
    assert high_pred["predicted_latency_s"] == 4.0
    assert idle_pred["predicted_latency_s"] == 1.0
    assert plain_pred["predicted_latency_s"] == 1.0
