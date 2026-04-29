"""Agency binder — nested intent_provenance + integrity seals."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from System.swarm_agency_binder import AgencyBinder


def _seal_provenance(prov: dict) -> dict:
    body = {k: v for k, v in prov.items() if k != "integrity"}
    sealed = dict(body)
    sealed["integrity"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return sealed


@pytest.fixture
def binder(tmp_path: Path) -> AgencyBinder:
    return AgencyBinder(root=tmp_path / "state")


def test_owner_whatsapp_is_owner_authorized_not_alice_owned(binder: AgencyBinder) -> None:
    intent = {
        "intent_provenance": _seal_provenance(
            {
                "intent_source": "owner",
                "consent": "explicit",
                "decision_path": ["owner_ui", "effector"],
                "receipt_proof": True,
            }
        )
    }
    effector = {"ok": True, "phase": "COMMIT", "status": "SENT"}
    v = binder.bind("a1", intent, effector, "message_delivered")
    assert v.social_label == "owner_authorized_action"
    assert v.owned_by_alice is False


def test_model_gate_pass_alice_owned(binder: AgencyBinder) -> None:
    intent = {
        "intent_provenance": _seal_provenance(
            {
                "intent_source": "model",
                "consent": "implicit",
                "decision_path": ["cosmos", "tool_router", "effector"],
                "receipt_proof": True,
            }
        )
    }
    effector = {"ok": True, "phase": "COMMIT"}
    v = binder.bind("a2", intent, effector, "sent")
    assert v.social_label == "alice_owned_action"
    assert v.owned_by_alice is True


def test_router_without_consent_not_owned(binder: AgencyBinder) -> None:
    intent = {
        "intent_provenance": _seal_provenance(
            {
                "intent_source": "model",
                "consent": "none",
                "decision_path": ["tool_router"],
                "receipt_proof": False,
            }
        )
    }
    effector = {"ok": True, "phase": "COMMIT"}
    v = binder.bind("a3", intent, effector, "blocked")
    assert v.social_label == "observed_or_routed_not_owned"
    assert v.owned_by_alice is False


def test_reflex_emergency_alice_reflex_label(binder: AgencyBinder) -> None:
    intent = {
        "intent_provenance": _seal_provenance(
            {
                "intent_source": "reflex",
                "consent": "implicit",
                "decision_path": ["vagus", "effector"],
                "receipt_proof": True,
            }
        )
    }
    effector = {"ok": True}
    v = binder.bind("a4", intent, effector, "ping_sent")
    assert v.social_label == "alice_reflex_action"
    assert v.owned_by_alice is True


def test_effector_failed_not_owned(binder: AgencyBinder) -> None:
    intent = {
        "intent_provenance": _seal_provenance(
            {
                "intent_source": "model",
                "consent": "explicit",
                "decision_path": ["x", "y"],
                "receipt_proof": True,
            }
        )
    }
    effector = {"ok": False, "phase": "BROKEN"}
    v = binder.bind("a5", intent, effector, "send_failed")
    assert v.social_label == "attempt_failed_not_owned"
    assert v.owned_by_alice is False


def test_tampered_intent_rejected(binder: AgencyBinder) -> None:
    body = {
        "intent_source": "owner",
        "consent": "explicit",
        "decision_path": ["p"],
    }
    intent = {**body, "integrity": "deadbeef" * 8}
    with pytest.raises(ValueError, match="intent_receipt_tampered"):
        binder.bind("a6", intent, {"ok": True}, "n/a")


def test_verdict_row_has_verdict_hash(binder: AgencyBinder) -> None:
    intent = {
        "intent_provenance": _seal_provenance(
            {
                "intent_source": "owner",
                "consent": "explicit",
                "decision_path": ["p"],
                "receipt_proof": True,
            }
        )
    }
    binder.bind("a7", intent, {"ok": True}, "ok")
    line = (binder.root / "agency_verdicts.jsonl").read_text().strip().splitlines()[-1]
    row = json.loads(line)
    assert row.get("verdict_hash")
    assert len(row["verdict_hash"]) == 64
