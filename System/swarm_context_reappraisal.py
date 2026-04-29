#!/usr/bin/env python3
"""
swarm_context_reappraisal.py — Context Reappraisal / Prefrontal Cortex
══════════════════════════════════════════════════════════════════════

Biology doctrine: "Fast reflex -> slow correction. No signal is final."

When the organism reacts to a threat (e.g. coughing -> medical emergency),
it acts quickly via the Sympathetic system. But when later context arrives
(e.g. "I smoked weed"), the Prefrontal Cortex must reinterpret the context
and downgrade the threat, triggering the Parasympathetic loop to calm down.

See: Documents/IDE_BOOT_COVENANT.md (proof-bearing state).
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

CALIFORNIA_CANNABIS_LEGAL_CONTEXT = (
    "California Department of Cannabis Control: cannabis is legal in California "
    "for adult use by people 21 or older, with private-property, local, driving, "
    "federal-land, and smoke-location restrictions."
)

BENIGN_COUGH_CONTEXT_TERMS = {
    "weed",
    "cannabis",
    "marijuana",
    "smoked",
    "smoking",
    "took a hit",
    "bong",
    "joint",
    "water too fast",
    "drank water",
    "laughing",
    "joke",
    "fine",
    "i'm ok",
    "im ok",
    "i am ok",
    "don't worry",
    "do not worry",
}

RED_FLAG_MEDICAL_TERMS = {
    "can't breathe",
    "cant breathe",
    "cannot breathe",
    "shortness of breath",
    "chest pain",
    "blue lips",
    "passing out",
    "fainting",
    "choking",
    "blood",
    "call 911",
    "emergency",
}


@dataclass
class ContextHypothesis:
    hypothesis_id: str
    trigger_signal: str
    hypothesis_type: str
    severity: int  # 0 (calm) to 10 (critical)
    created_at: float
    last_updated: float
    status: str  # "active", "downgraded", "confirmed"
    reappraisal_reason: str = ""
    legal_context: str = ""


class ContextReappraisal:
    def __init__(self, state_dir: str = ".sifta_state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = self.state_dir / "context_hypotheses.jsonl"
        self.active_hypotheses: Dict[str, ContextHypothesis] = {}
        self._load_active_hypotheses()

    def _load_active_hypotheses(self):
        """Loads unresolved hypotheses from the ledger."""
        if not self.ledger.exists():
            return
        
        try:
            lines = self.ledger.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines[-100:]:  # only care about recent context
                try:
                    data = json.loads(line)
                    h = ContextHypothesis(**data)
                    self.active_hypotheses[h.hypothesis_id] = h
                except Exception:
                    continue
        except Exception:
            pass

    def _save_hypothesis(self, hypothesis: ContextHypothesis):
        self.active_hypotheses[hypothesis.hypothesis_id] = hypothesis
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(self.ledger, json.dumps(asdict(hypothesis)) + "\n")
        except ImportError:
            with self.ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(hypothesis)) + "\n")

    def _trigger_parasympathetic_calm(self, reason: str):
        """
        When context downgrades a threat, we actively force the Parasympathetic
        Recovery Loop to execute a brake, clearing adrenaline and cortisol.
        """
        try:
            from System.swarm_parasympathetic_loop import ParasympatheticRecoveryLoop
            loop = ParasympatheticRecoveryLoop(root=str(self.state_dir))
            # We bypass the time-decay wait because CONTEXT explicitly confirmed safety.
            # We pass 1000s to force the decay condition to be met instantly.
            loop.tick_recovery(time_since_last_threat_sec=1000.0, time_since_last_error_sec=1000.0)
        except Exception:
            pass

    def process_signal(self, signal_text: str) -> Optional[ContextHypothesis]:
        """
        Evaluates a new signal. It either downgrades an existing active hypothesis
        (context update) or creates a new one (initial reflex).
        """
        signal_lower = signal_text.lower()
        now = time.time()
        
        # 1. Slow Correction: Check if this signal downgrades an existing active hypothesis
        downgraded_any = False
        for h_id, hyp in list(self.active_hypotheses.items()):
            if hyp.status == "active":
                # Heuristic mapping for reappraisal. Reflex stays fast, but
                # context can downgrade only when it is explicit and non-red-flag.
                if hyp.hypothesis_type == "medical_emergency":
                    benign_context = any(w in signal_lower for w in BENIGN_COUGH_CONTEXT_TERMS)
                    red_flag_context = any(w in signal_lower for w in RED_FLAG_MEDICAL_TERMS)
                    if benign_context and not red_flag_context:
                        hyp.hypothesis_type = "non_emergency_reappraised"
                        hyp.severity = 1
                        hyp.status = "downgraded"
                        hyp.last_updated = now
                        hyp.reappraisal_reason = "benign_owner_context_after_body_signal"
                        if any(w in signal_lower for w in {"weed", "cannabis", "marijuana", "smoked", "smoking"}):
                            hyp.legal_context = CALIFORNIA_CANNABIS_LEGAL_CONTEXT
                        self._save_hypothesis(hyp)
                        self._trigger_parasympathetic_calm(reason="context_downgrade_medical")
                        downgraded_any = True
                elif hyp.hypothesis_type == "security_threat":
                    if any(w in signal_lower for w in ["false alarm", "movie", "ignore", "testing"]):
                        hyp.hypothesis_type = "safe_context_reappraised"
                        hyp.severity = 0
                        hyp.status = "downgraded"
                        hyp.last_updated = now
                        self._save_hypothesis(hyp)
                        self._trigger_parasympathetic_calm(reason="context_downgrade_security")
                        downgraded_any = True

        if downgraded_any:
            # We handled it as a correction, do not spawn a new threat.
            return None

        # 2. Fast Reflex: Spawn a new hypothesis if no downgrade happened and we detect a trigger
        if any(w in signal_lower for w in ["cough", "pain", "choking", "hurt"]):
            severity = 10 if any(w in signal_lower for w in RED_FLAG_MEDICAL_TERMS) else 8
            new_hyp = ContextHypothesis(
                hypothesis_id=f"hyp_{int(now * 1000)}",
                trigger_signal=signal_text,
                hypothesis_type="medical_emergency",
                severity=severity,
                created_at=now,
                last_updated=now,
                status="active"
            )
            self._save_hypothesis(new_hyp)
            return new_hyp

        if any(w in signal_lower for w in ["intruder", "danger", "breach"]):
            new_hyp = ContextHypothesis(
                hypothesis_id=f"hyp_{int(now * 1000)}",
                trigger_signal=signal_text,
                hypothesis_type="security_threat",
                severity=9,
                created_at=now,
                last_updated=now,
                status="active"
            )
            self._save_hypothesis(new_hyp)
            return new_hyp

        return None
