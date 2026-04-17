#!/usr/bin/env python3
"""
mutation_governor.py — Stability organ for genome-driven mutations
════════════════════════════════════════════════════════════════════
Thermodynamic constraint layer between:

  MycelialGenome (mutation pressure)  →  SCAR / Neural Gate (execution)

Prevents:
  - runaway self-rewrite
  - replay loops (identical mutation spam)
  - hotspot collapse (one file hammered)
  - unbounded global mutation rate

Replay hashes are recorded only on successful commit(), not on rejected
candidates, so failed attempts do not poison future proposals.

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_GOVERNOR_STATE = _STATE_DIR / "mutation_governor.json"

# Cap stored replay hashes to bound memory (FIFO eviction via deque)
_MAX_REPLAY_TRACK = 8000


class MutationGovernor:
    """
    Controls genome-driven mutations with:
    - global rate limiting (per minute)
    - per-file budgets
    - per-file cooldown
    - mutation replay protection (content-hash)
    - risk scoring (System/Kernel paths, large payloads)

    §5.2 Leverage mechanisms (SOLID_PLAN):
    - friction layer: state-disruption cost penalizes noisy mutation
    - reversibility index: low-undo actions require human gate
    - attention budget: hard cap on reads/writes/spawns per cycle
    """

    # ── §5.2.3 Attention budget defaults ─────────────────────────
    ATTENTION_COSTS = {
        "read_trace":    5,
        "analyze_event": 10,
        "write_trace":   8,
        "mutate_file":   15,
        "spawn_agent":   50,
    }

    def __init__(
        self,
        max_mutations_per_minute: int = 5,
        file_budget: int = 10,
        cooldown: float = 30.0,
        risk_threshold: float = 0.7,
        # §5.2 leverage knobs
        friction_ceiling: float = 0.8,
        reversibility_threshold: float = 0.3,
        attention_budget_per_cycle: int = 100,
    ):
        self.max_mutations_per_minute = max_mutations_per_minute
        self.file_budget = file_budget
        self.cooldown = cooldown
        self.risk_threshold = risk_threshold

        # §5.2 leverage
        self.friction_ceiling = friction_ceiling
        self.reversibility_threshold = reversibility_threshold
        self.attention_budget_per_cycle = attention_budget_per_cycle
        self._attention_spent: int = 0
        self._cycle_start: float = time.time()

        self._global_events: deque[float] = deque()
        self._file_budgets: dict[str, int] = defaultdict(lambda: file_budget)
        self._last_mutation_time: dict[str, float] = {}
        self._seen_hashes: deque[str] = deque(maxlen=_MAX_REPLAY_TRACK)
        self._seen_set: set[str] = set()
        self.last_reject_reason: str = ""

        self._load()  # may replace _seen_hashes from disk

    # ── Risk ─────────────────────────────────────────────────────

    def _mutation_content_hash(self, mutation: str) -> str:
        return hashlib.sha256(mutation.encode()).hexdigest()

    def _risk_score(self, file_path: str, mutation: str) -> float:
        score = 0.0
        fp = file_path.replace("\\", "/")

        if "System" in fp:
            score += 0.5
        if "Kernel" in fp:
            score += 0.3
        if len(mutation) > 500:
            score += 0.2

        return min(score, 1.0)

    # ── §5.2.1 Friction layer ────────────────────────────────────

    def friction_cost(self, file_path: str, mutation: str) -> float:
        """
        State disruption cost, not just compute.
        Biology works because change is expensive.
        """
        complexity = min(1.0, len(mutation) / 2000)
        fp = file_path.replace("\\", "/")
        # Magnitude: touching System/ or Kernel/ = high disruption
        magnitude = 0.0
        if "System" in fp:
            magnitude += 0.4
        if "Kernel" in fp:
            magnitude += 0.3
        if "__init__" in fp:
            magnitude += 0.2
        # Novelty penalty: unique hash = novel = higher friction
        h = self._mutation_content_hash(mutation)
        novelty = 0.0 if h in self._seen_set else 0.15
        return min(1.0, complexity + magnitude + novelty)

    # ── §5.2.2 Reversibility index ───────────────────────────────

    def reversibility_score(self, file_path: str, mutation: str) -> float:
        """
        Score undoability [0, 1]. 1.0 = fully reversible.
        Below threshold → require human gate.
        """
        score = 1.0
        fp = file_path.replace("\\", "/")
        # Deleting files is irreversible
        if "delete" in mutation.lower() or "rm " in mutation.lower():
            score -= 0.6
        # System/Kernel mutations are harder to undo safely
        if "System" in fp:
            score -= 0.2
        if "Kernel" in fp:
            score -= 0.3
        # Large mutations are harder to review and revert
        if len(mutation) > 1000:
            score -= 0.15
        return max(0.0, score)

    # ── §5.2.3 Attention budget ──────────────────────────────────

    def _maybe_reset_attention_cycle(self) -> None:
        """Auto-reset attention every 60s (one swarm cycle)."""
        if time.time() - self._cycle_start > 60.0:
            self._attention_spent = 0
            self._cycle_start = time.time()

    def spend_attention(self, action: str = "mutate_file") -> bool:
        """
        Spend attention tokens. Returns True if budget allows.
        Call this from swim loops and blackboard readers.
        """
        self._maybe_reset_attention_cycle()
        cost = self.ATTENTION_COSTS.get(action, 10)
        if self._attention_spent + cost > self.attention_budget_per_cycle:
            return False
        self._attention_spent += cost
        return True

    def attention_remaining(self) -> int:
        """How many attention tokens remain this cycle."""
        self._maybe_reset_attention_cycle()
        return max(0, self.attention_budget_per_cycle - self._attention_spent)

    def reset_attention_cycle(self) -> None:
        """Manual epoch reset for attention budget."""
        self._attention_spent = 0
        self._cycle_start = time.time()

    # ── Global rate ──────────────────────────────────────────────

    def _global_allowed(self) -> bool:
        now = time.time()
        while self._global_events and now - self._global_events[0] > 60.0:
            self._global_events.popleft()
        return len(self._global_events) < self.max_mutations_per_minute

    def _file_allowed(self, file_path: str) -> bool:
        last = self._last_mutation_time.get(file_path, 0.0)
        return (time.time() - last) > self.cooldown

    def _track_seen(self, h: str) -> None:
        if h in self._seen_set:
            return
        mx = self._seen_hashes.maxlen
        if mx is not None and len(self._seen_hashes) == mx:
            old = self._seen_hashes[0]
            self._seen_set.discard(old)
        self._seen_hashes.append(h)
        self._seen_set.add(h)

    # ── Public API ───────────────────────────────────────────────

    def allow(self, file_path: str, mutation: str) -> bool:
        """
        Return True if this mutation may enter the SCAR proposal pipeline.
        Does not record replay hash — call commit() only after SCAR accepts.

        Gate order: replay → rate → cooldown → budget → risk →
                    §5.2 friction → §5.2 reversibility → §5.2 attention
        """
        self.last_reject_reason = ""

        h = self._mutation_content_hash(mutation)
        if h in self._seen_set:
            self.last_reject_reason = "replay"
            return False

        if not self._global_allowed():
            self.last_reject_reason = "global_rate"
            return False

        if not self._file_allowed(file_path):
            self.last_reject_reason = "cooldown"
            return False

        if self._file_budgets[file_path] <= 0:
            self.last_reject_reason = "file_budget"
            return False

        risk = self._risk_score(file_path, mutation)
        if risk > self.risk_threshold:
            self.last_reject_reason = f"risk:{risk:.2f}"
            return False

        # ── §5.2.1 Friction gate ─────────────────────────────────
        friction = self.friction_cost(file_path, mutation)
        if friction > self.friction_ceiling:
            self.last_reject_reason = f"friction:{friction:.2f}"
            return False

        # ── §5.2.2 Reversibility gate ────────────────────────────
        rev = self.reversibility_score(file_path, mutation)
        if rev < self.reversibility_threshold:
            self.last_reject_reason = f"reversibility:{rev:.2f}"
            return False

        # ── §5.2.3 Attention gate ────────────────────────────────
        if not self.spend_attention("mutate_file"):
            self.last_reject_reason = "attention_exhausted"
            return False

        # ── §5.2.10 Objective worth gate ─────────────────────────
        # Final question: is this mutation WORTH IT?
        try:
            from objective_registry import get_registry
            reg = get_registry()
            estimates = reg.estimate_mutation(
                file_path, mutation,
                friction=friction, reversibility=rev
            )
            if not reg.is_worth_it(estimates):
                self.last_reject_reason = f"objective_score:{reg.score_action(estimates):.2f}"
                return False
        except ImportError:
            pass  # Registry not available — degrade gracefully

        # ── §5.2.7 Shadow Simulation gate ────────────────────────
        # Ultimate sanity check: does the code compile?
        if file_path.endswith('.py'):
            try:
                try:
                    from System.shadow_simulator import get_simulator
                except ImportError:
                    from shadow_simulator import get_simulator
                sim = get_simulator()
                sim_ok, sim_msg = sim.simulate_mutation(file_path, mutation)
                if not sim_ok:
                    self.last_reject_reason = f"shadow_simulation_failed"
                    return False
            except ImportError:
                pass  # Simulator not available

        return True

    def commit(self, file_path: str, mutation: str) -> None:
        """Call after a mutation is successfully proposed to SCAR."""
        h = self._mutation_content_hash(mutation)
        self._track_seen(h)
        self._global_events.append(time.time())
        self._file_budgets[file_path] -= 1
        self._last_mutation_time[file_path] = time.time()
        self._persist()

    def reset_budgets(self) -> None:
        """Optional epoch reset — nudge depleted files back toward 1."""
        for k in list(self._file_budgets.keys()):
            self._file_budgets[k] = max(self._file_budgets[k], 1)
        self._persist()

    def _persist(self) -> None:
        try:
            payload = {
                "ts": time.time(),
                "file_budgets": dict(self._file_budgets),
                "last_mutation_time": self._last_mutation_time,
                "seen_hashes": list(self._seen_hashes),
            }
            _GOVERNOR_STATE.write_text(json.dumps(payload, indent=1))
        except Exception:
            pass

    def _load(self) -> None:
        if not _GOVERNOR_STATE.exists():
            return
        try:
            data = json.loads(_GOVERNOR_STATE.read_text())
            self._file_budgets = defaultdict(
                lambda: self.file_budget,
                data.get("file_budgets", {}),
            )
            self._last_mutation_time = data.get("last_mutation_time", {})
            hashes = data.get("seen_hashes", [])
            self._seen_hashes = deque(hashes, maxlen=_MAX_REPLAY_TRACK)
            self._seen_set = set(self._seen_hashes)
        except Exception:
            pass


if __name__ == "__main__":
    g = MutationGovernor()
    ok = g.allow("System/foo.py", "hello")
    print("allow1", ok, g.last_reject_reason)
    if ok:
        g.commit("System/foo.py", "hello")
    ok2 = g.allow("System/foo.py", "hello")
    print("allow2_replay", ok2, g.last_reject_reason)
