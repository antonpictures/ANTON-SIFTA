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
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parents[1]


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


def _verify_integrity_block(block: Dict[str, Any]) -> None:
    if "integrity" not in block:
        return
    stripped = {k: v for k, v in block.items() if k != "integrity"}
    expect = hashlib.sha256(
        json.dumps(stripped, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if block.get("integrity") != expect:
        raise ValueError("intent_receipt_tampered")


def _flatten_intent(intent_receipt: Dict[str, Any]) -> Dict[str, Any]:
    """Merge ``intent_provenance`` into a single dict for classification."""
    out = dict(intent_receipt)
    prov = intent_receipt.get("intent_provenance")
    if isinstance(prov, dict):
        for k, v in prov.items():
            out.setdefault(k, v)
    return out


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

    def __init__(self, root: Optional[Any] = None):
        if root is None:
            self.root = _REPO / ".sifta_state"
        else:
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
        flat = _flatten_intent(intent_receipt)
        prov = intent_receipt.get("intent_provenance")
        prov_sealed = isinstance(prov, dict) and "integrity" in prov
        if prov_sealed:
            _verify_integrity_block(prov)

        intent_hash = flat.get("provenance_hash")
        if intent_hash:
            payload = {
                "action_id": flat.get("action_id"),
                "source": flat.get("intent_source"),
                "consent": flat.get("consent"),
                "authorized": flat.get("authorized"),
            }
            recalc_hash = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            if recalc_hash != intent_hash:
                raise ValueError("intent_receipt_tampered")
        elif prov_sealed:
            pass
        elif "integrity" in flat:
            _verify_integrity_block(flat)
        else:
            raise ValueError("intent_receipt_missing_hash")

        source = str(flat.get("intent_source", "unknown"))
        consent = str(flat.get("consent", "none"))
        decision_path = list(flat.get("decision_path") or [])

        effector_ok = bool(effector_receipt.get("ok", False)) or (
            effector_receipt.get("status") in {"COMMITTED", "SENT", "ok", "committed"}
        )
        if effector_receipt.get("phase") == "COMMIT" and effector_receipt.get("ok") is True:
            effector_ok = True

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

        if not effector_ok:
            social_label = "attempt_failed_not_owned"
        elif source == "owner":
            social_label = "owner_authorized_action"
        elif owned_by_alice and source == "reflex":
            social_label = "alice_reflex_action"
        elif owned_by_alice:
            social_label = "alice_owned_action"
        else:
            social_label = "observed_or_routed_not_owned"

        owned_flag = bool(owned_by_alice and source != "owner")

        verdict_payload = {
            "action_id": action_id,
            "intent_source": source,
            "consent": consent,
            "effector_ok": effector_ok,
            "observed_outcome": observed_outcome,
            "owned_by_alice": owned_flag,
            "social_label": social_label,
            "intent_hash": intent_hash or flat.get("integrity"),
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
            owned_by_alice=owned_flag,
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
