#!/usr/bin/env python3
"""
swarm_stigmergic_reasoning.py — Stigmergic Reasoning Cortex
══════════════════════════════════════════════════════════════════════

Comparative psychology translated to code:
1. Metacognition ("I know when I don't know") -> uncertainty monitoring
2. Evidence Reappraisal ("New evidence changes my mind") -> Bayesian update
3. Dual-process Reasoning -> fast reflex vs slow deliberation
4. Active Inference -> predictive error minimization
5. Stigmergy -> Reasoning that leaves an evidence trail (ledgers)

Human reasoning happens in the head.
Animal reasoning happens in body + world.
SIFTA reasoning happens in ledgers + body + world.

See: Documents/IDE_BOOT_COVENANT.md (proof-bearing state).
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


TRACE_SCHEMA = "SIFTA_STIGMERGIC_REASONING_TRACE_V1"


@dataclass
class ReasoningTrace:
    schema: str
    ts: float
    trace_id: str
    question: str
    hypothesis: str
    evidence: List[str]
    confidence: float
    uncertainty: float
    risk: float
    energy_cost: float
    prediction_error: float
    intent_source: str
    consent: str
    effector_ok: bool
    observed_outcome: str
    action: str
    reason: str
    trace_hash: str


class StigmergicReasoner:
    """
    Stigmergic Reasoning Cortex.
    Audits and structures LLM reasoning through comparative psychology rules.
    """

    def __init__(self, root: str = ".sifta_state"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger = self.root / "stigmergic_reasoning.jsonl"

    def decide(
        self,
        question: str,
        hypothesis: str,
        evidence: List[str],
        confidence: float,
        risk: float,
        energy_cost: float,
        *,
        prediction_error: float = 0.0,
        intent_source: str = "unknown",
        consent: str = "none",
        effector_receipt: Optional[Dict[str, Any]] = None,
        observed_outcome: str = "",
        external_action_claim: bool = False,
    ) -> ReasoningTrace:
        """
        Dual-process routing + Metacognitive uncertainty monitoring.
        """
        confidence = max(0.0, min(1.0, confidence))
        risk = max(0.0, min(1.0, risk))
        energy_cost = max(0.0, min(1.0, energy_cost))
        prediction_error = max(-1.0, min(1.0, float(prediction_error)))
        uncertainty = 1.0 - confidence
        clean_evidence = [str(e) for e in evidence]
        effector_ok = self._effector_ok(effector_receipt)

        if external_action_claim and not effector_ok:
            action = "SLOW_REVIEW"
            reason = "external_claim_requires_effector_receipt"
        elif risk > 0.7:
            action = "SLOW_REVIEW"
            reason = "high_risk_requires_deliberation"
        elif abs(prediction_error) > 0.5 and risk > 0.3:
            action = "SLOW_REVIEW"
            reason = "prediction_error_requires_deliberation"
        elif uncertainty > 0.45:
            action = "ASK_OR_OBSERVE_MORE"
            reason = "uncertainty_monitoring_triggered"
        elif abs(prediction_error) > 0.35:
            action = "ASK_OR_OBSERVE_MORE"
            reason = "prediction_error_observe_more"
        elif energy_cost > 0.7:
            action = "DEFER_OR_COMPRESS"
            reason = "metabolic_cost_high"
        else:
            action = "ACT"
            reason = "confidence_sufficient"

        payload = {
            "schema": TRACE_SCHEMA,
            "trace_id": f"reason_{uuid.uuid4()}",
            "question": question,
            "hypothesis": hypothesis,
            "evidence": clean_evidence,
            "confidence": confidence,
            "uncertainty": uncertainty,
            "risk": risk,
            "energy_cost": energy_cost,
            "prediction_error": prediction_error,
            "intent_source": str(intent_source or "unknown"),
            "consent": str(consent or "none"),
            "effector_ok": effector_ok,
            "observed_outcome": str(observed_outcome or ""),
            "action": action,
            "reason": reason,
        }

        h = self._hash_payload(payload)

        trace = ReasoningTrace(
            ts=time.time(),
            trace_hash=h,
            **payload,
        )

        self._record_trace(trace)
        return trace

    def reappraise(
        self, 
        old_trace: Dict[str, Any], 
        new_evidence: str, 
        evidence_strength: float,
        *,
        risk: Optional[float] = None,
        energy_cost: Optional[float] = None,
    ) -> ReasoningTrace:
        """
        Evidence reappraisal: Belief update based on new evidence.
        belief_next = belief_old + learning_rate * (new_evidence_strength - belief_old)
        """
        old_conf = float(old_trace.get("confidence", 0.5))
        evidence_strength = max(0.0, min(1.0, evidence_strength))

        # Learning rate is conceptually 0.35 here
        updated_conf = old_conf + 0.35 * (evidence_strength - old_conf)

        return self.decide(
            question=old_trace.get("question", ""),
            hypothesis=old_trace.get("hypothesis", ""),
            evidence=list(old_trace.get("evidence", [])) + [new_evidence],
            confidence=updated_conf,
            risk=0.3 if risk is None else risk,
            energy_cost=0.2 if energy_cost is None else energy_cost,
            prediction_error=evidence_strength - old_conf,
            intent_source=str(old_trace.get("intent_source", "unknown")),
            consent=str(old_trace.get("consent", "none")),
            observed_outcome=str(old_trace.get("observed_outcome", "")),
        )

    @staticmethod
    def _effector_ok(effector_receipt: Optional[Dict[str, Any]]) -> bool:
        if not effector_receipt:
            return False
        return bool(effector_receipt.get("ok")) or str(effector_receipt.get("status", "")).lower() in {
            "ok",
            "sent",
            "committed",
        }

    @staticmethod
    def _hash_payload(payload: Dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @classmethod
    def verify_trace_hash(cls, trace: Dict[str, Any]) -> bool:
        payload = dict(trace)
        payload.pop("ts", None)
        stored = str(payload.pop("trace_hash", ""))
        return bool(stored) and cls._hash_payload(payload) == stored

    def _record_trace(self, trace: ReasoningTrace) -> None:
        row = json.dumps(asdict(trace), sort_keys=True, separators=(",", ":")) + "\n"
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(self.ledger, row)
        except ImportError:
            with self.ledger.open("a", encoding="utf-8") as f:
                f.write(row)


def _smoke_test():
    print("\n=== SIFTA STIGMERGIC REASONING (Comparative Psychology) ===")
    
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        reasoner = StigmergicReasoner(root=td)
        
        # 1. High Uncertainty -> Ask for more
        t1 = reasoner.decide(
            question="Is the user angry?",
            hypothesis="User is angry about the bug.",
            evidence=["User said 'fix this'"],
            confidence=0.4, # Uncertainty = 0.6
            risk=0.5,
            energy_cost=0.1
        )
        assert t1.action == "ASK_OR_OBSERVE_MORE"
        print("[PASS] Uncertainty monitoring triggered.")
        
        # 2. High Risk -> Slow Review
        t2 = reasoner.decide(
            question="Should I delete the system logs?",
            hypothesis="Logs are taking up space.",
            evidence=["Disk at 90%"],
            confidence=0.9, # High confidence
            risk=0.8,       # But high risk
            energy_cost=0.1
        )
        assert t2.action == "SLOW_REVIEW"
        print("[PASS] Dual-process triggered SLOW_REVIEW for high risk.")
        
        # 3. Reappraisal -> Update Belief
        old_trace = asdict(t1)
        t3 = reasoner.reappraise(
            old_trace=old_trace,
            new_evidence="User followed up with 'thanks for checking! take your time'",
            evidence_strength=0.1 # Very low anger probability
        )
        print(f"[PASS] Reappraisal adjusted confidence from {t1.confidence} to {t3.confidence:.3f}")

if __name__ == "__main__":
    _smoke_test()
