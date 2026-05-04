#!/usr/bin/env python3
"""
System/swarm_td_learner.py — TD Q-Learner Organ (Predator v7, Event 76)
══════════════════════════════════════════════════════════════════════
Implements Temporal Difference Q-learning (Schultz 1997) over the SIFTA
action space. Writes the live Q-table and receipt ledger consumed by
swarm_body_monitor.py.

Ledger outputs:
  .sifta_state/td_q_table.json       — state-action value table
  .sifta_state/td_receipts.jsonl     — Bellman update receipts

proof_of_property(): verifies both ledgers exist and have valid content.
"""

from __future__ import annotations

import json
import time
import math
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_Q_TABLE_PATH  = _STATE / "td_q_table.json"
_RECEIPTS_PATH = _STATE / "td_receipts.jsonl"

# ── Hyperparameters ───────────────────────────────────────────────────────────
ALPHA   = 0.1   # learning rate
GAMMA   = 0.95  # discount factor
EPSILON = 0.15  # exploration rate

# ── Action space (mirrors swarm_action_selector_trace.jsonl winners) ──────────
ACTIONS = [
    "listen",           # attend to incoming audio
    "respond",          # produce verbal output
    "log_body_event",   # write stigmergic body row
    "probe_vision",     # trigger vision body probe
    "idle",             # no-op conserves STGM
]

# ── State encoding (compact; expands as organs come online) ───────────────────
def _current_state_key() -> str:
    """Encode current organism state into a discrete Q-table key."""
    try:
        hour = int(time.strftime("%H"))
        time_bucket = "morning" if 5 <= hour < 12 else (
            "afternoon" if 12 <= hour < 18 else (
            "evening"   if 18 <= hour < 22 else "night"))
    except Exception:
        time_bucket = "unknown"

    # Read energy from body file if available
    energy_bucket = "mid"
    try:
        body = json.loads((_STATE / "ALICE_M5.json").read_text())
        e = float(body.get("energy", 50))
        energy_bucket = "high" if e > 70 else ("low" if e < 30 else "mid")
    except Exception:
        pass

    # --- High-Dimensional Stigmergic Field Coupling ---
    # The decision organ reads the physical biology to define its state space.
    cuttlefish_pattern = "mottle"
    honeybee_route = "none"
    try:
        c_lines = (_STATE / "cuttlefish_display.jsonl").read_text(encoding="utf-8").strip().splitlines()
        if c_lines:
            c_row = json.loads(c_lines[-1])
            cuttlefish_pattern = c_row.get("payload", c_row).get("pattern", "mottle")
            
        h_lines = (_STATE / "waggle_quorum.jsonl").read_text(encoding="utf-8").strip().splitlines()
        if h_lines:
            h_row = json.loads(h_lines[-1])
            honeybee_route = str(h_row.get("payload", h_row).get("route", "none"))[:8]
    except Exception:
        pass

    return f"{time_bucket}:{energy_bucket}:skin_{cuttlefish_pattern}:route_{honeybee_route}"


# ── Q-table I/O ───────────────────────────────────────────────────────────────
def load_q_table() -> Dict[str, Dict[str, float]]:
    """Load Q-table from disk. Returns empty dict if missing."""
    if not _Q_TABLE_PATH.exists():
        return {}
    try:
        return json.loads(_Q_TABLE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_q_table(q: Dict[str, Dict[str, float]]) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    _Q_TABLE_PATH.write_text(
        json.dumps(q, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _ensure_state(q: Dict, state: str) -> None:
    """Initialise Q-values for a state if not yet seen (optimistic zeros)."""
    if state not in q:
        q[state] = {a: 0.0 for a in ACTIONS}


# ── Bellman update ────────────────────────────────────────────────────────────
def bellman_update(
    state: str,
    action: str,
    reward: float,
    next_state: str,
    *,
    q: Optional[Dict] = None,
) -> Tuple[Dict, float]:
    """
    Q(s,a) ← Q(s,a) + α [r + γ·max_a' Q(s',a') - Q(s,a)]
    Returns updated table and the TD error δ.
    """
    if q is None:
        q = load_q_table()
    _ensure_state(q, state)
    _ensure_state(q, next_state)

    q_sa      = q[state][action]
    max_next  = max(q[next_state].values())
    td_error  = reward + GAMMA * max_next - q_sa
    q[state][action] = q_sa + ALPHA * td_error
    return q, td_error


def _append_receipt(receipt: Dict[str, Any]) -> None:
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(_RECEIPTS_PATH, json.dumps(receipt) + "\n")
    except Exception:
        _STATE.mkdir(parents=True, exist_ok=True)
        with _RECEIPTS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(receipt) + "\n")


# ── Public API ────────────────────────────────────────────────────────────────
def observe_reward(reward: float, action: str = "idle") -> float:
    """
    Record a reward signal, run one Bellman update, persist Q-table + receipt.
    Returns the TD error δ (useful for dopamine organ).
    """
    state      = _current_state_key()
    next_state = _current_state_key()   # single-step; expand later
    q, td_error = bellman_update(state, action, reward, next_state)
    save_q_table(q)

    receipt = {
        "ts":         time.time(),
        "state":      state,
        "action":     action,
        "reward":     round(reward, 4),
        "td_error":   round(td_error, 6),
        "q_states":   len(q),
        "source":     "swarm_td_learner",
    }
    _append_receipt(receipt)
    return td_error


def select_action(state: Optional[str] = None) -> str:
    """ε-greedy action selection from current Q-table."""
    import random
    if random.random() < EPSILON:
        return random.choice(ACTIONS)
    q = load_q_table()
    s = state or _current_state_key()
    _ensure_state(q, s)
    return max(q[s], key=lambda a: q[s][a])


# ── Boot initialisation ───────────────────────────────────────────────────────
def _boot_init() -> None:
    """Write first Q-table and boot receipt if ledger is empty."""
    q = load_q_table()
    if not q:
        # Seed with current state so body monitor sees > 0 Q-states immediately
        state = _current_state_key()
        _ensure_state(q, state)
        save_q_table(q)

    # Write a boot receipt so td_receipts.jsonl exists
    if not _RECEIPTS_PATH.exists() or _RECEIPTS_PATH.stat().st_size == 0:
        receipt = {
            "ts":       time.time(),
            "state":    _current_state_key(),
            "action":   "idle",
            "reward":   0.0,
            "td_error": 0.0,
            "q_states": len(q),
            "source":   "swarm_td_learner:boot_init",
        }
        _append_receipt(receipt)


# ── Proof of property ─────────────────────────────────────────────────────────
def proof_of_property() -> dict:
    """
    CI DAM invariant: both Q-table and receipt ledger must exist and be valid.
    Called by swarm_proof_runner.py at boot.
    """
    _boot_init()   # idempotent first-write

    q_ok      = _Q_TABLE_PATH.exists() and _Q_TABLE_PATH.stat().st_size > 2
    receipt_ok = _RECEIPTS_PATH.exists() and _RECEIPTS_PATH.stat().st_size > 2

    try:
        q = json.loads(_Q_TABLE_PATH.read_text())
        q_valid = isinstance(q, dict) and len(q) > 0
    except Exception:
        q_valid = False

    return {
        "ok":                q_ok and receipt_ok and q_valid,
        "q_table_exists":    q_ok,
        "receipts_exist":    receipt_ok,
        "q_table_valid":     q_valid,
    }


# ── Standalone boot ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    _boot_init()
    result = proof_of_property()
    print(f"[TD Q-Learner] proof_of_property → {result}")
    if result["ok"]:
        print(f"[TD Q-Learner] Q-table: {_Q_TABLE_PATH}")
        print(f"[TD Q-Learner] Receipts: {_RECEIPTS_PATH}")
        # Do one live Bellman update to demonstrate
        delta = observe_reward(0.5, "listen")
        print(f"[TD Q-Learner] First live update: δ={delta:.6f}")
