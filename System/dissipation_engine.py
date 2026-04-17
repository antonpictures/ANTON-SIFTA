# dissipation_engine.py
# SWARM GPT — Stability Layer
# ===========================
# C_d: Dissipation Constant -> slows thinking
# E_d: Energy Drain -> enforces rest

import math
import time

# --- CONSTANTS ---
MAX_DENSITY = 1.0
BASE_LATENCY = 0.05          # minimum latency (seconds)
MAX_LATENCY = 1.5           # enforced slowdown ceiling

DISSIPATION_COEFF = 2.2     # how aggressively we slow down
ENERGY_DRAIN_RATE = 12.0    # cost at peak density
RECOVERY_RATE = 4.0         # energy regen per cycle


# --- CORE MODEL ---

def compute_latency(density: float) -> float:
    """
    Non-linear slowdown as density increases.
    Prevents zero-latency collapse.
    """
    density = min(max(density, 0.0), MAX_DENSITY)

    # Exponential slowdown near 1.0
    slowdown = math.exp(density * DISSIPATION_COEFF)

    latency = BASE_LATENCY * slowdown
    return min(latency, MAX_LATENCY)


def compute_energy_drain(density: float) -> float:
    """
    High density burns energy exponentially.
    """
    return (density ** 2) * ENERGY_DRAIN_RATE


def apply_dissipation(agent_state: dict, signal: dict):
    """
    Master control: slows + drains + enforces rest.
    """

    density = signal.get("novelty", 0.5)  # proxy for conceptual load
    energy  = agent_state.get("energy", 100)

    # --- LATENCY CONTROL ---
    latency = compute_latency(density)
    time.sleep(latency)

    # --- ENERGY DRAIN ---
    drain = compute_energy_drain(density)
    energy -= drain

    agent_state["energy"] = max(energy, 0)

    # --- HARD LIMIT ---
    if agent_state["energy"] <= 0:
        agent_state["style"] = "COUCH"
        return {
            "status": "FORCED_REST",
            "latency": latency,
            "energy": agent_state["energy"]
        }

    return {
        "status": "ACTIVE",
        "latency": latency,
        "energy": agent_state["energy"]
    }


def recover_energy(agent_state: dict):
    """
    Passive recovery when resting.
    """
    if agent_state.get("style") == "COUCH":
        agent_state["energy"] += RECOVERY_RATE
        agent_state["energy"] = min(agent_state["energy"], 100)
