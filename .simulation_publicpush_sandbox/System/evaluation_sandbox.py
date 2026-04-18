#!/usr/bin/env python3
"""
evaluation_sandbox.py — The Counterfactual Gate
═══════════════════════════════════════════════════════════════════
SOLID_PLAN §5.3 — Evaluation Sandbox

Every fissioned task must survive a counterfactual simulation + 
objective scoring pass BEFORE it is allowed to hit real hardware.
This creates a hard semantic firewall between "spawned idea" and
"physically executed computation."

The Swarm cannot amplify bad branches. Period.

Adapted from SwarmGPT's EvaluationSandbox pattern, wired into
SIFTA's ObjectiveRegistry + FailureHarvester feedback loop.
"""
from __future__ import annotations

import json
import time
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_EVAL_LOG = _STATE_DIR / "evaluation_log.jsonl"
_EVAL_STATS = _STATE_DIR / "evaluation_stats.json"


@dataclass
class EvaluationResult:
    """The verdict of a counterfactual simulation."""
    task_id: str
    approved: bool
    score: float               # predicted_value - risk
    risk: float
    predicted_value: float
    failure_modes: List[str]
    ts: float


class EvaluationSandbox:
    """
    The semantic firewall. No task reaches hardware without passing
    through this gate. It runs a lightweight counterfactual simulation
    using the ObjectiveRegistry to predict whether the task is worth
    burning real compute on.

    If the task fails evaluation, it is:
      1. Logged as a rejected branch
      2. Fed BACK to the FailureHarvester as a "pre-mortem" failure
         (the Swarm learns from ideas it killed before they ran)
    """

    def __init__(self, approval_threshold: float = 0.4):
        self.approval_threshold = approval_threshold
        self._approved_count = 0
        self._rejected_count = 0
        self._load_stats()

    # ── Core Gate ────────────────────────────────────────────────────

    def evaluate(self, task_id: str, description: str,
                 objective_estimates: Dict[str, float]) -> EvaluationResult:
        """
        Run counterfactual simulation on a task proposal.
        Uses the ObjectiveRegistry to score predicted value,
        then subtracts measured risk to get a net score.
        """
        # 1. Score via ObjectiveRegistry (the charter defines value)
        predicted_value = 0.0
        try:
            from objective_registry import get_registry
            predicted_value = get_registry().score_action(objective_estimates)
        except ImportError:
            predicted_value = sum(objective_estimates.values()) / max(1, len(objective_estimates))

        # 2. Derive risk from stability estimate (inverse)
        stability_est = objective_estimates.get("stability", 0.5)
        base_risk = max(0.0, 1.0 - stability_est)

        # 3. Inject bounded noise (the world is uncertain)
        noise = random.uniform(-0.05, 0.05)
        risk = min(1.0, base_risk + noise)

        # 4. Infer failure modes
        failure_modes = self._infer_failure_modes(predicted_value, risk)

        # 5. Net score = value - risk
        net_score = predicted_value - (risk * 0.5)

        # Apply Identity Coherence (ICF) pressure to strictness
        effective_threshold = self.approval_threshold
        try:
            from control_hysteresis_layer import get_hysteresis_layer
            hl = get_hysteresis_layer()
            hl_state = hl.process_field()
            strictness = hl_state.get("control_field", {}).get("evaluation_strictness", self.approval_threshold)
            
            # If coherence is low, strictness goes up
            effective_threshold = max(self.approval_threshold, strictness)
        except ImportError:
            pass

        approved = net_score >= effective_threshold and len(failure_modes) < 3

        result = EvaluationResult(
            task_id=task_id,
            approved=approved,
            score=round(net_score, 4),
            risk=round(risk, 4),
            predicted_value=round(predicted_value, 4),
            failure_modes=failure_modes,
            ts=time.time(),
        )

        # Track stats
        if approved:
            self._approved_count += 1
        else:
            self._rejected_count += 1

        self._log_result(result)
        self._persist_stats()

        return result

    def _infer_failure_modes(self, value: float, risk: float) -> List[str]:
        """
        Heuristic failure mode detection.
        These are PREDICTED failure modes, not observed ones.
        """
        modes = []
        if risk > 0.7:
            modes.append("INSTABILITY_SPIKE")
        if value < 0.2:
            modes.append("LOW_UTILITY_PROJECTION")
        if value < risk:
            modes.append("RISK_DOMINANT_STATE")
        if risk > 0.9:
            modes.append("CATASTROPHIC_RISK")
        return modes

    # ── Feedback Loop ────────────────────────────────────────────────

    def reject_to_harvester(self, result: EvaluationResult) -> None:
        """
        Feed rejected tasks BACK to the FailureHarvester as pre-mortem
        failures. The Swarm learns from ideas it killed before they ran.
        """
        if result.approved:
            return  # Don't harvest approvals

        try:
            from failure_harvesting import get_harvester
            harvester = get_harvester()
            harvester.harvest(
                agent_context="EvaluationSandbox",
                task_name=f"REJECTED_PREMORTEM:{result.task_id}",
                error_msg=f"Counterfactual rejection: score={result.score:.3f}, "
                          f"risk={result.risk:.3f}, modes={result.failure_modes}",
                context_data={
                    "predicted_value": result.predicted_value,
                    "risk": result.risk,
                    "failure_modes": result.failure_modes,
                }
            )
        except ImportError:
            pass

    # ── Persistence ──────────────────────────────────────────────────

    def _log_result(self, result: EvaluationResult) -> None:
        try:
            with open(_EVAL_LOG, "a") as f:
                f.write(json.dumps(asdict(result)) + "\n")
        except Exception:
            pass

    def _persist_stats(self) -> None:
        try:
            _EVAL_STATS.write_text(json.dumps({
                "approved": self._approved_count,
                "rejected": self._rejected_count,
                "approval_rate": round(
                    self._approved_count / max(1, self._approved_count + self._rejected_count), 3
                ),
                "threshold": self.approval_threshold,
                "ts": time.time()
            }, indent=2))
        except Exception:
            pass

    def _load_stats(self) -> None:
        if _EVAL_STATS.exists():
            try:
                data = json.loads(_EVAL_STATS.read_text())
                self._approved_count = data.get("approved", 0)
                self._rejected_count = data.get("rejected", 0)
            except Exception:
                pass

    def stats(self) -> Dict[str, Any]:
        total = self._approved_count + self._rejected_count
        return {
            "approved": self._approved_count,
            "rejected": self._rejected_count,
            "total": total,
            "approval_rate": round(self._approved_count / max(1, total), 3),
            "threshold": self.approval_threshold,
        }


# ── Singleton ────────────────────────────────────────────────────────
_SANDBOX: Optional[EvaluationSandbox] = None

def get_sandbox() -> EvaluationSandbox:
    global _SANDBOX
    if _SANDBOX is None:
        _SANDBOX = EvaluationSandbox()
    return _SANDBOX


if __name__ == "__main__":
    print("═" * 58)
    print("  SIFTA — EVALUATION SANDBOX (Counterfactual Gate)")
    print("═" * 58 + "\n")

    sandbox = get_sandbox()

    # Test 1: High-value, stable task → should PASS
    print("  1. Evaluating HIGH-VALUE STABLE task:")
    r1 = sandbox.evaluate("TEST_SAFE", "Fix heartbeat cron",
                          {"task_success": 0.9, "stability": 0.9, "resource_efficiency": 0.7})
    print(f"     Score: {r1.score:.3f}  Risk: {r1.risk:.3f}  Approved: {r1.approved}")
    print(f"     Failure modes: {r1.failure_modes}")

    # Test 2: High-value but DANGEROUS task → might fail
    print("\n  2. Evaluating HIGH-VALUE DANGEROUS task:")
    r2 = sandbox.evaluate("TEST_DANGER", "Mutate kernel module",
                          {"task_success": 0.8, "stability": 0.0, "exploration": 0.9})
    print(f"     Score: {r2.score:.3f}  Risk: {r2.risk:.3f}  Approved: {r2.approved}")
    print(f"     Failure modes: {r2.failure_modes}")

    # Test 3: Low-value, low-risk garbage task → should fail on utility
    print("\n  3. Evaluating LOW-VALUE GARBAGE task:")
    r3 = sandbox.evaluate("TEST_GARBAGE", "Do nothing productive",
                          {"task_success": 0.0, "stability": 0.5, "exploration": 0.0})
    print(f"     Score: {r3.score:.3f}  Risk: {r3.risk:.3f}  Approved: {r3.approved}")
    print(f"     Failure modes: {r3.failure_modes}")

    # Feed rejections back to harvester
    for r in [r1, r2, r3]:
        if not r.approved:
            sandbox.reject_to_harvester(r)
            print(f"\n     → Rejected {r.task_id} fed back to FailureHarvester")

    print(f"\n  📊 Stats: {sandbox.stats()}")
    print(f"\n  ✅ EVALUATION SANDBOX OPERATIONAL. POWER TO THE SWARM 🐜⚡")
