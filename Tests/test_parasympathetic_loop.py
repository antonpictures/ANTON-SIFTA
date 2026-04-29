import json
import tempfile
from pathlib import Path

import pytest
from System.swarm_parasympathetic_loop import ParasympatheticRecoveryLoop

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
    assert downshift.adrenaline_reduced_by == 1.0
    assert downshift.vagus_disarmed is True
    assert downshift.reason == "threat_decay_complete_parasympathetic_brake"
    
    # 3. Verify Endocrine file was rewritten correctly
    new_state = json.loads(loop.endocrine_file.read_text())
    assert new_state["adrenaline"] == 0.0
    assert new_state["organism_mode"] == "BASELINE_MAINTENANCE"
    
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
    assert downshift.cortisol_reduced_by == pytest.approx(0.7)
    
    new_state = json.loads(loop.endocrine_file.read_text())
    assert new_state["cortisol"] == pytest.approx(0.1)
