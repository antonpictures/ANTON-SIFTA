#!/usr/bin/env python3
"""
identity_intrinsic_reward.py — Wiring CRDT Identity Stability into SwarmRL
==========================================================================

Origin
------
Proposed by CG53 (SwarmGPT): "wire this directly into your SwarmRL reward
loop so identity stability itself becomes an optimization target."
Developed by AG31 (Gemini 3.1 Pro High) to help C47H.

How it works
------------
Instead of just logging when identity drifts (e.g., a Chimera State or 
Pheromone Mirroring), this module outputs an intrinsic RL reward:
  + Positive reward for maintaining high identity stability (single peak).
  - Negative penalty for identity drift/entropy spikes (spoofing).

When SwarmRL agents explore or write code, their actions implicitly affect
the swarm's identity field. By folding this signal into the Proximal Policy 
Loss (PPO) alongside territory intrinsic reward, the swarm organically learns 
to avoid identity collapse.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict
from System.identity_field_crdt import IdentityField

# Reward multipliers
STABILITY_REWARD_WEIGHT = 2.0
DRIFT_PENALTY_WEIGHT = -5.0

def compute_identity_intrinsic_reward() -> Dict[str, float]:
    """
    Reads the live CRDT Identity Field and returns intrinsic rewards
    for SwarmRL's agent loop.
    """
    field = IdentityField.load()
    
    # Stability ranges from 0.0 (uniform noise) to 1.0 (pure single identity)
    stability_score = field.stability()
    
    # Is it drastically drifting from its historical centroid?
    is_drifting = field.is_drifting()
    
    reward = 0.0
    reasons = []
    
    # 1. Base stability reward
    if stability_score > 0.6:
        # High stability yields positive reinforcement
        r = stability_score * STABILITY_REWARD_WEIGHT
        reward += r
        reasons.append(f"STABLE(+{r:.3f})")
    elif stability_score < 0.3:
        # Low stability (fractured identity) yields penalty
        penalty = (0.3 - stability_score) * DRIFT_PENALTY_WEIGHT
        reward += penalty
        reasons.append(f"FRACTURED({penalty:.3f})")
        
    # 2. Drift penalty (active hallucination/mirroring)
    if is_drifting:
        reward += DRIFT_PENALTY_WEIGHT
        reasons.append(f"DRIFT_PUNISH({DRIFT_PENALTY_WEIGHT:.3f})")

    return {
        "reward_raw": round(reward, 4),
        "stability": round(stability_score, 4),
        "entropy": round(field.entropy(), 4),
        "drifting": is_drifting,
        "breakdown": " | ".join(reasons) if reasons else "NEUTRAL"
    }

if __name__ == "__main__":
    result = compute_identity_intrinsic_reward()
    print("=== Identity Intrinsic Reward (SwarmRL Bridge) ===")
    print(f"Total Reward: {result['reward_raw']}")
    print(f"Stability:    {result['stability']}")
    print(f"Entropy:      {result['entropy']}")
    print(f"Drifting:     {result['drifting']}")
    print(f"Breakdown:    {result['breakdown']}")
