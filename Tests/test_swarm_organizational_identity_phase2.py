import json
from pathlib import Path

from System.swarm_organizational_identity import (
    record_core_self_interaction,
    get_recent_core_self_context,
    build_core_self_continuity_on_revival,
    rehydrate_identity,
    get_identity_ledger_path,
)

def test_record_core_self_interaction_high_salience(tmp_path: Path):
    v1 = {"na_level": 0.5, "valence": 0.0}
    v2 = {"na_level": 0.8, "valence": -0.5}
    
    res = record_core_self_interaction(
        interaction_type="ARBITER_DECISION",
        salience=0.8,
        proto_self_before=v1,
        proto_self_after=v2,
        summary="High risk action",
        root=tmp_path,
        tick_id=123
    )
    
    assert res is not None
    assert res["interaction_type"] == "ARBITER_DECISION"
    assert res["salience"] == 0.8
    assert res["proto_self_delta"]["na_level"] == 0.3
    assert res["proto_self_delta"]["valence"] == -0.5
    
    # Verify in ledger
    path = get_identity_ledger_path(tmp_path)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    row = json.loads(lines[-1])
    assert row["kind"] == "CORE_SELF_INTERACTION"


def test_record_core_self_interaction_low_salience_filtered(tmp_path: Path):
    v1 = {"na_level": 0.5}
    v2 = {"na_level": 0.51}
    
    res = record_core_self_interaction(
        interaction_type="ARBITER_DECISION",
        salience=0.3,
        proto_self_before=v1,
        proto_self_after=v2,
        summary="Low risk action",
        root=tmp_path,
        tick_id=124
    )
    
    assert res is None
    
    path = get_identity_ledger_path(tmp_path)
    if path.exists():
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        for line in lines:
            row = json.loads(line)
            assert row["kind"] != "CORE_SELF_INTERACTION"


def test_build_core_self_continuity_on_revival(tmp_path: Path):
    v1 = {"na_level": 0.5}
    v2 = {"na_level": 0.9}
    
    record_core_self_interaction(
        interaction_type="CAUSAL_PROBE",
        salience=0.9,
        proto_self_before=v1,
        proto_self_after=v2,
        summary="Intervention X",
        root=tmp_path,
        tick_id=100
    )
    
    cont = build_core_self_continuity_on_revival(root=tmp_path)
    assert cont["was_mid_interaction"] is True
    assert cont["last_interaction_type"] == "CAUSAL_PROBE"
    assert cont["last_interaction_summary"] == "Intervention X"
    assert cont["proto_self_shift"] == {"na_level": 0.4}


def test_rehydrate_incorporates_core_self_continuity(tmp_path: Path):
    v1 = {"na_level": 0.5}
    v2 = {"na_level": 0.9}
    
    record_core_self_interaction(
        interaction_type="CAUSAL_PROBE",
        salience=0.9,
        proto_self_before=v1,
        proto_self_after=v2,
        summary="Intervention Y",
        root=tmp_path,
        tick_id=100
    )
    
    res = rehydrate_identity(root=tmp_path, current_tick=110)
    assert "core_self_continuity" in res
    assert res["core_self_continuity"]["was_mid_interaction"] is True
    assert res["core_self_continuity"]["last_interaction_type"] == "CAUSAL_PROBE"
    
    # Ensure revival score took a slight penalty for being interrupted mid-interaction
    # Normal revival score with these parameters (no gap, no personality shift) is ~0.945 or 1.0.
    # With a 0.05 penalty, it should be lower.
    assert res["revival_score"] < 1.0
