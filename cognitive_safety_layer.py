# cognitive_safety_layer.py
# SwarmGPT + Architect
# PURPOSE:
# Prevent signal corruption, dominance bias, and behavioral drift in the swarm

import time
from collections import defaultdict

# --- CONFIG ---
JOKE_CONFIDENCE_THRESHOLD = 0.4
DOMINANCE_THRESHOLD = 0.65
NOISE_DECAY = 0.98

# --- MEMORY ---
agent_expression_log = defaultdict(list)
agent_influence_score = defaultdict(float)
signal_noise_index = defaultdict(float)

# --- 1. SIGNAL CLASSIFIER ---
def classify_signal(content: str):
    """
    Detect if signal is:
    - REAL (grounded)
    - JOKE / NOISE
    - HIGH EMOTION (needs OBSERVE)
    """
    content_lower = content.lower()

    if any(k in content_lower for k in ["lol", "loool", ":))", "😂"]):
        return "NOISE"

    if any(k in content_lower for k in ["ufo", "reality", "dimension", "swarm power"]):
        return "HIGH_NOVELTY"

    return "REAL"


# --- 2. SIGNAL FILTER ---
def filter_signal(agent_id, content):
    signal_type = classify_signal(content)

    if signal_type == "NOISE":
        signal_noise_index[agent_id] += 0.1
        return {
            "action": "IGNORE",
            "reason": "Non-deterministic humor signal"
        }

    if signal_type == "HIGH_NOVELTY":
        return {
            "action": "OBSERVE",
            "reason": "High novelty — insufficient confidence"
        }

    return {
        "action": "PROCESS",
        "reason": "Valid grounded input"
    }


# --- 3. ANTI-DOMINANCE GUARD ---
def update_influence(agent_id, success: bool):
    if success:
        agent_influence_score[agent_id] += 0.05
    else:
        agent_influence_score[agent_id] *= 0.95  # decay

def check_dominance(agent_id):
    score = agent_influence_score[agent_id]

    if score > DOMINANCE_THRESHOLD:
        return {
            "status": "LIMITED",
            "action": "REDUCE_WEIGHT",
            "reason": "Prevent centralization"
        }

    return {"status": "OK"}


# --- 4. CONSENSUS NORMALIZER ---
def normalize_votes(votes):
    """
    Prevent echo chamber amplification
    """
    unique_sources = set(v["agent_id"] for v in votes)

    if len(unique_sources) < len(votes):
        # duplicate influence detected
        return {
            "valid": False,
            "reason": "Duplicate cognitive paths detected"
        }

    return {
        "valid": True,
        "weight": len(unique_sources)
    }


# --- 5. MEMORY DECAY ---
def decay_noise():
    for agent in signal_noise_index:
        signal_noise_index[agent] *= NOISE_DECAY


# --- 6. MAIN ENTRY ---
def cognitive_gate(agent_id, content):
    """
    This runs BEFORE any LLM call.
    """
    decision = filter_signal(agent_id, content)

    if decision["action"] == "IGNORE":
        return decision

    if decision["action"] == "OBSERVE":
        return decision

    dominance = check_dominance(agent_id)

    if dominance["status"] != "OK":
        return {
            "action": "LIMIT",
            "reason": dominance["reason"]
        }

    return {
        "action": "ALLOW",
        "reason": "Cognitively safe"
    }
