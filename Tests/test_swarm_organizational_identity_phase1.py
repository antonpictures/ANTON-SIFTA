import json
import pytest
from pathlib import Path

from System.swarm_organizational_identity import (
    build_current_internal_state_vector,
    snapshot_proto_self,
    load_latest_proto_self_vector,
    compute_revival_score,
    get_identity_ledger_path,
    rehydrate_identity,
)

def test_build_internal_state_vector(tmp_path: Path):
    vec = build_current_internal_state_vector(root=tmp_path)
    expected_keys = {
        "avg_prediction_error_50", "dam_stage", "chronic_dam2_streak",
        "genome_drift_magnitude", "na_level", "valence",
        "pruning_pressure", "ledger_pressure"
    }
    assert set(vec.keys()) == expected_keys


def test_snapshot_proto_self(tmp_path: Path):
    snapshot_proto_self(root=tmp_path, tick_id=123)
    path = get_identity_ledger_path(tmp_path)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    
    row = json.loads(lines[0])
    assert row["kind"] == "PROTO_SELF_SNAPSHOT"
    assert row["tick_id"] == 123
    assert "internal_state_vector" in row
    
    loaded_vec = load_latest_proto_self_vector(root=tmp_path)
    assert loaded_vec is not None
    assert loaded_vec == row["internal_state_vector"]


def test_revival_score_with_identical_vectors():
    vec = {
        "avg_prediction_error_50": 0.5,
        "dam_stage": 1.0,
        "chronic_dam2_streak": 5.0,
        "genome_drift_magnitude": 0.1,
        "na_level": 0.5,
        "valence": 0.0,
        "pruning_pressure": 0.2,
        "ledger_pressure": 0.1
    }
    score = compute_revival_score(
        last_seen_tick=100,
        current_tick=110,
        personality_delta=0.0,
        recent_boots=0,
        current_internal_state=vec,
        last_proto_self_vector=vec
    )
    # Cosine sim of identical vectors is 1.0, so penalty is 0
    # gap penalty is tiny
    assert score >= 0.85


def test_revival_score_with_divergent_vectors():
    vec1 = {
        "avg_prediction_error_50": 0.5,
        "dam_stage": 1.0,
        "chronic_dam2_streak": 5.0,
        "genome_drift_magnitude": 0.1,
        "na_level": 0.5,
        "valence": 0.0,
        "pruning_pressure": 0.2,
        "ledger_pressure": 0.1
    }
    vec2 = {
        "avg_prediction_error_50": 0.0,
        "dam_stage": 0.0,
        "chronic_dam2_streak": 0.0,
        "genome_drift_magnitude": 0.0,
        "na_level": 0.0,
        "valence": 1.0,
        "pruning_pressure": 0.0,
        "ledger_pressure": 0.0
    }
    
    score1 = compute_revival_score(100, 110, 0.0, 0, vec1, vec1)
    score2 = compute_revival_score(100, 110, 0.0, 0, vec1, vec2)
    
    assert score2 < score1


def test_rehydrate_correctly_loads_latest_proto_self(tmp_path: Path):
    # Snapshot first
    snapshot_proto_self(root=tmp_path, tick_id=100)
    
    # Rehydrate
    res = rehydrate_identity(root=tmp_path, current_tick=110)
    assert res is not None
    # Because there's a proto_self snapshot, compute_revival_score should have been called
    # with the vectors and not raised any errors.
    assert "revival_score" in res
