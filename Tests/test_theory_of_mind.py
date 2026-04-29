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


def test_btom_trace_has_integrity_and_no_certainty_claim(btom_env):
    btom = SwarmTheoryOfMind(state_dir=str(btom_env))
    modulation = btom.update_architect_state("FIX THE CRYPTOPHYSICS NOW", {})

    row = json.loads((btom_env / "theory_of_mind.jsonl").read_text(encoding="utf-8").splitlines()[-1])

    assert row["schema"] == "SIFTA_THEORY_OF_MIND_TRACE_V1"
    assert row["integrity"]
    assert row["features"]["urgent_terms"] >= 1
    assert modulation["certainty"] == "hypothesis"
    assert modulation["external_action_policy"] == "explicit_owner_consent_required"


def test_btom_external_send_request_blocks_autonomy_even_in_focus(btom_env):
    btom = SwarmTheoryOfMind(state_dir=str(btom_env))

    modulation = btom.update_architect_state(
        "Please send this update:\n```json\n{\"tool\":\"send_whatsapp\"}\n```",
        {"contains_code": True, "external_send_requested": True},
    )

    assert modulation["tool_autonomy"] == "low"
    assert modulation["external_action_policy"] == "blocked_until_effector_consent_receipt"


def test_btom_stress_prior_can_relax_after_context(btom_env):
    btom = SwarmTheoryOfMind(state_dir=str(btom_env), prior_decay=0.2)
    btom.update_architect_state("KILL THE PROCESS NOW", {})
    modulation = btom.update_architect_state(
        "I was thinking about how biological systems coordinate through receipts and memory. What are your thoughts on that pattern?",
        {},
    )

    assert modulation["inferred_state"] in {"leisure_chat", "deep_focus"}
    assert modulation["tone"] in {"conversational", "clinical_and_exact"}
