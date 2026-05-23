import json
import tempfile
from pathlib import Path

import pytest
from System.swarm_parasympathetic_loop import ParasympatheticRecoveryLoop
from System.swarm_endocrine_system import EndocrineSystem

@pytest.fixture
def recovery_env():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)

def test_parasympathetic_downshift_from_adrenaline(recovery_env):
    loop = ParasympatheticRecoveryLoop(root=str(recovery_env))
    
    # Mock Endocrine escalated state (Adrenaline)
    state = {
        "adrenaline": 1.0,
        "cortisol": 0.2,
        "organism_mode": "FREEZE_OR_FLEE"
    }
    loop.endocrine_file.write_text(json.dumps(state))
    
    # Mock Vagus Armed state
    loop.vagus_mode_file.write_text(json.dumps({"mode": "armed"}))
    
    # 1. Threat is still recent (30s) -> No downshift
    assert loop.tick_recovery(time_since_last_threat_sec=30, time_since_last_error_sec=1000) is None
    
    # 2. Threat decayed (120s) -> Force downshift
    downshift = loop.tick_recovery(time_since_last_threat_sec=120, time_since_last_error_sec=1000)
    
    assert downshift is not None
    assert downshift.pre_downshift_mode == "FREEZE_OR_FLEE"
    assert downshift.post_downshift_mode == "BASELINE_MAINTENANCE"
    assert downshift.adrenaline_reduced_by == 1.0
    assert downshift.vagus_disarmed is True
    assert downshift.reason == "threat_decay_complete_parasympathetic_brake"
    
    # 3. Verify Endocrine file was rewritten correctly
    new_state = json.loads(loop.endocrine_file.read_text())
    assert new_state["adrenaline"] == 0.0
    assert new_state["organism_mode"] == "BASELINE_MAINTENANCE"
    assert new_state["parasympathetic_downshift_id"] == downshift.recovery_id
    
    # 4. Verify Vagus file was rewritten correctly
    new_vagus = json.loads(loop.vagus_mode_file.read_text())
    assert new_vagus["mode"] == "dry_run"
    
    # 5. Verify ledger trace exists
    with open(loop.ledger, "r") as f:
        rows = f.readlines()
        assert len(rows) == 1

def test_parasympathetic_downshift_from_cortisol(recovery_env):
    loop = ParasympatheticRecoveryLoop(root=str(recovery_env))
    
    # Mock Endocrine escalated state (Cortisol)
    state = {
        "adrenaline": 0.0,
        "cortisol": 0.8,
        "organism_mode": "PRUNE_AND_CAUTION"
    }
    loop.endocrine_file.write_text(json.dumps(state))
    
    # 1. Errors still recent (100s) -> No downshift
    assert loop.tick_recovery(time_since_last_threat_sec=1000, time_since_last_error_sec=100) is None
    
    # 2. Errors decayed (400s) -> Force downshift
    downshift = loop.tick_recovery(time_since_last_threat_sec=1000, time_since_last_error_sec=400)
    
    assert downshift is not None
    assert downshift.pre_downshift_mode == "PRUNE_AND_CAUTION"
    assert downshift.cortisol_reduced_by == pytest.approx(0.7)
    
    new_state = json.loads(loop.endocrine_file.read_text())
    assert new_state["cortisol"] == pytest.approx(0.1)

def test_endocrine_tick_autonomically_downshifts_after_threat_window(recovery_env):
    endo = EndocrineSystem(root=str(recovery_env))

    spike = endo.tick({"threat_detected": True, "_now": 1_000.0})
    assert spike.organism_mode == "FREEZE_OR_FLEE"

    still_hot = endo.tick({"_now": 1_030.0})
    assert still_hot.adrenaline > 0.2
    assert not (recovery_env / "parasympathetic_recovery.jsonl").exists()

    recovered = endo.tick({"_now": 1_061.0})
    assert recovered.organism_mode == "BASELINE_MAINTENANCE"
    assert recovered.adrenaline == 0.0
    assert recovered.parasympathetic_downshift_id.startswith("recov_")

    rows = [json.loads(line) for line in (recovery_env / "parasympathetic_recovery.jsonl").read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["reason"] == "threat_decay_complete_parasympathetic_brake"

def test_endocrine_tick_autonomically_downshifts_after_error_window(recovery_env):
    endo = EndocrineSystem(root=str(recovery_env))

    stressed = endo.tick({"errors_last_tick": 6, "_now": 2_000.0})
    assert stressed.organism_mode == "PRUNE_AND_CAUTION"

    still_cautious = endo.tick({"_now": 2_100.0})
    assert still_cautious.organism_mode == "PRUNE_AND_CAUTION"

    recovered = endo.tick({"_now": 2_301.0})
    assert recovered.organism_mode == "BASELINE_MAINTENANCE"
    assert recovered.cortisol == pytest.approx(0.1)
    assert recovered.parasympathetic_downshift_id.startswith("recov_")
