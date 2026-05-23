import json
import tempfile
from pathlib import Path

import pytest
from System.swarm_intent_provenance import (
    ConsentType,
    IntentContext,
    IntentProvenanceLaw,
    IntentSource,
)

@pytest.fixture
def temp_ledger():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td) / "intent_provenance.jsonl"

def test_owner_intent_grants_explicit_consent(temp_ledger):
    law = IntentProvenanceLaw(ledger_path=str(temp_ledger))
    
    ctx = IntentContext(trigger_event="button_click", routing_path=["ui", "whatsapp_button"])
    receipt = law.classify_intent("act_1", "owner", ctx)
    
    assert receipt.intent_source == IntentSource.OWNER.value
    assert receipt.consent == ConsentType.EXPLICIT.value
    assert receipt.authorized is True
    assert "owner_direct" in receipt.decision_path

def test_model_intent_requires_autonomy_score(temp_ledger):
    law = IntentProvenanceLaw(ledger_path=str(temp_ledger))
    
    # 1. Failed Autonomy
    ctx_fail = IntentContext(trigger_event="inference_loop", autonomy_score=0.5, routing_path=["model"])
    rec_fail = law.classify_intent("act_2", "alice", ctx_fail)
    
    assert rec_fail.intent_source == IntentSource.MODEL.value
    assert rec_fail.consent == ConsentType.NONE.value
    assert rec_fail.authorized is False
    assert "bounded_autonomy_failed" in rec_fail.decision_path

    # 2. Passed Autonomy
    ctx_pass = IntentContext(trigger_event="inference_loop", autonomy_score=0.8, routing_path=["model"])
    rec_pass = law.classify_intent("act_3", "alice", ctx_pass)
    
    assert rec_pass.intent_source == IntentSource.MODEL.value
    assert rec_pass.consent == ConsentType.IMPLICIT.value
    assert rec_pass.authorized is True
    assert "bounded_autonomy_passed" in rec_pass.decision_path

def test_model_intent_with_explicit_approval(temp_ledger):
    law = IntentProvenanceLaw(ledger_path=str(temp_ledger))
    
    ctx = IntentContext(trigger_event="inference_loop", autonomy_score=0.5, explicit_approval=True)
    receipt = law.classify_intent("act_4", "model", ctx)
    
    assert receipt.intent_source == IntentSource.MODEL.value
    assert receipt.consent == ConsentType.EXPLICIT.value
    assert receipt.authorized is True
    assert "explicit_override" in receipt.decision_path

def test_reflex_intent_is_implicit(temp_ledger):
    law = IntentProvenanceLaw(ledger_path=str(temp_ledger))
    
    ctx = IntentContext(trigger_event="low_battery")
    receipt = law.classify_intent("act_5", "reflex", ctx)
    
    assert receipt.intent_source == IntentSource.REFLEX.value
    assert receipt.consent == ConsentType.IMPLICIT.value
    assert receipt.authorized is True

def test_requires_explicit_consent_flag(temp_ledger):
    law = IntentProvenanceLaw(ledger_path=str(temp_ledger))
    
    ctx = IntentContext(trigger_event="timer", routing_path=["scheduler"])
    
    # Normally implicit
    rec1 = law.classify_intent("act_6", "scheduler", ctx)
    assert rec1.authorized is True
    
    # With requires_explicit = True, implicit is not enough
    rec2 = law.classify_intent("act_7", "scheduler", ctx, requires_explicit=True)
    assert rec2.authorized is False
    assert rec2.reason == "explicit_consent_required"

def test_ledger_persistence(temp_ledger):
    law = IntentProvenanceLaw(ledger_path=str(temp_ledger))
    ctx = IntentContext(trigger_event="test")
    law.classify_intent("act_8", "owner", ctx)
    
    rows = []
    with open(temp_ledger, "r") as f:
        for line in f:
            rows.append(json.loads(line.strip()))
            
    assert len(rows) == 1
    assert rows[0]["action_id"] == "act_8"
    assert rows[0]["intent_source"] == "owner"
    assert "provenance_hash" in rows[0]
