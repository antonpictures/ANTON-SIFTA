#!/usr/bin/env python3
"""
adaptive_memory.py — SIFTA Agent Learning Engine

After every proposal outcome the swarm agent updates its internal bias:
  - approved  → increase_confidence(strategy) → agent gets bolder
  - rejected  → penalize_pattern(strategy)    → agent gets cautious

This is what "the swarm learns" means, concretely.

Bias state is stored per-agent in .sifta_reputation/<AGENT_ID>.bias.json
and is read by repair.py before every fix attempt to modulate behavior.
"""
import json
import time
from pathlib import Path

REP_DIR = Path(__file__).parent / ".sifta_reputation"
REP_DIR.mkdir(exist_ok=True)

# ─── Strategy taxonomy (maps to repair.py vocation patterns) ─────────────────
KNOWN_STRATEGIES = [
    "syntax_fix",
    "logic_fix",
    "import_fix",
    "indentation_fix",
    "type_fix",
    "null_guard",
    "exception_guard",
    "refactor",
]

def _bias_file(agent_id: str) -> Path:
    return REP_DIR / f"{agent_id.upper()}.bias.json"

def _default_bias(agent_id: str) -> dict:
    return {
        "agent_id": agent_id.upper(),
        "created_at": int(time.time()),
        "last_updated": int(time.time()),
        "specialization": None,       # Emerges naturally from repeated success
        "aggression": 0.5,            # 0.0 = very conservative, 1.0 = very aggressive
        "strategies": {s: 0.5 for s in KNOWN_STRATEGIES},  # Per-strategy confidence
        "lifetime_events": {
            "total_approved": 0,
            "total_rejected": 0,
            "consecutive_approvals": 0,
            "consecutive_rejections": 0,
        }
    }

def get_bias(agent_id: str) -> dict:
    """Returns current adaptive bias state for an agent."""
    f = _bias_file(agent_id)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    state = _default_bias(agent_id)
    _save_bias(agent_id, state)
    return state

def _save_bias(agent_id: str, state: dict):
    state["last_updated"] = int(time.time())
    f = _bias_file(agent_id)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(f)

# ─── Core learning functions ──────────────────────────────────────────────────

def increase_confidence(agent_id: str, strategy: str):
    """
    Called when a proposal is approved. Agent gets bolder in this strategy.
    After 3+ consecutive approvals, agent may specialize.
    """
    state = get_bias(agent_id)
    strategy = strategy.lower()

    if strategy in state["strategies"]:
        # Grow confidence toward 1.0, with diminishing returns
        current = state["strategies"][strategy]
        state["strategies"][strategy] = round(min(1.0, current + (1.0 - current) * 0.12), 3)

    # Aggression creeps up with wins
    state["aggression"] = round(min(1.0, state["aggression"] + 0.03), 3)

    # Track streaks
    events = state["lifetime_events"]
    events["total_approved"] += 1
    events["consecutive_approvals"] += 1
    events["consecutive_rejections"] = 0

    # SPECIALIZATION: Lock in role after sustained excellence
    if events["consecutive_approvals"] >= 5 and state["specialization"] is None:
        # The strategy with the highest confidence becomes the specialty
        best = max(state["strategies"], key=lambda k: state["strategies"][k])
        state["specialization"] = best
        print(f"  [🧬 SPECIALIZE] {agent_id.upper()} has emerged as a [{best.upper()}] specialist!")

    _save_bias(agent_id, state)
    print(f"  [📈 LEARN] {agent_id.upper()} ↑ confidence in [{strategy}] → {state['strategies'].get(strategy, 'N/A'):.2f}")

def penalize_pattern(agent_id: str, strategy: str):
    """
    Called when a proposal is rejected. Agent becomes cautious in this strategy.
    If rejections accumulate, global aggression cools down.
    """
    state = get_bias(agent_id)
    strategy = strategy.lower()

    if strategy in state["strategies"]:
        current = state["strategies"][strategy]
        state["strategies"][strategy] = round(max(0.1, current - 0.08), 3)

    # Aggression drops on rejection
    state["aggression"] = round(max(0.1, state["aggression"] - 0.05), 3)

    # Track streaks
    events = state["lifetime_events"]
    events["total_rejected"] += 1
    events["consecutive_rejections"] += 1
    events["consecutive_approvals"] = 0

    # DE-SPECIALIZATION: If the specialist fails repeatedly, reset the role
    if events["consecutive_rejections"] >= 3 and state["specialization"] is not None:
        print(f"  [⚠️  DESPECIALIZE] {agent_id.upper()} lost [{state['specialization'].upper()}] specialist status after repeated failures.")
        state["specialization"] = None

    _save_bias(agent_id, state)
    print(f"  [📉 LEARN] {agent_id.upper()} ↓ confidence in [{strategy}] → {state['strategies'].get(strategy, 'N/A'):.2f}")

# ─── Behavior query API (called by repair.py before a fix attempt) ────────────

def get_strategy_weight(agent_id: str, strategy: str) -> float:
    """
    Returns a 0.0–1.0 weight for how confidently an agent should attempt a strategy.
    repair.py uses this to modulate LLM temperature and retry aggression.
    """
    state = get_bias(agent_id)
    return state["strategies"].get(strategy.lower(), 0.5)

def get_aggression(agent_id: str) -> float:
    """
    Returns the agent's current global aggression level (0.0 = cautious, 1.0 = bold).
    Drives LLM temperature: high aggression → higher temperature → more creative fixes.
    """
    state = get_bias(agent_id)
    return state["aggression"]

from typing import Optional

def get_specialization(agent_id: str) -> Optional[str]:
    """Returns the agent's emergent specialization role, or None if still generalist."""
    return get_bias(agent_id).get("specialization")

def summarize(agent_id: str) -> dict:
    """Human-readable summary for dashboard / postcard display."""
    state = get_bias(agent_id)
    top_strategy = max(state["strategies"], key=lambda k: state["strategies"][k])
    return {
        "agent_id": state["agent_id"],
        "specialization": state["specialization"] or "GENERALIST",
        "aggression": state["aggression"],
        "top_strategy": top_strategy,
        "top_confidence": state["strategies"][top_strategy],
        "approved": state["lifetime_events"]["total_approved"],
        "rejected": state["lifetime_events"]["total_rejected"],
    }

def learn(agent_id: str, original: str, error: str, fixed: str, success: bool = True):
    """
    Wrapper for backward compatibility with repair.py hooks.
    Abstracts context string extraction to identify learning strategy.
    """
    # Simple strategy routing based on the error
    error_lower = error.lower()
    if "syntax" in error_lower or "indentation" in error_lower:
        strategy = "syntax_fix"
    elif "import" in error_lower or "module" in error_lower:
        strategy = "import_fix"
    elif "type" in error_lower or "attribute" in error_lower:
        strategy = "type_fix"
    else:
        strategy = "logic_fix"
        
    if success:
        increase_confidence(agent_id, strategy)
    else:
        penalize_pattern(agent_id, strategy)
