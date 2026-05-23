from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from System.canonical_schemas import LEDGER_SCHEMAS
from System.swarm_unified_field_engine import (
    ATTENTION,
    DANGER,
    CROWDING,
    MEMORY,
    PREDICTION,
    REPAIR,
    SALIENCE,
    UnifiedFieldConfig,
    UnifiedFieldEngine,
    append_experiment_row,
    proof_of_property,
    run_unified_field_experiment,
)
from System.swarm_unified_field import (
    UnifiedFieldConfig as SubstrateConfig,
    UnifiedStigmergicField,
)


def test_total_field_combines_channels_with_danger_negative():
    engine = UnifiedFieldEngine(UnifiedFieldConfig(grid_size=16, diffusion=0.0))
    center = np.array([0.5, 0.5], dtype=np.float32)
    i, j = engine._idx(center)

    engine.fields[MEMORY, i, j] = 2.0
    engine.fields[PREDICTION, i, j] = 1.0
    engine.fields[REPAIR, i, j] = 1.0
    engine.fields[DANGER, i, j] = 3.0

    expected = (
        engine.cfg.alpha_memory * 2.0
        + engine.cfg.beta_prediction
        + engine.cfg.gamma_repair
        - engine.cfg.delta_danger * 3.0
    )
    assert engine.total_field()[i, j] == pytest.approx(expected)


def test_simple_substrate_api_collapses_channels_and_senses_one_position():
    field = UnifiedStigmergicField(
        SubstrateConfig(
            grid_size=16,
            diffusion=0.0,
            w_memory=1.0,
            w_prediction=0.8,
            w_attention=0.6,
            w_danger=1.2,
        )
    )
    pos = np.array([0.5, 0.5], dtype=np.float32)

    field.deposit(pos, "memory", 2.0)
    field.deposit(pos, "prediction", 1.0)
    field.deposit(pos, "attention", 0.5)
    field.deposit(pos, "danger", 0.25)
    total, channels = field.sense(pos)

    assert channels == pytest.approx((2.0, 1.0, 0.5, 0.25))
    assert total == pytest.approx(2.0 + 0.8 + 0.3 - 0.3)
    assert field.attention.max() == pytest.approx(field.salience.max())
    assert field.fields[ATTENTION].max() > 0.0
    assert field.combined().shape == (16, 16)
    assert field.glyph()


def test_simple_substrate_gradient_points_away_from_danger_and_no_arg_step_decays():
    field = UnifiedStigmergicField(SubstrateConfig(grid_size=32, diffusion=0.0, decay=0.5))
    here = np.array([0.5, 0.5], dtype=np.float32)
    right = np.array([0.53, 0.5], dtype=np.float32)
    left_danger = np.array([0.47, 0.5], dtype=np.float32)

    field.deposit(right, "memory", 4.0)
    field.deposit(left_danger, "danger", 4.0)
    grad = field.gradient(here)
    before = float(field.memory.sum() + field.danger.sum())
    field.step()
    after = float(field.memory.sum() + field.danger.sum())

    assert grad[0] > 0.0
    assert after < before


def test_external_update_couples_salience_and_crowding_channels():
    engine = UnifiedFieldEngine(
        UnifiedFieldConfig(
            grid_size=32,
            diffusion=0.0,
            crowding_deposit=2.0,
            crowding_weight=1.0,
        )
    )
    memory = np.ones((32, 32), dtype=np.float32)
    salience = np.zeros((32, 32), dtype=np.float32)
    salience[24, 24] = 1.0
    crowded = np.array([[0.50, 0.50], [0.50, 0.50], [0.50, 0.50]], dtype=np.float32)

    total = engine.update(memory=memory, salience=salience, positions=crowded)
    peak_x, peak_y, peak_value = engine.peak()
    crowded_idx = engine._idx(np.array([0.50, 0.50], dtype=np.float32))
    open_idx = engine._idx(np.array([0.10, 0.10], dtype=np.float32))

    assert total.shape == (32, 32)
    assert engine.fields[SALIENCE].max() > 0.0
    assert engine.fields[CROWDING].max() > 0.0
    assert float(engine.total[crowded_idx]) < float(engine.total[open_idx])
    assert 0.70 <= peak_x <= 0.85
    assert 0.70 <= peak_y <= 0.85
    assert peak_value > 0.0
    assert engine.glyph("salience")
    assert engine.glyph("crowding")


def test_step_writes_memory_prediction_and_repair_reduces_danger():
    engine = UnifiedFieldEngine(UnifiedFieldConfig(grid_size=32, diffusion=0.0, prediction_horizon=4))
    first = np.array([[0.3, 0.3]], dtype=np.float32)
    second = np.array([[0.34, 0.34]], dtype=np.float32)
    engine.inject_danger(second, radius=0.05, amount=2.0)
    danger_before = float(engine.fields[DANGER].sum())

    engine.step(first)
    rewards = engine.step(second)

    assert engine.fields[MEMORY].max() > 0.0
    assert engine.fields[PREDICTION].max() > 0.0
    assert engine.fields[REPAIR].max() > 0.0
    assert float(engine.fields[DANGER].sum()) < danger_before
    assert rewards.shape == (1,)


def test_policy_gradient_moves_toward_positive_field():
    engine = UnifiedFieldEngine(UnifiedFieldConfig(grid_size=32, diffusion=0.0))
    engine.inject_memory(np.array([[0.8, 0.5]], dtype=np.float32), radius=0.10, amount=5.0)

    action = engine.policy_actions(np.array([[0.65, 0.5]], dtype=np.float32))[0]

    assert action[0] > 0.0


def test_active_inference_selects_low_expected_free_energy_action():
    engine = UnifiedFieldEngine(UnifiedFieldConfig(grid_size=32, diffusion=0.0, step_size=0.05))
    engine.inject_memory(np.array([[0.75, 0.5]], dtype=np.float32), radius=0.08, amount=4.0)
    engine.inject_danger(np.array([[0.25, 0.5]], dtype=np.float32), radius=0.08, amount=4.0)
    positions = np.array([[0.50, 0.50]], dtype=np.float32)

    action = engine.active_inference_actions(
        positions,
        candidate_actions=np.array([[0.10, 0.0], [-0.10, 0.0], [0.0, 0.0]], dtype=np.float32),
    )[0]

    assert action[0] > 0.0


def test_experiment_row_matches_schema_and_writes_jsonl(tmp_path: Path):
    row = run_unified_field_experiment(
        n_agents=30,
        steps=25,
        seed=123,
        cfg=UnifiedFieldConfig(grid_size=40),
    )
    ledger = tmp_path / "unified_field_engine.jsonl"
    append_experiment_row(row, ledger_path=ledger)

    written = json.loads(ledger.read_text(encoding="utf-8"))
    assert set(row) == LEDGER_SCHEMAS["unified_field_engine.jsonl"]
    assert written["event"] == "unified_field_engine_run"
    assert written["path_efficiency"] > 0.0
    assert written["repair_total"] > 0.0
    assert written["prediction_total"] > 0.0


def test_validation_and_proof():
    with pytest.raises(ValueError, match="grid_size"):
        UnifiedFieldEngine(UnifiedFieldConfig(grid_size=1))
    with pytest.raises(ValueError, match="positions"):
        UnifiedFieldEngine().step(np.array([0.1, 0.2], dtype=np.float32))

    assert proof_of_property() is True
