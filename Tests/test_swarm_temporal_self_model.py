import json
import pytest
from pathlib import Path
from System.swarm_temporal_self_model import TemporalSelfModel


def test_boot_identity_increments(tmp_path):
    """First boot_id is 1; second instantiation reads snapshot and increments."""
    m1 = TemporalSelfModel(root=tmp_path)
    assert m1._boot_id == 1
    m1._persist_snapshot()
    m2 = TemporalSelfModel(root=tmp_path)
    assert m2._boot_id == 2


def test_prediction_written_to_log(tmp_path):
    m = TemporalSelfModel(root=tmp_path)
    ctx = {"gate_norm": 1.8, "wm_pe": 0.12, "owner_dev": 0.03}
    row = m.predict_future_self(ctx, delta_ticks=50)
    assert row["kind"] == "TEMPORAL_SELF_PREDICTION"
    assert row["boot_id"] == 1
    # Log file exists and parses
    lines = [l for l in (tmp_path / "self_model.jsonl").read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["delta_ticks"] == 50


def test_schema_refines_on_update(tmp_path):
    m = TemporalSelfModel(root=tmp_path)
    ctx = {"gate_norm": 1.0, "wm_pe": 0.2}
    # First prediction — no schema yet, returns identity copy
    pred_row = m.predict_future_self(ctx)
    assert pred_row["confidence"] == pytest.approx(0.1, abs=0.01)

    # Observe outcome with deviation
    actual = {"gate_norm": 1.3, "wm_pe": 0.18}
    upd_row = m.update_from_outcome(ctx, actual)
    assert upd_row["pe"] > 0.0
    assert upd_row["schema_refined"] is True

    # Second prediction now uses the schema
    pred_row2 = m.predict_future_self(ctx)
    # confidence should be higher than 0.1 because mean_pe < 1.0
    assert pred_row2["confidence"] > 0.1


def test_identity_summary(tmp_path):
    m = TemporalSelfModel(root=tmp_path)
    ctx = {"gate_norm": 0.5}
    m.update_from_outcome(ctx, {"gate_norm": 0.6})
    summary = m.get_identity_summary()
    assert summary["boot_id"] == 1
    assert summary["known_schemas"] == 1
    assert 0.0 <= summary["mean_self_pe"] <= 1.0
