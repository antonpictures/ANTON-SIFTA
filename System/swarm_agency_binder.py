#!/usr/bin/env python3
"""
swarm_agency_binder.py — Agency Cortex
══════════════════════════════════════════════════════════════════════

The Agency Cortex enforces biological agency binding.
It binds intent provenance (why) to effector receipt (did it happen) to produce
a social ownership verdict. This mimics corollary discharge / efference copy,
ensuring Alice never hallucinates ownership of an action caused by the owner, 
a tool-router hallucination, or a failed effector.

See: Documents/IDE_BOOT_COVENANT.md
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass
class AgencyVerdict:
    ts: float
    action_id: str
    intent_source: str
    consent: str
    effector_ok: bool
    observed_outcome: str
    owned_by_alice: bool
    social_label: str
    verdict_hash: str


class AgencyBinder:
    """
    Biological agency binding (Agency Cortex).

    Inspired by:
      - efference copy / corollary discharge
      - self vs other action monitoring
      - social intentional-action attribution

    It prevents:
      "Alice sent it" when only the owner/tool-router/reflex caused it.
    """

    def __init__(self, root: str = ".sifta_state"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger = self.root / "agency_verdicts.jsonl"

    def bind(
        self,
        action_id: str,
        intent_receipt: Dict[str, Any],
        effector_receipt: Dict[str, Any],
        observed_outcome: str,
    ) -> AgencyVerdict:
        
        # 1. Validate intent hash
        intent_hash = intent_receipt.get("provenance_hash")
        if not intent_hash:
            raise ValueError("intent_receipt_missing_hash")
            
        # Optional: check if intent_receipt is tampered by recalculating hash
        payload = {
            "action_id": intent_receipt.get("action_id"),
            "source": intent_receipt.get("intent_source"),
            "consent": intent_receipt.get("consent"),
            "authorized": intent_receipt.get("authorized"),
        }
        recalc_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        
        if recalc_hash != intent_hash:
            raise ValueError("intent_receipt_tampered")

        source = intent_receipt.get("intent_source", "unknown")
        consent = intent_receipt.get("consent", "none")
        decision_path = intent_receipt.get("decision_path", [])

        effector_ok = bool(effector_receipt.get("ok", False)) or (
            effector_receipt.get("status") in {"COMMITTED", "SENT", "ok", "committed"}
        )

        # Alice owns the action only if:
        # 1. model/reflex/scheduler generated the intent,
        # 2. consent gate permitted it,
        # 3. effector actually executed,
        # 4. decision path is recorded.
        owned_by_alice = (
            source in {"model", "reflex", "scheduler"}
            and consent in {"implicit", "explicit"}
            and effector_ok
            and len(decision_path) > 0
        )

        if source == "owner":
            social_label = "owner_authorized_action"
        elif owned_by_alice:
            social_label = "alice_owned_action"
        elif not effector_ok:
            social_label = "attempt_failed_not_owned"
        else:
            social_label = "observed_or_routed_not_owned"

        verdict_payload = {
            "action_id": action_id,
            "intent_source": source,
            "consent": consent,
            "effector_ok": effector_ok,
            "observed_outcome": observed_outcome,
            "owned_by_alice": owned_by_alice,
            "social_label": social_label,
            "intent_hash": intent_hash
        }

        h = hashlib.sha256(
            json.dumps(verdict_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        verdict = AgencyVerdict(
            ts=time.time(),
            action_id=action_id,
            intent_source=source,
            consent=consent,
            effector_ok=effector_ok,
            observed_outcome=observed_outcome,
            owned_by_alice=owned_by_alice,
            social_label=social_label,
            verdict_hash=h,
        )

        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(self.ledger, json.dumps(asdict(verdict)) + "\n")
        except ImportError:
            with self.ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(verdict)) + "\n")

        return verdict
