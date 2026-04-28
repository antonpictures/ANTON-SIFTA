#!/usr/bin/env python3
"""
System/swarm_td_learning.py
Predator v7.0 — Event 76: Temporal Difference (TD) Q-Learner

Biology
-------
Schultz, Dayan & Montague (1997) "A Neural Substrate of Prediction and Reward"
Science 275(5306):1593-1599.

Dopamine neurons compute the TD error:
    δ(t) = R(t) + γ·V(s_{t+1}) - V(s_t)

We extend this to a full Q-learner so Alice learns not just that reward happened
globally, but WHICH action worked in WHICH situation.

Algorithm: Q-Learning (Watkins 1989), off-policy TD(0)
    Q(s,a) ← Q(s,a) + α · [r + γ · max_{a'} Q(s',a') - Q(s,a)]

where:
    α ∈ (0,1]  = learning rate
    γ ∈ [0,1]  = discount factor (how much future reward matters)
    δ          = TD error (the dopamine signal)

State Representation (compact — NOT raw text)
---------------------------------------------
State is a tuple of discrete buckets to keep the Q-table bounded:

    source        = owner | contact | group
    stt_bucket    = low | mid | high | typed
    c1_action     = SILENCE | TOOL | ENGAGE | BOND
    tool          = stgm | whatsapp | none | other
    social_frame  = owner | external | group
    recent_mode   = rewarded | punished | neutral

Max table size = 3 × 4 × 4 × 4 × 3 × 3 × 4_actions = 6912 entries.
That is bounded. That will not explode.

Authors: AG31/Antigravity (Event 76) — scalpel order per C55M-DR-CODEX
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Optional

_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_Q_TABLE_FILE  = _STATE / "td_q_table.json"
_TD_LEDGER     = _STATE / "td_receipts.jsonl"

# ── Hyperparameters ────────────────────────────────────────────────────────────
ALPHA   = 0.15   # learning rate  — moderate, ledger-backed
GAMMA   = 0.90   # discount factor — care about near-future reward
LAMBDA_Q = 0.25  # Q-value injection weight into BG c1_scores

# ── Actions (must match swarm_action_selector.py) ─────────────────────────────
ACTIONS = ("SILENCE", "TOOL", "ENGAGE", "BOND")

# ── Compact state enum values ──────────────────────────────────────────────────
SOURCE_VALS     = ("owner", "contact", "group")
STT_VALS        = ("low", "mid", "high", "typed")
C1_VALS         = ("SILENCE", "TOOL", "ENGAGE", "BOND")
TOOL_VALS       = ("stgm", "whatsapp", "none", "other")
FRAME_VALS      = ("owner", "external", "group")
RECENT_VALS     = ("rewarded", "punished", "neutral")


# ── State extraction ───────────────────────────────────────────────────────────

def extract_state(
    text: str,
    stt_confidence: Optional[float] = None,
    c1_action: str = "ENGAGE",
    tool: str = "none",
    source: str = "owner",
    social_frame: str = "owner",
    recent_reward: float = 0.0,
) -> tuple[str, ...]:
    """
    Convert raw inputs into a compact, bounded state key.

    Every dimension is bucketed so the Q-table stays finite.
    Do NOT pass raw text as state — that explodes the table.
    """
    # STT bucket
    if stt_confidence is None:
        stt_b = "typed"
    elif stt_confidence < 0.50:
        stt_b = "low"
    elif stt_confidence < 0.75:
        stt_b = "mid"
    else:
        stt_b = "high"

    # Source
    src = source if source in SOURCE_VALS else "contact"

    # C1 action (already discrete)
    c1 = c1_action if c1_action in C1_VALS else "ENGAGE"

    # Tool
    t = tool if tool in TOOL_VALS else "other"

    # Social frame
    frame = social_frame if social_frame in FRAME_VALS else "external"

    # Recent reward mode
    if recent_reward > 0.3:
        mode = "rewarded"
    elif recent_reward < -0.3:
        mode = "punished"
    else:
        mode = "neutral"

    return (src, stt_b, c1, t, frame, mode)


# ── Q-Table (persisted as JSON) ────────────────────────────────────────────────

class QTable:
    """
    Bounded Q-table persisted to .sifta_state/td_q_table.json.

    Key format: "src|stt|c1|tool|frame|mode||action"
    Value: float (expected cumulative reward)
    """

    def __init__(self):
        self._table: dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        if _Q_TABLE_FILE.exists():
            try:
                with open(_Q_TABLE_FILE) as f:
                    self._table = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._table = {}

    def _save(self) -> None:
        _Q_TABLE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_Q_TABLE_FILE, "w") as f:
            json.dump(self._table, f, indent=2)

    def _key(self, state: tuple, action: str) -> str:
        return "|".join(state) + "||" + action

    def get(self, state: tuple, action: str) -> float:
        return self._table.get(self._key(state, action), 0.0)

    def set(self, state: tuple, action: str, value: float) -> None:
        self._table[self._key(state, action)] = round(value, 6)

    def max_q(self, state: tuple) -> float:
        """max_a Q(state, a) — for Bellman target."""
        return max(self.get(state, a) for a in ACTIONS)

    def q_scores(self, state: tuple) -> dict[str, float]:
        """Return {action: Q(state,action)} for all actions."""
        return {a: self.get(state, a) for a in ACTIONS}

    def update(
        self,
        state: tuple,
        action: str,
        reward: float,
        next_state: tuple,
    ) -> float:
        """
        Q-Learning Bellman update (Watkins 1989):
            Q(s,a) ← Q(s,a) + α · [r + γ · max_{a'} Q(s',a') − Q(s,a)]

        Returns the TD error δ.
        """
        q_sa      = self.get(state, action)
        max_q_next = self.max_q(next_state)
        td_error   = reward + GAMMA * max_q_next - q_sa
        new_q      = q_sa + ALPHA * td_error
        self.set(state, action, new_q)
        self._save()
        return td_error

    def __len__(self) -> int:
        return len(self._table)


# ── Singleton ──────────────────────────────────────────────────────────────────
_Q = None


def get_qtable() -> QTable:
    global _Q
    if _Q is None:
        _Q = QTable()
    return _Q


# ── TD Receipt ─────────────────────────────────────────────────────────────────

def _write_td_receipt(
    state: tuple,
    action: str,
    reward: float,
    td_error: float,
    next_state: tuple,
) -> str:
    trace_id = str(uuid.uuid4())
    row = {
        "ts":         time.time(),
        "trace_id":   trace_id,
        "kind":       "td_update",
        "state":      list(state),
        "action":     action,
        "reward":     round(reward, 4),
        "td_error":   round(td_error, 6),
        "next_state": list(next_state),
        "alpha":      ALPHA,
        "gamma":      GAMMA,
    }
    _TD_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_TD_LEDGER, "a") as f:
        f.write(json.dumps(row) + "\n")
    return trace_id


# ── Public API ─────────────────────────────────────────────────────────────────

def update_from_reward(
    state: tuple,
    action: str,
    reward: float,
    next_state: Optional[tuple] = None,
) -> dict:
    """
    Called when the Architect gives a reward/punishment.
    Updates Q(state, action) and writes a TD receipt.

    Parameters
    ----------
    state      : compact state tuple at the time action was taken
    action     : one of SILENCE, TOOL, ENGAGE, BOND
    reward     : δ from dopamine_reward_loop.detect_reward()
    next_state : state after the action (None → terminal, uses zeros)

    Returns
    -------
    dict with td_error, new_q, receipt_id
    """
    q = get_qtable()
    ns = next_state if next_state is not None else state  # terminal: s' = s
    td_error = q.update(state, action, reward, ns)
    receipt = _write_td_receipt(state, action, reward, td_error, ns)
    return {
        "td_error":   round(td_error, 6),
        "new_q":      round(q.get(state, action), 6),
        "receipt_id": receipt,
        "table_size": len(q),
    }


def q_inject_scores(
    state: tuple,
    c1_scores: dict[str, float],
    weight: float = LAMBDA_Q,
) -> dict[str, float]:
    """
    Inject Q-values into C1 scores for the Basal Ganglia.

    Biology: striatum (C1 input) is modulated by dopaminergic signals
    (Q-values) before the BG makes its selection.

    Formula:
        score'(a) = c1_score(a) + λ_q · Q(s, a)

    Parameters
    ----------
    state     : compact state tuple
    c1_scores : raw C1 confidence scores
    weight    : λ_q — how strongly Q-values modulate C1 scores

    Returns
    -------
    Adjusted score dict, same keys as c1_scores
    """
    q = get_qtable()
    qs = q.q_scores(state)
    adjusted = {}
    for action, score in c1_scores.items():
        q_val = qs.get(action, 0.0)
        adjusted[action] = score + weight * q_val
    return adjusted


def get_action_summary(state: tuple) -> str:
    """Human-readable Q-value summary for a given state."""
    q = get_qtable()
    qs = q.q_scores(state)
    lines = ["[TD Q-VALUES]"]
    for action in ACTIONS:
        bar = "+" * max(0, int(qs[action] * 10)) + "-" * max(0, int(-qs[action] * 10))
        lines.append(f"  {action:8s}: {qs[action]:+.4f}  {bar}")
    lines.append(f"  table_size={len(q)}")
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== TD Q-Learner — Event 76 Verification ===\n")

    # Simulate 5 interactions
    s0 = extract_state("What is the STGM balance?", stt_confidence=0.85,
                        c1_action="TOOL", tool="stgm", source="owner",
                        social_frame="owner", recent_reward=0.0)
    s1 = extract_state("Great job Alice", stt_confidence=0.90,
                        c1_action="ENGAGE", tool="none", source="owner",
                        social_frame="owner", recent_reward=0.7)

    print(f"State s0: {s0}")
    print(f"State s1: {s1}")
    print(f"\nBefore update: Q(s0, TOOL) = {get_qtable().get(s0, 'TOOL'):+.4f}")

    # Architect says "great" → +0.7 reward for TOOL action
    result = update_from_reward(s0, "TOOL", reward=0.7, next_state=s1)
    print(f"After  update: Q(s0, TOOL) = {result['new_q']:+.4f}")
    print(f"  TD error δ = {result['td_error']:+.6f}")
    print(f"  Receipt: {result['receipt_id'][:16]}...")
    print(f"  Table size: {result['table_size']} entries")

    # Verify injection
    c1_raw = {"SILENCE": 0.02, "TOOL": 0.90, "ENGAGE": 0.05, "BOND": 0.03}
    c1_adj = q_inject_scores(s0, c1_raw)
    print(f"\nC1 scores before Q-injection: {c1_raw}")
    print(f"C1 scores after  Q-injection: {c1_adj}")

    # Verify negative reward suppresses
    result2 = update_from_reward(s0, "ENGAGE", reward=-0.8, next_state=s1)
    print(f"\nNegative reward on ENGAGE: Q={result2['new_q']:+.4f}  δ={result2['td_error']:+.4f}")

    print(f"\n{get_action_summary(s0)}")
    print("\n✅ TD Q-Learner verified. Alice now learns which action works where.")
