import hashlib
import json
import tempfile
from pathlib import Path

import pytest
from System.swarm_agency_binder import AgencyBinder

def _make_intent(action_id: str, source: str, consent: str, authorized: bool, path: list) -> dict:
    payload = {
        "action_id": action_id,
        "source": source,
        "consent": consent,
        "authorized": authorized,
    }
    h = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "action_id": action_id,
        "intent_source": source,
        "consent": consent,
        "authorized": authorized,
        "decision_path": path,
        "provenance_hash": h
    }

@pytest.fixture
def binder():
    with tempfile.TemporaryDirectory() as td:
        yield AgencyBinder(root=td)

def test_owner_sends_is_authorized_but_not_alice_owned(binder):
    # 1. owner sends WhatsApp → owner_authorized_action, not alice_owned_action
    intent = _make_intent("a1", "owner", "explicit", True, ["owner_direct"])
    effector = {"ok": True}
    
    verdict = binder.bind("a1", intent, effector, "whatsapp_sent")
    assert verdict.social_label == "owner_authorized_action"
    assert verdict.owned_by_alice is False

def test_model_sends_with_autonomy_pass_is_alice_owned(binder):
    # 2. model sends with autonomy gate pass → alice_owned_action
    intent = _make_intent("a2", "model", "implicit", True, ["bounded_autonomy_passed"])
    effector = {"ok": True}
    
    verdict = binder.bind("a2", intent, effector, "whatsapp_sent")
    assert verdict.social_label == "alice_owned_action"
    assert verdict.owned_by_alice is True

def test_tool_router_emits_send_without_consent_is_not_owned(binder):
    # 3. tool-router emits send tag without consent → observed_or_routed_not_owned
    intent = _make_intent("a3", "model", "none", False, ["bounded_autonomy_failed"])
    effector = {"ok": True} # effector executed anyway because no one checked, or simulated 
    
    verdict = binder.bind("a3", intent, effector, "whatsapp_sent_by_router")
    assert verdict.social_label == "observed_or_routed_not_owned"
    assert verdict.owned_by_alice is False

def test_reflex_emergency_fires_is_alice_owned(binder):
    # 4. reflex emergency fires → alice_owned_action
    intent = _make_intent("a4", "reflex", "implicit", True, ["reflex_implicit"])
    effector = {"ok": True}
    
    verdict = binder.bind("a4", intent, effector, "battery_saver_on")
    assert verdict.social_label == "alice_reflex_action"
    assert verdict.owned_by_alice is True
    assert verdict.intent_source == "reflex"

def test_effector_fails_is_attempt_failed(binder):
    # 5. effector fails → attempt_failed_not_owned
    intent = _make_intent("a5", "model", "implicit", True, ["bounded_autonomy_passed"])
    effector = {"ok": False, "status": "error"}
    
    verdict = binder.bind("a5", intent, effector, "network_timeout")
    assert verdict.social_label == "attempt_failed_not_owned"
    assert verdict.owned_by_alice is False

def test_tampered_intent_hash_rejected(binder):
    # 6. tampered intent hash → reject before binding
    intent = _make_intent("a6", "model", "implicit", True, ["bounded_autonomy_passed"])
    intent["consent"] = "explicit" # Tampered!
    
    effector = {"ok": True}
    
    with pytest.raises(ValueError, match="intent_receipt_tampered"):
        binder.bind("a6", intent, effector, "hacked_send")
