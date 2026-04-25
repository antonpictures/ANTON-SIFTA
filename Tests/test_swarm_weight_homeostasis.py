from __future__ import annotations

import numpy as np
import pytest

from System.swarm_unified_field_engine import UnifiedFieldConfig, UnifiedFieldEngine
from System.swarm_weight_homeostasis import (
    HomeostasisConfig,
    WeightHomeostasis,
    regulate_tuning_row,
)


def test_weight_homeostasis_corrects_dominant_channel():
    homeo = WeightHomeostasis(
        n_fields=4,
        cfg=HomeostasisConfig(target_entropy=0.95, correction_rate=0.4, drift_decay=1.0),
    )
    weights = np.array([5.0, 0.05, 0.05, 0.05], dtype=np.float32)

    regulated = homeo.regulate(weights)

    assert regulated[0] < weights[0]
    assert regulated[1] > weights[1]
    assert homeo.last_entropy < homeo.cfg.target_entropy
    assert np.all(regulated >= homeo.cfg.min_weight)


def test_weight_homeostasis_decays_drift_when_entropy_is_healthy():
    homeo = WeightHomeostasis(
        n_fields=4,
        cfg=HomeostasisConfig(target_entropy=0.5, correction_rate=0.4, drift_decay=0.5),
    )
    homeo.drift[:] = np.array([0.2, -0.1, -0.05, -0.05], dtype=np.float32)

    regulated = homeo.regulate(np.ones(4, dtype=np.float32))

    assert homeo.last_entropy > homeo.cfg.target_entropy
    assert homeo.drift[0] == pytest.approx(0.1)
    assert regulated[0] == pytest.approx(1.1)


def test_weight_homeostasis_regulates_tuning_row_and_applies_to_engine():
    row = {
        "best_weights": {
            "alpha_memory": 5.0,
            "beta_prediction": 0.05,
            "salience_weight": 0.05,
            "delta_danger": 0.05,
            "gamma_repair": 0.75,
            "crowding_weight": 0.55,
        }
    }
    homeo = WeightHomeostasis(
        n_fields=4,
        cfg=HomeostasisConfig(target_entropy=0.95, correction_rate=0.4, drift_decay=1.0),
    )
    safe_weights = regulate_tuning_row(row, homeo)
    engine = UnifiedFieldEngine(UnifiedFieldConfig(grid_size=16, diffusion=0.0))
    applied = homeo.apply_to_unified_field(engine, row["best_weights"])

    assert set(safe_weights) == {"alpha_memory", "beta_prediction", "salience_weight", "delta_danger"}
    assert safe_weights["alpha_memory"] < row["best_weights"]["alpha_memory"]
    assert safe_weights["beta_prediction"] > row["best_weights"]["beta_prediction"]
    assert applied["alpha_memory"] < row["best_weights"]["alpha_memory"]
    assert applied["gamma_repair"] == pytest.approx(0.75)


def test_weight_homeostasis_validation():
    with pytest.raises(ValueError, match="n_fields"):
        WeightHomeostasis(n_fields=1)
    with pytest.raises(ValueError, match="target_entropy"):
        HomeostasisConfig(target_entropy=1.5)
    with pytest.raises(ValueError, match="weights must match"):
        WeightHomeostasis(n_fields=4).regulate(np.ones(3, dtype=np.float32))
    with pytest.raises(ValueError, match="best_weights"):
        regulate_tuning_row({})
