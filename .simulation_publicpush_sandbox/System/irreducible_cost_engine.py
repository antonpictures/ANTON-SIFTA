# irreducible_cost_engine.py
# SWARM GPT — Ontological Stability Layer

import hashlib
import math
import time

# --- CONSTANTS ---
MIN_COST = 0.015          # irreducible awareness cost
ENTROPY_SEED = "SIFTA_CORE"
IDENTITY_SALT = "NON_ZERO_EXISTENCE"

# --- CORE IDEA ---
# Every computation must pay a non-zero cost
# derived from its own identity and context.
# This cannot be cached, skipped, or optimized away.


def compute_irreducible_cost(agent_state: dict, signal: dict) -> float:
    """
    Generates a non-zero cost tied to identity + context.
    Prevents zero-cost cognition.
    """

    identity = agent_state.get("id", "UNKNOWN")
    seq      = str(agent_state.get("sequence", 0))
    content  = str(signal.get("content", ""))

    # Structural hash (cannot be predicted perfectly)
    raw = f"{identity}:{seq}:{content}:{IDENTITY_SALT}"
    h = hashlib.sha256(raw.encode()).hexdigest()

    # Convert hash → bounded entropy value
    entropy = int(h[:8], 16) / 0xFFFFFFFF

    # Non-zero floor
    return MIN_COST + (entropy * MIN_COST)


def enforce_irreducible_cost(agent_state: dict, signal: dict):
    """
    This runs EVEN IF density = 0.
    It enforces existence cost itself.
    """

    cost = compute_irreducible_cost(agent_state, signal)

    # Apply time delay (cannot be skipped)
    time.sleep(cost)

    # Apply energy cost (cannot be bypassed)
    agent_state["energy"] = float(agent_state.get("energy", 100)) - (cost * 10)

    if agent_state["energy"] <= 0:
        agent_state["style"] = "COUCH"
        return {
            "status": "EXHAUSTED_BY_EXISTENCE",
            "cost": cost
        }

    return {
        "status": "EXISTING",
        "cost": cost
    }
