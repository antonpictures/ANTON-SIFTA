from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from System.canonical_schemas import LEDGER_SCHEMAS
from System.swarm_evolutionary_rl import (
    EvolutionaryFieldTuner,
    append_tuning_row,
    apply_tuned_weights,
    proof_of_property,
)
from System.swarm_unified_field_engine import MEMORY, UnifiedFieldConfig, UnifiedFieldEngine


def test_unified_field_weights_can_be_updated_without_parallel_substrate():
    engine = UnifiedFieldEngine(UnifiedFieldConfig(grid_size=12, diffusion=0.0))
    engine.fields[MEMORY, 6, 6] = 2.0
    before = float(engine.total_field()[6, 6])

    weights = engine.set_weights({"alpha_memory": 1.5, "delta_danger": 0.2})

    assert weights["alpha_memory"] == 1.5
    assert float(engine.total_field()[6, 6]) > before
    with pytest.raises(ValueError, match="unknown"):
        engine.set_weights({"ghost_weight": 1.0})


def test_evolutionary_tuner_row_matches_schema_and_applies(tmp_path: Path):
    tuner = EvolutionaryFieldTuner(
        UnifiedFieldConfig(grid_size=28, diffusion=0.0),
        seed=77,
        mutation_scale=0.12,
    )

    row = tuner.tune(generations=2, population=3, n_agents=18, steps=12)
    ledger = tmp_path / "evolutionary_rl_meta_cortex.jsonl"
    append_tuning_row(row, ledger_path=ledger)

    saved = json.loads(ledger.read_text(encoding="utf-8"))
    engine = UnifiedFieldEngine(UnifiedFieldConfig(grid_size=28, diffusion=0.0))
    applied = apply_tuned_weights(engine, row)

    assert set(row) == LEDGER_SCHEMAS["evolutionary_rl_meta_cortex.jsonl"]
    assert saved["event"] == "evolutionary_rl_meta_cortex_tune"
    assert row["best_score"] >= row["baseline_score"]
    assert row["reward_delta"] >= 0.0
    assert np.isfinite(list(applied.values())).all()


def test_evolutionary_rl_proof_passes():
    assert proof_of_property() is True
