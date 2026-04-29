import json
import tempfile
from pathlib import Path

import pytest
from System.swarm_theory_of_mind import SwarmTheoryOfMind

@pytest.fixture
def btom_env():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)

def test_btom_stress_inference(btom_env):
    btom = SwarmTheoryOfMind(state_dir=str(btom_env))
    
    # Send a short, all-caps message (high stress)
    modulation = btom.update_architect_state("FIX THIS BUG NOW", {})
    
    # Verify the dominant state became high_stress and verbosity plummeted
    idx = btom.prior.index(max(btom.prior))
    dominant_state = btom.states[idx]
    assert dominant_state == "high_stress"
    assert modulation["verbosity"] == "absolute_minimum"
    assert modulation["tool_autonomy"] == "low"

def test_btom_focus_inference_with_code(btom_env):
    btom = SwarmTheoryOfMind(state_dir=str(btom_env))
    
    # Send a message containing code (deep focus)
    modulation = btom.update_architect_state("I am building this:\n```python\nprint('hello')\n```", {"contains_code": True})
    
    idx = btom.prior.index(max(btom.prior))
    dominant_state = btom.states[idx]
    
    assert dominant_state == "deep_focus"
    assert modulation["verbosity"] == "minimal"
    assert modulation["tool_autonomy"] == "high"

def test_btom_leisure_inference(btom_env):
    btom = SwarmTheoryOfMind(state_dir=str(btom_env))
    
    # Send a long, relaxed message (leisure chat)
    msg = "I was thinking about how biological systems use stigmergy to coordinate over long periods of time. What are your thoughts on this? It is quite fascinating."
    modulation = btom.update_architect_state(msg, {})
    
    idx = btom.prior.index(max(btom.prior))
    dominant_state = btom.states[idx]
    
    assert dominant_state == "leisure_chat"
    assert modulation["verbosity"] == "normal"
    assert modulation["tone"] == "conversational"

def test_btom_ledger_persistence(btom_env):
    btom1 = SwarmTheoryOfMind(state_dir=str(btom_env))
    btom1.update_architect_state("KILL THE PROCESS NOW", {})
    
    # Verify high stress
    assert btom1.states[btom1.prior.index(max(btom1.prior))] == "high_stress"
    
    # Re-instantiate to check if the new Prior was loaded from the ledger
    btom2 = SwarmTheoryOfMind(state_dir=str(btom_env))
    
    assert btom2.states[btom2.prior.index(max(btom2.prior))] == "high_stress"
