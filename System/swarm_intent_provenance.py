#!/usr/bin/env python3
"""
swarm_intent_provenance.py — Intent Provenance Law
══════════════════════════════════════════════════════════════════════

The INTENT PROVENANCE LAW solves the "self vs other" intent separation.
Every action must carry a classified intent source (owner | model | reflex | scheduler)
and a formal consent label. This prevents "action hallucination" where a system
incorrectly attributes a routed or owner-initiated action as "Alice autonomous".

See: Documents/IDE_BOOT_COVENANT.md
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


class IntentSource(str, Enum):
    OWNER = "owner"
    MODEL = "model"
    REFLEX = "reflex"
    SCHEDULER = "scheduler"


class ConsentType(str, Enum):
    EXPLICIT = "explicit"
    IMPLICIT = "implicit"
    NONE = "none"


@dataclass
class IntentContext:
    trigger_event: str
    autonomy_score: float = 0.0
    explicit_approval: bool = False
    routing_path: List[str] = field(default_factory=list)
    routed_via_tool_router: bool = False


@dataclass
class ProvenanceReceipt:
    ts: float
    action_id: str
    intent_source: str
    consent: str
    decision_path: List[str]
    authorized: bool
    reason: str
    provenance_hash: str


class IntentProvenanceLaw:
    """
    Enforces the Intent Provenance Law.
    Separates "self vs other" intent. 
    Prevents the system from mislabeling a routed action as "Alice autonomous" 
    when it was actually a scheduler or user reflex.
    """
    def __init__(self, ledger_path: str = ".sifta_state/intent_provenance.jsonl"):
        self.ledger_path = Path(ledger_path)
        
    def classify_intent(self, 
                        action_id: str,
                        source_hint: str, 
                        context: IntentContext,
                        requires_explicit: bool = False) -> ProvenanceReceipt:
        
        # 1. Classify Source (legacy WhatsApp / tool_router tags included)
        hint = source_hint.lower()
        if hint in {"owner", "architect", "human", "owner_explicit"}:
            source = IntentSource.OWNER
        elif "alice_tool_router_architect_consent" in hint or "architect_consent" in hint:
            source = IntentSource.OWNER
        elif "alice_tool_router_owner_path" in hint:
            source = IntentSource.OWNER
        elif "alice_autonomous" in hint:
            if context.routed_via_tool_router:
                source = IntentSource.MODEL
            else:
                source = IntentSource.REFLEX
        elif hint in {"model", "alice", "llm"} or "tool_router" in hint:
            source = IntentSource.MODEL
        elif hint in {"reflex", "immune", "homeostasis"}:
            source = IntentSource.REFLEX
        elif hint in {"scheduler", "cron", "timer"}:
            source = IntentSource.SCHEDULER
        else:
            raise ValueError(f"Unknown intent source hint: {hint}")
            
        # 2. Determine Consent
        path = list(context.routing_path) if context.routing_path else []
        if source == IntentSource.OWNER:
            consent = ConsentType.EXPLICIT
            path.append("owner_direct")
        elif context.explicit_approval:
            consent = ConsentType.EXPLICIT
            path.append("explicit_override")
        elif source == IntentSource.MODEL:
            if context.autonomy_score > 0.72:
                consent = ConsentType.IMPLICIT
                path.append("bounded_autonomy_passed")
            else:
                consent = ConsentType.NONE
                path.append("bounded_autonomy_failed")
        elif source in {IntentSource.REFLEX, IntentSource.SCHEDULER}:
            consent = ConsentType.IMPLICIT
            path.append(f"{source.value}_implicit")
        else:
            consent = ConsentType.NONE
            
        # 3. Authorization Gate
        if consent == ConsentType.NONE:
            authorized = False
            reason = "no_consent"
        elif requires_explicit and consent != ConsentType.EXPLICIT:
            authorized = False
            reason = "explicit_consent_required"
        else:
            authorized = True
            reason = "intent_authorized"
            
        # 4. Hash and Sign
        payload = {
            "action_id": action_id,
            "source": source.value,
            "consent": consent.value,
            "authorized": authorized,
        }
        provenance_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        
        receipt = ProvenanceReceipt(
            ts=time.time(),
            action_id=action_id,
            intent_source=source.value,
            consent=consent.value,
            decision_path=path,
            authorized=authorized,
            reason=reason,
            provenance_hash=provenance_hash
        )
        
        self._record_receipt(receipt)
        return receipt
        
    def _record_receipt(self, receipt: ProvenanceReceipt):
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(self.ledger_path, json.dumps(asdict(receipt)) + "\n")
        except ImportError:
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(receipt)) + "\n")
