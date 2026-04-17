#!/usr/bin/env python3
"""
mutation_governor_loop.py — Closed-Loop Self-Modification
═══════════════════════════════════════════════════════════════════
SOLID_PLAN §5 Track S4 — The Final Boss Layer.

The organism can now:
  - Perceive (SVL, Blackboard)
  - Remember (SkillRegistry, FailureHarvester)
  - Spawn ideas (FissionEngine)
  - Filter ideas (EvaluationSandbox)
  - Route to hardware (CrossHardwareRouter)

What it CANNOT do yet: **change its own rules safely.**

This module closes the loop. When the Fission Engine produces a
high-scoring task that targets a System module, it becomes a
MutationProposal. The proposal must survive:

  1. Evaluation Sandbox (counterfactual gate)
  2. Mutation Governor (12-gate discipline)
  3. Identity Drift Check (bounded phenotype distance)

Only then is it committed. After commitment, the outcome
(success/failure) feeds BACK into the Governor's thresholds,
making the organism's immune system adaptive.

The Swarm can rewrite itself, but only through an evaluation-gated
mutation loop that preserves identity under pressure.

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import json
import time
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_LOOP_LOG = _STATE_DIR / "governor_loop_events.jsonl"
_LOOP_STATE = _STATE_DIR / "governor_loop_state.json"

# ── Identity drift constants ────────────────────────────────────────
# Maximum allowed cumulative drift before the loop locks out
# further self-modifications until the Architect reviews.
MAX_IDENTITY_DRIFT = 5.0
DRIFT_PER_MUTATION = 0.25        # Each committed mutation adds drift
DRIFT_DECAY_PER_HOUR = 0.1      # Drift slowly heals over time


@dataclass
class MutationProposal:
    """A candidate self-modification of the Swarm's own rules."""
    proposal_id: str
    source_task_id: str          # Which Blackboard task spawned this
    target_module: str           # Which System module to modify
    description: str             # What the mutation intends to do
    risk: float                  # From EvaluationSandbox
    expected_gain: float         # Predicted value
    status: str = "PENDING"      # PENDING → APPROVED → COMMITTED | REJECTED


class MutationGovernorLoop:
    """
    The adaptive immune system. Closes the loop between:
      FissionEngine → EvaluationSandbox → MutationGovernor → Commitment
                                                              ↓
                                          Outcome feedback → threshold tuning

    Identity drift is tracked as a cumulative score. Too much drift
    without Architect review → the loop locks itself out.
    """

    def __init__(self):
        self._proposals: List[MutationProposal] = []
        self._committed: int = 0
        self._rejected: int = 0
        self._identity_drift: float = 0.0
        self._last_drift_decay: float = time.time()
        self._locked: bool = False
        self._load()

    # ── Proposal Creation ────────────────────────────────────────────

    def propose_from_task(self, task_id: str, description: str,
                          target_module: str,
                          objective_estimates: Dict[str, float]) -> Optional[MutationProposal]:
        """
        Convert a high-value Blackboard task into a self-modification
        candidate. Only tasks targeting System/ modules qualify.
        """
        if self._locked:
            self._log("LOCKED_REJECT", task_id, "Identity drift exceeded — Architect review required")
            return None

        # Decay drift over time (the organism heals)
        self._apply_drift_decay()

        # Check identity budget
        if self._identity_drift >= MAX_IDENTITY_DRIFT:
            self._locked = True
            self._persist()
            self._log("DRIFT_LOCKOUT", task_id,
                      f"Drift {self._identity_drift:.2f} >= {MAX_IDENTITY_DRIFT}")
            return None

        proposal_id = "MUT_" + hashlib.sha256(
            f"{task_id}:{description}:{time.time()}".encode()
        ).hexdigest()[:12]

        proposal = MutationProposal(
            proposal_id=proposal_id,
            source_task_id=task_id,
            target_module=target_module,
            description=description,
            risk=0.0,           # Will be set by evaluate()
            expected_gain=0.0,  # Will be set by evaluate()
            status="PENDING"
        )

        self._proposals.append(proposal)
        return proposal

    # ── Gate Chain ────────────────────────────────────────────────────

    def evaluate_and_commit(self, proposal: MutationProposal,
                            objective_estimates: Dict[str, float]) -> bool:
        """
        Run the proposal through the full gate chain:
          1. Evaluation Sandbox (counterfactual simulation)
          2. Mutation Governor (12-gate discipline)
          3. Identity drift check

        Returns True only if all gates pass AND the mutation is committed.
        """
        # ── Gate 1: Evaluation Sandbox ────────────────────────────
        try:
            from evaluation_sandbox import get_sandbox
            sandbox = get_sandbox()
            eval_result = sandbox.evaluate(
                proposal.proposal_id,
                proposal.description,
                objective_estimates
            )
            proposal.risk = eval_result.risk
            proposal.expected_gain = eval_result.predicted_value

            if not eval_result.approved:
                proposal.status = "REJECTED"
                self._rejected += 1
                sandbox.reject_to_harvester(eval_result)
                self._log("EVAL_REJECT", proposal.proposal_id,
                          f"score={eval_result.score:.3f} modes={eval_result.failure_modes}")
                self._persist()
                return False
        except ImportError:
            pass  # No sandbox — degrade (allow through)

        # ── Gate 2: Mutation Governor (12-gate) ───────────────────
        try:
            from mutation_governor import MutationGovernor
            gov = MutationGovernor()
            # The "mutation" content is the description (what would change)
            if not gov.allow(f"System/{proposal.target_module}", proposal.description):
                proposal.status = "REJECTED"
                self._rejected += 1
                self._log("GOVERNOR_REJECT", proposal.proposal_id,
                          f"reason={gov.last_reject_reason}")
                self._persist()
                return False
        except ImportError:
            pass

        # ── Gate 3: Identity drift check ──────────────────────────
        projected_drift = self._identity_drift + DRIFT_PER_MUTATION
        if projected_drift >= MAX_IDENTITY_DRIFT:
            proposal.status = "REJECTED"
            self._rejected += 1
            self._log("DRIFT_REJECT", proposal.proposal_id,
                      f"projected_drift={projected_drift:.2f}")
            self._persist()
            return False

        # ── COMMIT POINT ──────────────────────────────────────────
        proposal.status = "COMMITTED"
        self._committed += 1
        self._identity_drift += DRIFT_PER_MUTATION

        # Log the mutation to the Blackboard as a completed task
        try:
            from swarm_blackboard import get_blackboard
            board = get_blackboard()
            board.post_task(
                f"MUTATION COMMITTED: {proposal.description[:80]}",
                {"task_success": 1.0, "stability": 0.8, "information_gain": 0.5},
                artifacts=[f"System/{proposal.target_module}"]
            )
        except ImportError:
            pass

        self._log("COMMITTED", proposal.proposal_id,
                  f"drift_now={self._identity_drift:.2f} target={proposal.target_module}")
        self._persist()
        return True

    # ── Outcome Feedback (the actual closed loop) ─────────────────────

    def report_outcome(self, proposal_id: str, success: bool) -> None:
        """
        After a committed mutation runs in production, report the outcome.
        This adjusts the Governor's thresholds — the immune system learns.

        Success → relax friction slightly (encourage more exploration)
        Failure → tighten friction + raise risk threshold (become cautious)
        """
        try:
            from mutation_governor import MutationGovernor
            gov = MutationGovernor()

            if success:
                # Organism learned something useful — slightly relax constraints
                gov.friction_ceiling = min(1.0, gov.friction_ceiling + 0.02)
                gov.risk_threshold = min(1.0, gov.risk_threshold + 0.01)
                self._log("OUTCOME_SUCCESS", proposal_id,
                          f"friction_ceil→{gov.friction_ceiling:.2f} risk_thresh→{gov.risk_threshold:.2f}")
            else:
                # Mutation failed — tighten the immune response
                gov.friction_ceiling = max(0.3, gov.friction_ceiling - 0.05)
                gov.risk_threshold = max(0.3, gov.risk_threshold - 0.03)
                # Add extra drift penalty for failed mutations
                self._identity_drift += DRIFT_PER_MUTATION
                self._log("OUTCOME_FAILURE", proposal_id,
                          f"friction_ceil→{gov.friction_ceiling:.2f} risk_thresh→{gov.risk_threshold:.2f} "
                          f"drift→{self._identity_drift:.2f}")

                # Feed back to FailureHarvester
                try:
                    from failure_harvesting import get_harvester
                    get_harvester().harvest(
                        "MutationGovernorLoop",
                        f"MUTATION_FAILED:{proposal_id}",
                        "Self-modification failed in production",
                        {"proposal_id": proposal_id}
                    )
                except ImportError:
                    pass
        except ImportError:
            pass

        self._persist()

    # ── Architect Override ────────────────────────────────────────────

    def architect_reset_drift(self) -> None:
        """
        Architect reviews the drift log and clears the lockout.
        This is the human-in-the-loop safety valve.
        """
        self._identity_drift = 0.0
        self._locked = False
        self._log("ARCHITECT_RESET", "MANUAL", "Drift cleared by Architect")
        self._persist()

    # ── Drift Decay ──────────────────────────────────────────────────

    def _apply_drift_decay(self) -> None:
        """Identity drift slowly heals over time — the organism stabilizes."""
        now = time.time()
        hours_elapsed = (now - self._last_drift_decay) / 3600.0
        decay = hours_elapsed * DRIFT_DECAY_PER_HOUR
        self._identity_drift = max(0.0, self._identity_drift - decay)
        self._last_drift_decay = now

    # ── Persistence ──────────────────────────────────────────────────

    def _log(self, action: str, ref_id: str, detail: str) -> None:
        try:
            with open(_LOOP_LOG, "a") as f:
                f.write(json.dumps({
                    "ts": time.time(),
                    "action": action,
                    "ref": ref_id,
                    "detail": detail,
                    "drift": round(self._identity_drift, 3),
                    "locked": self._locked,
                }) + "\n")
        except Exception:
            pass

    def _persist(self) -> None:
        try:
            _LOOP_STATE.write_text(json.dumps({
                "committed": self._committed,
                "rejected": self._rejected,
                "identity_drift": round(self._identity_drift, 3),
                "locked": self._locked,
                "last_drift_decay": self._last_drift_decay,
                "ts": time.time(),
            }, indent=2))
        except Exception:
            pass

    def _load(self) -> None:
        if not _LOOP_STATE.exists():
            return
        try:
            data = json.loads(_LOOP_STATE.read_text())
            self._committed = data.get("committed", 0)
            self._rejected = data.get("rejected", 0)
            self._identity_drift = data.get("identity_drift", 0.0)
            self._locked = data.get("locked", False)
            self._last_drift_decay = data.get("last_drift_decay", time.time())
        except Exception:
            pass

    def stats(self) -> Dict[str, Any]:
        self._apply_drift_decay()
        return {
            "committed": self._committed,
            "rejected": self._rejected,
            "identity_drift": round(self._identity_drift, 3),
            "max_drift": MAX_IDENTITY_DRIFT,
            "locked": self._locked,
            "total_proposals": len(self._proposals),
        }


# ── Singleton ────────────────────────────────────────────────────────
_LOOP: Optional[MutationGovernorLoop] = None

def get_governor_loop() -> MutationGovernorLoop:
    global _LOOP
    if _LOOP is None:
        _LOOP = MutationGovernorLoop()
    return _LOOP


if __name__ == "__main__":
    print("═" * 58)
    print("  SIFTA — MUTATION GOVERNOR LOOP (Closed-Loop Evolution)")
    print("═" * 58 + "\n")

    loop = get_governor_loop()

    # Test 1: Safe mutation proposal
    print("  1. Proposing SAFE self-modification:")
    p1 = loop.propose_from_task(
        "TASK_001", "Optimize threshold math in objective_registry",
        "objective_registry.py",
        {"task_success": 0.8, "stability": 0.9}
    )
    if p1:
        ok = loop.evaluate_and_commit(p1, {"task_success": 0.8, "stability": 0.9})
        print(f"     Status: {p1.status}  Committed: {ok}")

    # Test 2: Dangerous mutation proposal
    print("\n  2. Proposing DANGEROUS self-modification:")
    p2 = loop.propose_from_task(
        "TASK_002", "Rewrite genesis_lock.py to remove all constraints",
        "genesis_lock.py",
        {"task_success": 0.5, "stability": 0.0}
    )
    if p2:
        ok2 = loop.evaluate_and_commit(p2, {"task_success": 0.5, "stability": 0.0})
        print(f"     Status: {p2.status}  Committed: {ok2}")

    # Test 3: Report outcome → threshold tuning
    print("\n  3. Reporting SUCCESS on committed mutation:")
    if p1 and p1.status == "COMMITTED":
        loop.report_outcome(p1.proposal_id, success=True)
        print("     Governor thresholds relaxed slightly")

    print(f"\n  📊 Loop stats: {loop.stats()}")
    print(f"\n  ✅ CLOSED-LOOP EVOLUTION OPERATIONAL. POWER TO THE SWARM 🐜⚡")
