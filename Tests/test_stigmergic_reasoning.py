import json
import tempfile
from pathlib import Path
from dataclasses import asdict

import pytest
from System.swarm_stigmergic_reasoning import StigmergicReasoner

@pytest.fixture
def reasoning_env():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)

def test_uncertainty_monitoring(reasoning_env):
    reasoner = StigmergicReasoner(root=str(reasoning_env))
    
    # Low confidence -> High uncertainty
    trace = reasoner.decide(
        question="What does the user mean?",
        hypothesis="They want help",
        evidence=["Hello"],
        confidence=0.4, # Uncertainty 0.6
        risk=0.1,
        energy_cost=0.1
    )
    
    assert trace.action == "ASK_OR_OBSERVE_MORE"
    assert trace.reason == "uncertainty_monitoring_triggered"

def test_high_risk_deliberation(reasoning_env):
    reasoner = StigmergicReasoner(root=str(reasoning_env))
    
    # High confidence but high risk
    trace = reasoner.decide(
        question="Should I wipe the database?",
        hypothesis="User asked for reset",
        evidence=["Reset db"],
        confidence=0.95,
        risk=0.9,
        energy_cost=0.1
    )
    
    assert trace.action == "SLOW_REVIEW"
    assert trace.reason == "high_risk_requires_deliberation"

def test_metabolic_cost_deferral(reasoning_env):
    reasoner = StigmergicReasoner(root=str(reasoning_env))
    
    trace = reasoner.decide(
        question="Should I parse the 10GB log file now?",
        hypothesis="It contains the error",
        evidence=["Error missing from recent logs"],
        confidence=0.8,
        risk=0.2,
        energy_cost=0.9 # High energy
    )
    
    assert trace.action == "DEFER_OR_COMPRESS"
    assert trace.reason == "metabolic_cost_high"

def test_evidence_reappraisal(reasoning_env):
    reasoner = StigmergicReasoner(root=str(reasoning_env))
    
    # Initial belief
    t1 = reasoner.decide(
        question="Is user angry?",
        hypothesis="Yes",
        evidence=["CAPS LOCK"],
        confidence=0.8,
        risk=0.1,
        energy_cost=0.1
    )
    
    # Reappraise with contradictory evidence
    t2 = reasoner.reappraise(
        old_trace=asdict(t1),
        new_evidence="Sorry keyboard is broken",
        evidence_strength=0.1 # Very low probability of anger now
    )
    
    # belief_next = 0.8 + 0.35 * (0.1 - 0.8) = 0.8 - 0.245 = 0.555
    assert t2.confidence == pytest.approx(0.555)
    assert len(t2.evidence) == 2
    assert t2.evidence[1] == "Sorry keyboard is broken"
    
def test_trace_ledger_persistence(reasoning_env):
    reasoner = StigmergicReasoner(root=str(reasoning_env))
    
    trace = reasoner.decide(
        question="Test?",
        hypothesis="Yes",
        evidence=["A"],
        confidence=0.9,
        risk=0.1,
        energy_cost=0.1
    )
    
    with open(reasoner.ledger, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        loaded = json.loads(lines[0])
        assert loaded["trace_hash"] == trace.trace_hash
