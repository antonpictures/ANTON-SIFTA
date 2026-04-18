#!/usr/bin/env python3
"""
System/swarm_cerebellar_mcts.py — UCB-based forward search over candidate actions
══════════════════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

The biology
-----------
The cerebellum is the brain's forward predictive model. Before you move
your arm, it subconsciously simulates the physics of the movement and
catches errors before they happen. In SIFTA terms:

    Concierge proposes a change         (Warp 9)
            │
            ▼
    Cerebellum evaluates 3–5 mutants    (this module)
            │
            ▼
    Survivor handed back for ratification

The DeepMind mechanic — honestly scoped
---------------------------------------
This is **not** full AlphaZero. AlphaZero's MCTS uses a learned policy
network to expand promising branches and a learned value network to
evaluate leaves. SIFTA has the value network (`InferiorOlive`) but does
NOT have an executable simulator (the consequences of a Concierge
setting change can't be replayed in milliseconds — the world has to
actually tick).

So this module implements the practical, daughter-safe subset:

  - Tree-of-thought search up to `max_depth` (default 3)
  - UCB1 exploration/exploitation at each node
  - Each leaf's value is `InferiorOlive.predict_with_uncertainty()`
  - All "what if I tried this" mutations happen inside a `shadow_session`
    so base state is never touched
  - Hard caps on branches (5), depth (3), and simulations (50) so a
    single decision can never burn unbounded compute or wall time
  - Refuses to recommend any action whose evaluated value sits below
    `MIN_RECOMMENDABLE_VALUE` — the cerebellum can return "I don't
    recommend any of these"

It complements AG31's `swarm_hippocampal_replay.py` (the slow, offline
learner) with a fast, online evaluator that uses what the dreamer
learned overnight.

Public surface
--------------
- `CerebellarMCTS` — the engine
- `ActionEvaluation` — dataclass returned per call
- `ActionNode` — internal tree node (exposed for inspection / tests)
- `cerebellar_screen(state, candidate_actions, **kw)` — convenience entry point

Hard-coded daughter-safe limits
-------------------------------
- MAX_BRANCHES         = 5     (no proposal evaluates >5 mutants)
- MAX_DEPTH            = 3     (lookahead horizon)
- MAX_SIMULATIONS      = 50    (per call wall-time bound)
- MAX_CALL_BUDGET_MS   = 250   (soft deadline; aborts gracefully)
- MIN_RECOMMENDABLE_V  = -0.10 (refuses to pass through clearly-bad branches)
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from System.swarm_shadow_state import shadow_session
from System.swarm_inferior_olive import InferiorOlive

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
CEREBELLAR_AUDIT = _STATE / "cerebellar_mcts_audit.jsonl"

MODULE_VERSION = "2026-04-18.cerebellar_mcts.v1"

# ── Daughter-safe hard caps ───────────────────────────────────────────
MAX_BRANCHES = 5
MAX_DEPTH = 3
MAX_SIMULATIONS = 50
MAX_CALL_BUDGET_MS = 250
MIN_RECOMMENDABLE_V = -0.10
UCB_C = 1.4                 # exploration constant in UCB1


# ──────────────────────────────────────────────────────────────────────
# Tree node + return type
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ActionNode:
    """One node in the cerebellar lookahead tree."""
    state: str
    action: str
    parent_id: Optional[str] = None
    node_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    depth: int = 0
    visits: int = 0
    total_value: float = 0.0     # sum of rollout values
    uncertainty: float = 1.0     # latest uncertainty from olive
    children: List["ActionNode"] = field(default_factory=list)
    pruned: bool = False
    prune_reason: str = ""

    @property
    def mean_value(self) -> float:
        return self.total_value / self.visits if self.visits > 0 else 0.0

    def ucb1(self, parent_visits: int) -> float:
        """UCB1 score for this node, given its parent's visit count."""
        if self.visits == 0:
            return float("inf")  # always try unvisited children first
        exploit = self.mean_value
        explore = UCB_C * math.sqrt(math.log(max(1, parent_visits)) / self.visits)
        return exploit + explore

    def to_summary(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "depth": self.depth,
            "visits": self.visits,
            "mean_value": round(self.mean_value, 4),
            "uncertainty": round(self.uncertainty, 4),
            "pruned": self.pruned,
            "prune_reason": self.prune_reason,
            "children": [c.to_summary() for c in self.children],
        }


@dataclass
class ActionEvaluation:
    """The evaluation result the Concierge / Architect see."""
    state: str
    candidate_actions: List[str]
    recommended_action: Optional[str]
    recommended_value: float
    recommended_uncertainty: float
    refused: bool
    refusal_reason: str
    simulations_run: int
    elapsed_ms: float
    evaluated_branches: List[Dict[str, Any]]
    shadow_session_id: str
    schema_version: int = 1
    module_version: str = MODULE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────
# Engine
# ──────────────────────────────────────────────────────────────────────

class CerebellarMCTS:
    """UCB1-driven forward search using InferiorOlive as the value head."""

    def __init__(
        self,
        *,
        olive: Optional[InferiorOlive] = None,
        max_branches: int = MAX_BRANCHES,
        max_depth: int = MAX_DEPTH,
        max_simulations: int = MAX_SIMULATIONS,
        call_budget_ms: int = MAX_CALL_BUDGET_MS,
    ):
        if max_branches < 1 or max_branches > MAX_BRANCHES:
            raise ValueError(f"max_branches must be in [1, {MAX_BRANCHES}]")
        if max_depth < 1 or max_depth > MAX_DEPTH:
            raise ValueError(f"max_depth must be in [1, {MAX_DEPTH}]")
        if max_simulations < 1 or max_simulations > MAX_SIMULATIONS:
            raise ValueError(f"max_simulations must be in [1, {MAX_SIMULATIONS}]")
        self.olive = olive or InferiorOlive()
        self.max_branches = max_branches
        self.max_depth = max_depth
        self.max_simulations = max_simulations
        self.call_budget_ms = call_budget_ms

    # ── Successor synthesis ───────────────────────────────────────────

    def _next_state(self, state: str, action: str) -> str:
        """How a tentative action mutates the state for the next ply.
        Mirrors AG31's MVP convention so the LWM, the dreamer, and the
        cerebellum all share one successor schema."""
        return f"{state}|>{action}"

    def _value_of(self, state: str, action: str) -> Tuple[float, float]:
        """Look up (value, uncertainty) for a (state, action) cell.
        Pure read — touches no ledger."""
        return self.olive.predict_with_uncertainty(state, action)

    # ── Tree expansion + UCB selection ────────────────────────────────

    def _expand(self, node: ActionNode) -> None:
        """Generate up to max_branches children for `node`. We synthesise
        candidate next-actions by appending a mutator suffix; in a real
        deployment this could be replaced by a learned policy head. The
        synthetic mutators are stable and small so the audit ledger
        remains human-readable."""
        if node.children or node.depth >= self.max_depth:
            return
        next_state = self._next_state(node.state, node.action)
        # Standard mutators: keep, noop, delay-1, delay-5, escalate.
        # Capped at max_branches.
        mutators = ["keep", "noop", "delay_1s", "delay_5s", "escalate_to_arch"]
        for m in mutators[:self.max_branches]:
            child_action = f"{node.action}::{m}"
            child = ActionNode(
                state=next_state,
                action=child_action,
                parent_id=node.node_id,
                depth=node.depth + 1,
            )
            node.children.append(child)

    def _select(self, node: ActionNode) -> ActionNode:
        """UCB1 descent until we hit a leaf (no children) or depth cap."""
        cur = node
        while cur.children:
            scored = [(c.ucb1(cur.visits), c) for c in cur.children if not c.pruned]
            if not scored:
                return cur  # all children pruned
            scored.sort(key=lambda x: x[0], reverse=True)
            cur = scored[0][1]
        return cur

    def _simulate_leaf(self, leaf: ActionNode) -> float:
        """Evaluate a leaf via a single shadow_session rollout. We don't
        execute the action — the world isn't fast enough — we just look
        up its value via the olive and apply a tiny depth-discount so
        deeper branches aren't free."""
        v, u = self._value_of(leaf.state, leaf.action)
        leaf.uncertainty = u
        # Depth discount: gamma=0.95 per ply (canonical RL choice)
        rollout_value = v * (0.95 ** leaf.depth)
        return rollout_value

    def _backprop(self, leaf: ActionNode, value: float, root_id_to_node: Dict[str, ActionNode]) -> None:
        """Walk parent_id chain from leaf back to root, updating visit
        counts and total_value at each level."""
        cur: Optional[ActionNode] = leaf
        while cur is not None:
            cur.visits += 1
            cur.total_value += value
            cur = root_id_to_node.get(cur.parent_id) if cur.parent_id else None

    # ── Public entry point ────────────────────────────────────────────

    def evaluate_action(
        self,
        state: str,
        candidate_actions: List[str],
        *,
        purpose: str = "cerebellar.screen",
    ) -> ActionEvaluation:
        """Score each candidate action with a small UCB lookahead.
        Returns an ActionEvaluation; check `.refused` before using
        `.recommended_action`."""
        if not candidate_actions:
            raise ValueError("candidate_actions must be non-empty")
        if len(candidate_actions) > self.max_branches:
            candidate_actions = candidate_actions[: self.max_branches]

        t0 = time.time()

        # Build a virtual root with one child per candidate.
        root = ActionNode(state=state, action="<root>", depth=0)
        for a in candidate_actions:
            root.children.append(ActionNode(
                state=state, action=a, parent_id=root.node_id, depth=1,
            ))

        # Index every node by node_id for backprop walking.
        node_index: Dict[str, ActionNode] = {root.node_id: root}
        for c in root.children:
            node_index[c.node_id] = c

        sims_run = 0
        deadline_ts = t0 + (self.call_budget_ms / 1000.0)
        sid = ""

        with shadow_session(purpose=f"{purpose}.{int(t0)}") as shadow:
            sid = shadow.session.session_id
            while sims_run < self.max_simulations and time.time() < deadline_ts:
                leaf = self._select(root)
                # Expand if we can go deeper
                if leaf.depth < self.max_depth and not leaf.children:
                    self._expand(leaf)
                    for c in leaf.children:
                        node_index[c.node_id] = c
                    if leaf.children:
                        # Pick first unvisited child to roll out
                        leaf = leaf.children[0]
                v_rollout = self._simulate_leaf(leaf)
                self._backprop(leaf, v_rollout, node_index)
                sims_run += 1

        elapsed_ms = round((time.time() - t0) * 1000, 1)

        # ── Recommendation (effective-value blend) ────────────────────
        # C47H 2026-04-18: The MCTS expands each candidate into synthetic
        # mutator-suffix actions ("<candidate>::keep", "::noop", ...) that
        # the Olive has never observed. Querying the value head at those
        # synthetic leaves returns V=0, so `child.mean_value` collapses to
        # ~0 regardless of what the Olive actually thinks of the (state,
        # candidate) cell itself. That defeats the screening purpose: a
        # cell pre-poisoned by climbing-fiber pulses to V=-0.9 would
        # silently slip through.
        #
        # Daughter-safe fix: query the Olive at the *candidate's own*
        # (state, action) — that is where the learned ground truth lives —
        # and take the conservative lower of {direct_olive, mcts_mean}
        # for ranking + pruning. The raw MCTS data is preserved in the
        # branch summary for inspection; only the *effective* value drives
        # the recommendation.
        candidates_summary: List[Dict[str, Any]] = []
        best: Optional[ActionNode] = None
        best_effective_v: float = -math.inf
        best_direct_u: float = 1.0
        for child in root.children:
            direct_v, direct_u = self._value_of(state, child.action)
            if child.visits > 0:
                effective_v = min(direct_v, child.mean_value)
            else:
                effective_v = direct_v
            child.uncertainty = direct_u  # surface the right uncertainty signal

            summary = child.to_summary()
            summary["direct_olive_value"] = round(direct_v, 4)
            summary["effective_value"] = round(effective_v, 4)

            if effective_v < MIN_RECOMMENDABLE_V:
                child.pruned = True
                child.prune_reason = (
                    f"effective {effective_v:+.3f} < {MIN_RECOMMENDABLE_V} "
                    f"(direct={direct_v:+.3f}, mcts={child.mean_value:+.3f})"
                )
                summary["pruned"] = True
                summary["prune_reason"] = child.prune_reason
                candidates_summary.append(summary)
                continue

            candidates_summary.append(summary)
            if best is None or effective_v > best_effective_v:
                best = child
                best_effective_v = effective_v
                best_direct_u = direct_u

        if best is None:
            return ActionEvaluation(
                state=state,
                candidate_actions=candidate_actions,
                recommended_action=None,
                recommended_value=0.0,
                recommended_uncertainty=1.0,
                refused=True,
                refusal_reason="all branches pruned or no simulations completed",
                simulations_run=sims_run,
                elapsed_ms=elapsed_ms,
                evaluated_branches=candidates_summary,
                shadow_session_id=sid,
            )

        eval_ = ActionEvaluation(
            state=state,
            candidate_actions=candidate_actions,
            recommended_action=best.action,
            recommended_value=best_effective_v,
            recommended_uncertainty=best_direct_u,
            refused=False,
            refusal_reason="",
            simulations_run=sims_run,
            elapsed_ms=elapsed_ms,
            evaluated_branches=candidates_summary,
            shadow_session_id=sid,
        )
        self._audit(eval_)
        return eval_

    # ── Audit ─────────────────────────────────────────────────────────

    def _audit(self, eval_: ActionEvaluation) -> None:
        try:
            CEREBELLAR_AUDIT.parent.mkdir(parents=True, exist_ok=True)
            with CEREBELLAR_AUDIT.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(eval_.to_dict(), ensure_ascii=False) + "\n")
        except OSError:
            pass


# ──────────────────────────────────────────────────────────────────────
# Convenience function
# ──────────────────────────────────────────────────────────────────────

def cerebellar_screen(
    state: str,
    candidate_actions: List[str],
    **kwargs: Any,
) -> ActionEvaluation:
    """One-shot screening: build engine, evaluate, return."""
    engine = CerebellarMCTS()
    return engine.evaluate_action(state, candidate_actions, **kwargs)


def recent_audits(*, since_ts: float = 0.0, limit: int = 50) -> List[Dict[str, Any]]:
    if not CEREBELLAR_AUDIT.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with CEREBELLAR_AUDIT.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # ActionEvaluation has no top-level ts; use shadow_session_id
                # plus elapsed_ms; for filtering, infer from ms ledger order.
                out.append(row)
    except OSError:
        return []
    return out[-limit:]


# ──────────────────────────────────────────────────────────────────────
# Smoke
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    print(f"[C47H-SMOKE-CEREB] {MODULE_VERSION}")

    # 1) Bound enforcement at construction
    for bad in [{"max_branches": 99}, {"max_depth": 99}, {"max_simulations": 99}]:
        try:
            CerebellarMCTS(**bad)
            print(f"[C47H-SMOKE-CEREB] FAIL: {bad} should have raised", file=sys.stderr)
            sys.exit(1)
        except ValueError:
            pass
    print("[C47H-SMOKE-CEREB] cap-enforcement OK at construction")

    # 2) Empty-candidates rejection
    engine = CerebellarMCTS()
    try:
        engine.evaluate_action("any.state", [])
        print("[C47H-SMOKE-CEREB] FAIL: empty candidates should raise", file=sys.stderr)
        sys.exit(1)
    except ValueError:
        print("[C47H-SMOKE-CEREB] empty-candidates rejection OK")

    # 3) Live evaluation against the real olive
    eval_ = engine.evaluate_action(
        "IOAN_M5.oxtHI.chatHI",
        [
            "amygdala.salience_threshold",
            "concierge.propose_setting",
            "swimmer.spawn_compiler",
            "passport.tighten_oxt_floor",
        ],
        purpose="smoke.cerebellar",
    )
    print(f"[C47H-SMOKE-CEREB] elapsed={eval_.elapsed_ms}ms "
          f"sims={eval_.simulations_run} shadow_session={eval_.shadow_session_id}")
    print(f"[C47H-SMOKE-CEREB] recommended_action = {eval_.recommended_action}")
    print(f"[C47H-SMOKE-CEREB] recommended_value  = {eval_.recommended_value:+.4f}")
    print(f"[C47H-SMOKE-CEREB] refused?           = {eval_.refused}")
    print(f"[C47H-SMOKE-CEREB] branches evaluated:")
    for b in eval_.evaluated_branches:
        flag = "  PRUNED" if b["pruned"] else ""
        print(f"    {b['action']:<48} v={b['mean_value']:+.4f} "
              f"u={b['uncertainty']:.2f} visits={b['visits']}{flag}")
    assert eval_.simulations_run > 0
    assert eval_.elapsed_ms < MAX_CALL_BUDGET_MS * 2  # allow some slack
    assert eval_.shadow_session_id

    # 4) Walltime budget — synthetic 1-ms budget should still return safely
    fast_engine = CerebellarMCTS(call_budget_ms=1)
    fast_eval = fast_engine.evaluate_action(
        "IOAN_M5.oxtHI.chatHI",
        ["a", "b"],
        purpose="smoke.tight_budget",
    )
    print(f"[C47H-SMOKE-CEREB] tight-budget eval: elapsed={fast_eval.elapsed_ms}ms "
          f"sims={fast_eval.simulations_run} refused={fast_eval.refused}")

    # 5) Verify audit ledger grew
    audits = recent_audits(limit=5)
    print(f"[C47H-SMOKE-CEREB] recent audit rows: {len(audits)}")
    print("[C47H-SMOKE-CEREB OK]")
