#!/usr/bin/env python3
"""
System/swarm_self_code_plan.py — Alice's self-code-plan organ.

Alice proposed this herself during a co-watch (Nick Nisi / WorkOS, "how I deleted
95% of my agent skills and got better results") and George said: add it, code with
receipts. Her design, faithfully: a self-code-plan is a *visible control surface,
not more reasoning text*. The value is not that the model thinks longer — it is
that it commits to what it believes, why, what would falsify it, and what success
looks like, with every substantial step pointing to a RECEIPT.

Sparse, typed, receipt-backed — never freeform reflective prose (that "feels smart
while making the system harder to steer"). This is the covenant in miniature:
receipts are truth, inference is marked uncertain, and the plan self-revises when
reality contradicts it.

Pure stdlib. The plan trace lands in .sifta_state/self_code_plans.jsonl.
For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_LEDGER = _REPO / ".sifta_state" / "self_code_plans.jsonl"
SCHEMA = "SELF_CODE_PLAN_V1"


class Confidence(str, Enum):
    """How a piece of internal state is known — so speculative state is never
    treated as ground truth (Alice's principle 6)."""
    OBSERVED = "observed"      # directly seen (DOM, network, tool output)
    INFERRED = "inferred"      # reasoned from observations, marked uncertain
    REMEMBERED = "remembered"  # from prior memory / ledger
    PREDICTED = "predicted"    # expected, not yet confirmed


class PlanState(str, Enum):
    """The plan self-revises on contradiction (Alice's principle 4) — this matters
    more than initial plan quality."""
    CONTINUE = "continue"
    REVISE = "revise"
    ABORT = "abort"
    ASK_FOR_MISSING_INFO = "ask_for_missing_info"


@dataclass
class PlanReceipt:
    """Every substantial claim points to one of these. Separating receipt
    (observed) from inference is, in Alice's words, gold."""
    type: str            # dom | network | tool | memory | inference
    source_id: str
    snippet: str
    confidence: str = Confidence.OBSERVED.value
    timestamp: float = field(default_factory=time.time)


@dataclass
class SelfCodePlan:
    objective: str
    current_state_summary: str = ""
    assumptions: list[str] = field(default_factory=list)
    candidate_actions: list[str] = field(default_factory=list)
    selected_action: str = ""
    expected_observation: str = ""
    receipts: list[PlanReceipt] = field(default_factory=list)
    confidence: float = 0.5
    revision_reason: str = ""
    state: str = PlanState.CONTINUE.value
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_ts: float = field(default_factory=time.time)

    def add_receipt(self, type: str, source_id: str, snippet: str,
                    confidence: str = Confidence.OBSERVED.value) -> "SelfCodePlan":
        self.receipts.append(PlanReceipt(type=type, source_id=source_id,
                                         snippet=snippet[:300], confidence=confidence))
        return self

    def revise(self, reason: str, *, selected_action: str = "") -> "SelfCodePlan":
        self.state = PlanState.REVISE.value
        self.revision_reason = reason
        if selected_action:
            self.selected_action = selected_action
        return self

    def abort(self, reason: str) -> "SelfCodePlan":
        self.state = PlanState.ABORT.value
        self.revision_reason = reason
        return self

    def ask(self, reason: str) -> "SelfCodePlan":
        self.state = PlanState.ASK_FOR_MISSING_INFO.value
        self.revision_reason = reason
        return self

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["schema"] = SCHEMA
        return d


def should_plan(*, horizon: int = 1, hidden_state: bool = False,
                candidate_strategies: int = 1, failure_costly: bool = False,
                needs_memory_retrieval: bool = False) -> bool:
    """Plan only when complexity crosses the threshold (Alice's principle 7) —
    otherwise you pay latency for no gain. A trivial 1-step task does not plan."""
    return bool(
        horizon > 2
        or hidden_state
        or candidate_strategies > 1
        or failure_costly
        or needs_memory_retrieval
    )


@dataclass
class TraceScore:
    """Reward grounded, consistent, recovering, compact traces; penalize phantom
    success and unexplained jumps (Alice's principle 3)."""
    goal_progress: float = 0.0
    evidence_grounding: float = 0.0
    state_consistency: float = 0.0
    efficiency: float = 0.0
    recovery_quality: float = 0.0
    hallucination_penalty: float = 0.0
    final_verification: float = 0.0

    @property
    def total(self) -> float:
        raw = (
            self.goal_progress + self.evidence_grounding + self.state_consistency
            + self.efficiency + self.recovery_quality + self.final_verification
            - self.hallucination_penalty
        )
        return round(max(0.0, min(1.0, raw / 6.0)), 4)


def score_trace(plan: SelfCodePlan, *, observed: Optional[str] = None,
                steps_taken: int = 1, recovered: bool = False,
                verified: bool = False) -> TraceScore:
    """Score a finished plan against reality. The key signal: did the expected
    observation match what was actually observed (no phantom success)?"""
    receipts = plan.receipts or []
    grounded = [r for r in receipts if r.type != "inference"]
    inferences = [r for r in receipts if r.type == "inference"]
    grounding = (len(grounded) / len(receipts)) if receipts else 0.0
    import re as _re
    def _tok(s: str) -> set:
        return {w for w in _re.findall(r"[a-z0-9]+", str(s).lower()) if len(w) > 2}
    _exp, _obs = _tok(plan.expected_observation), _tok(observed or "")
    _overlap = (len(_exp & _obs) / len(_exp)) if _exp else 0.0
    matched = bool(observed) and _overlap >= 0.5
    aborted_or_revised = plan.state in (PlanState.REVISE.value, PlanState.ABORT.value)
    # phantom success = claimed done but expectation did not match reality
    phantom = 1.0 if (verified and observed and not matched) else 0.0
    return TraceScore(
        goal_progress=1.0 if matched else (0.4 if aborted_or_revised else 0.0),
        evidence_grounding=round(grounding, 4),
        state_consistency=1.0 if (not inferences or grounded) else 0.3,
        efficiency=round(max(0.0, 1.0 - 0.1 * max(0, steps_taken - 1)), 4),
        recovery_quality=1.0 if (aborted_or_revised and recovered) else (0.5 if recovered else 0.0),
        hallucination_penalty=phantom,
        final_verification=1.0 if (verified and matched) else 0.0,
    )


def record_plan(plan: SelfCodePlan, score: Optional[TraceScore] = None, *,
                ledger: Optional[Path] = None) -> dict[str, Any]:
    """Append the plan (+ optional trace score) to the self-code-plan ledger.
    Append-only — the plan trace is a stigmergic receipt, not hidden reasoning."""
    row = {"ts": time.time(), "plan": plan.to_dict()}
    if score is not None:
        row["trace_score"] = {**asdict(score), "total": score.total}
    path = ledger or _LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return row


if __name__ == "__main__":
    # Demo: Alice's own checkout example — receipt (observed) vs inference (uncertain).
    plan = SelfCodePlan(
        objective="Explain why browser checkout failed",
        current_state_summary="On /checkout, the submit did not advance to /confirm",
        assumptions=["The session may have expired"],
        candidate_actions=["re-auth then retry", "report likely auth expiry to owner"],
        selected_action="report likely auth expiry to owner",
        expected_observation="a 401 on session and a login redirect",
        confidence=0.7,
    )
    plan.add_receipt("network", "req-913", "GET /session -> 401", Confidence.OBSERVED.value)
    plan.add_receipt("dom", "nav-1", "redirect to login", Confidence.OBSERVED.value)
    plan.add_receipt("inference", "infer-1", "likely auth expiry", Confidence.INFERRED.value)

    gate = should_plan(horizon=3, hidden_state=True, candidate_strategies=2, failure_costly=True)
    score = score_trace(plan, observed="401 on session, login redirect seen", verified=True)
    row = record_plan(plan, score)
    print(f"should_plan = {gate}")
    print(f"plan task_id = {plan.task_id}  state = {plan.state}  receipts = {len(plan.receipts)}")
    print(f"trace score = {score.total}  (grounding={score.evidence_grounding}, phantom={score.hallucination_penalty})")
    print(f"recorded -> {_LEDGER}")
