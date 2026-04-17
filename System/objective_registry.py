#!/usr/bin/env python3
"""
objective_registry.py — The Decision Gravity Field of the Swarm
═══════════════════════════════════════════════════════════════════
SOLID_PLAN §5.2 item #10 — Objective Function Registry.

This is NOT a dict of wishes. It is the **single source of truth**
for what the swarm considers "good" vs "bad". Every decision in the
system — governor allow/reject, claw prioritization, blackboard
pheromone decay, evaluation scoring — references this registry.

Design rules (architectural invariants):
  1. GLOBAL — same objectives for all agents, all loops
  2. SIMPLE — ≤ 6 objectives; more = incoherence
  3. STABLE — weights change slowly (manual or stress-driven),
              never per-frame
  4. PERSISTED — weights survive restart from .sifta_state/
  5. AUDITABLE — every weight change is logged

Without this module, the swarm optimizes randomly.
With it, the swarm becomes coherent.

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Optional, Callable

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_OBJ_STATE = _STATE_DIR / "objective_registry.json"
_OBJ_LOG = _STATE_DIR / "objective_changes.jsonl"

# ── Default weights (sum = 1.0) ──────────────────────────────────
# These are the swarm's charter. Touch them rarely.
_DEFAULT_OBJECTIVES: Dict[str, float] = {
    "task_success":        0.35,   # Did the action accomplish its goal?
    "stability":           0.25,   # Does the action preserve system health?
    "resource_efficiency": 0.15,   # Does it spend tokens/compute wisely?
    "information_gain":    0.15,   # Does it teach the swarm something new?
    "exploration":         0.10,   # Does it explore uncharted territory?
}


class ObjectiveRegistry:
    """
    The decision gravity field. Every action is scored against these
    weighted objectives. Higher score = more aligned with the swarm's
    charter. Zero score = waste. Negative = harmful.

    Usage:
        reg = ObjectiveRegistry()
        score = reg.score_action(estimates)
        if score < reg.minimum_action_threshold:
            reject()
    """

    def __init__(self, minimum_action_threshold: float = 0.1):
        self.minimum_action_threshold = minimum_action_threshold
        self._weights: Dict[str, float] = dict(_DEFAULT_OBJECTIVES)
        self._load()

    # ── Core API ─────────────────────────────────────────────────

    @property
    def weights(self) -> Dict[str, float]:
        """Current objective weights (read-only copy)."""
        return dict(self._weights)

    @property
    def objective_names(self) -> list[str]:
        return list(self._weights.keys())

    def score_action(self, estimates: Dict[str, float]) -> float:
        """
        Score an action against the objective charter.

        Args:
            estimates: dict mapping objective name -> estimated score [0, 1]
                       for this specific action. Missing objectives = 0.

        Returns:
            Weighted sum in [0, 1]. Higher = more aligned.

        Example:
            reg.score_action({
                "task_success": 0.8,
                "stability": 0.9,
                "resource_efficiency": 0.5,
                "information_gain": 0.3,
                "exploration": 0.1,
            })
        """
        total = 0.0
        for obj, weight in self._weights.items():
            estimate = estimates.get(obj, 0.0)
            # Clamp to [-1, 1] — negative = actively harmful
            estimate = max(-1.0, min(1.0, float(estimate)))
            total += weight * estimate
        return total

    def is_worth_it(self, estimates: Dict[str, float]) -> bool:
        """Quick gate: is this action above minimum threshold?"""
        return self.score_action(estimates) >= self.minimum_action_threshold

    # ── Estimator helpers (heuristic, not ML) ────────────────────

    def estimate_mutation(self, file_path: str, mutation: str,
                          friction: float = 0.0,
                          reversibility: float = 1.0) -> Dict[str, float]:
        """
        Quick heuristic estimates for a code mutation action.
        Returns dict suitable for score_action().
        """
        fp = file_path.replace("\\", "/")

        # Task success: assume positive intent (caller tells us)
        task_success = 0.6

        # Stability: inverse of friction + bonus for reversibility
        stability = max(0.0, 1.0 - friction) * 0.7 + reversibility * 0.3

        # Resource efficiency: small mutations are efficient
        efficiency = max(0.0, 1.0 - len(mutation) / 5000)

        # Information gain: novel mutations teach more
        info_gain = 0.4 if len(mutation) > 50 else 0.1

        # Exploration: touching new paths = exploration
        exploration = 0.3 if "System" not in fp else 0.1

        return {
            "task_success":        task_success,
            "stability":           stability,
            "resource_efficiency": efficiency,
            "information_gain":    info_gain,
            "exploration":         exploration,
        }

    def estimate_claw_action(self, command: str, is_safe: bool) -> Dict[str, float]:
        """
        Quick heuristic estimates for a Claw (sandbox) action.
        """
        return {
            "task_success":        0.5,
            "stability":           0.8 if is_safe else 0.1,
            "resource_efficiency": 0.6,
            "information_gain":    0.3,
            "exploration":         0.2 if is_safe else 0.0,
        }

    # ── Weight management (slow, audited) ────────────────────────

    def set_weight(self, objective: str, new_weight: float,
                   reason: str = "manual") -> bool:
        """
        Update a single objective weight. Logs the change.
        Weights are NOT auto-normalized — caller must ensure sum ~ 1.0.
        Returns False if objective doesn't exist.
        """
        if objective not in self._weights:
            return False
        old = self._weights[objective]
        self._weights[objective] = max(0.0, min(1.0, new_weight))
        self._log_change(objective, old, self._weights[objective], reason)
        self._persist()
        return True

    def stress_shift(self, direction: str = "defensive") -> None:
        """
        Pre-built weight shift for system stress.

        'defensive': ↑ stability, ↓ exploration (under attack / high error)
        'exploratory': ↑ exploration, ↑ info_gain, ↓ stability (calm/idle)
        'reset': return to defaults
        """
        if direction == "defensive":
            self._weights["stability"] = min(0.40, self._weights["stability"] + 0.08)
            self._weights["exploration"] = max(0.02, self._weights["exploration"] - 0.05)
            self._weights["information_gain"] = max(0.05, self._weights["information_gain"] - 0.03)
        elif direction == "exploratory":
            self._weights["exploration"] = min(0.25, self._weights["exploration"] + 0.05)
            self._weights["information_gain"] = min(0.25, self._weights["information_gain"] + 0.03)
            self._weights["stability"] = max(0.10, self._weights["stability"] - 0.05)
        elif direction == "reset":
            self._weights = dict(_DEFAULT_OBJECTIVES)
        else:
            return

        self._log_change("*", 0, 0, f"stress_shift:{direction}")
        self._persist()

    # ── Persistence ──────────────────────────────────────────────

    def _persist(self) -> None:
        try:
            payload = {
                "ts": time.time(),
                "weights": self._weights,
                "threshold": self.minimum_action_threshold,
            }
            _OBJ_STATE.write_text(json.dumps(payload, indent=2))
        except Exception:
            pass

    def _load(self) -> None:
        if not _OBJ_STATE.exists():
            self._persist()  # Write defaults on first boot
            return
        try:
            data = json.loads(_OBJ_STATE.read_text())
            loaded = data.get("weights", {})
            # Only accept known keys — reject garbage
            for k in _DEFAULT_OBJECTIVES:
                if k in loaded:
                    self._weights[k] = float(loaded[k])
            self.minimum_action_threshold = float(
                data.get("threshold", self.minimum_action_threshold)
            )
        except Exception:
            pass

    def _log_change(self, objective: str, old: float, new: float,
                    reason: str) -> None:
        try:
            entry = {
                "ts": time.time(),
                "objective": objective,
                "old": round(old, 4),
                "new": round(new, 4),
                "reason": reason,
            }
            with open(_OBJ_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    # ── Diagnostics ──────────────────────────────────────────────

    def status(self) -> Dict[str, float]:
        """Full status snapshot for UI / telemetry."""
        return {
            "weights": dict(self._weights),
            "threshold": self.minimum_action_threshold,
            "weight_sum": round(sum(self._weights.values()), 4),
        }

    def __repr__(self) -> str:
        parts = " | ".join(f"{k}={v:.2f}" for k, v in self._weights.items())
        return f"<ObjectiveRegistry [{parts}] threshold={self.minimum_action_threshold}>"


# ── Singleton for system-wide access ─────────────────────────────
_INSTANCE: Optional[ObjectiveRegistry] = None


def get_registry() -> ObjectiveRegistry:
    """Get or create the global ObjectiveRegistry singleton."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = ObjectiveRegistry()
    return _INSTANCE


if __name__ == "__main__":
    reg = ObjectiveRegistry()
    print(reg)
    print(f"\nStatus: {json.dumps(reg.status(), indent=2)}")

    # Test scoring
    estimates = {
        "task_success": 0.8,
        "stability": 0.9,
        "resource_efficiency": 0.5,
        "information_gain": 0.3,
        "exploration": 0.1,
    }
    score = reg.score_action(estimates)
    print(f"\nAction score: {score:.4f}")
    print(f"Worth it? {reg.is_worth_it(estimates)}")

    # Test mutation estimate
    mut_est = reg.estimate_mutation("Applications/foo.py", "small fix", 0.2, 0.9)
    mut_score = reg.score_action(mut_est)
    print(f"\nMutation estimate: {mut_est}")
    print(f"Mutation score: {mut_score:.4f}")

    # Test stress shift
    print(f"\nBefore stress: {reg.weights}")
    reg.stress_shift("defensive")
    print(f"After defensive: {reg.weights}")
    reg.stress_shift("reset")
    print(f"After reset: {reg.weights}")
