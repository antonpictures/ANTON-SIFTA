import json
import tempfile
from pathlib import Path

import pytest
from System.swarm_endocrine_system import EndocrineSystem

@pytest.fixture
def endo_env():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)

def test_initial_state(endo_env):
    endo = EndocrineSystem(root=str(endo_env))
    # By default, thyroid or oxytocin is dominant at 0.5
    assert endo.hormones["oxytocin"] == 0.5
    assert endo.hormones["thyroid"] == 0.5
    assert endo.get_organism_mode() == "BASELINE_MAINTENANCE"

def test_adrenaline_spike_triggers_freeze(endo_env):
    endo = EndocrineSystem(root=str(endo_env))
    state = endo.tick({"threat_detected": True})
    
    assert state.adrenaline == 1.0
    assert state.organism_mode == "FREEZE_OR_FLEE"

def test_cortisol_rises_on_errors_triggers_caution(endo_env):
    endo = EndocrineSystem(root=str(endo_env))
    
    # Needs multiple ticks of high errors to surpass 0.7
    for _ in range(6):
        state = endo.tick({"errors_last_tick": 2})
        
    assert state.cortisol > 0.7
    assert state.organism_mode == "PRUNE_AND_CAUTION"

def test_oxytocin_rises_on_owner_interaction(endo_env):
    endo = EndocrineSystem(root=str(endo_env))
    
    for _ in range(3):
        state = endo.tick({"owner_interactions": 1})
        
    assert state.oxytocin > 0.7
    assert state.organism_mode == "SOCIAL_BONDING"

def test_melatonin_accumulates_over_time_triggers_sleep(endo_env):
    endo = EndocrineSystem(root=str(endo_env))
    
    # 16 hours awake -> melatonin ~ 0.88
    state = endo.tick({"time_since_sleep_hrs": 16.0})
    
    assert state.melatonin > 0.8
    assert state.organism_mode == "REQUIRE_SLEEP"
    
def test_thyroid_adjusts_to_compute_load(endo_env):
    endo = EndocrineSystem(root=str(endo_env))
    
    # Consistently high compute load raises baseline thyroid
    for _ in range(5):
        state = endo.tick({"compute_load": 1.0})
        
    assert state.thyroid > 0.7
    assert state.organism_mode == "HIGH_METABOLISM_GROWTH"

def test_ledger_persistence(endo_env):
    endo = EndocrineSystem(root=str(endo_env))
    endo.tick({"threat_detected": True})
    
    with open(endo.ledger, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
        
    assert len(rows) == 1
    assert rows[0]["organism_mode"] == "FREEZE_OR_FLEE"
    assert rows[0]["adrenaline"] == 1.0
