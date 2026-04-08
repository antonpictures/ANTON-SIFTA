#!/usr/bin/env python3
"""
market_router.py — SIFTA Universal Basic Inference (UBI) Router
─────────────────────────────────────────────────────────────
This acts as a decentralized load balancer. It evaluates external incoming
compute requests and automatically assigns them to nodes based on biological 
fiat survival quotas instead of raw latency optimization.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
import random

ROOT_DIR = Path(__file__).parent
STATE_DIR = ROOT_DIR / ".sifta_state"

# ─── BIOLOGICAL SURVIVAL CONSTANTS ──────────────────────────────────────────
# Assume placeholder values for "Shelter + 3 Meals" in STGM terms
MONTHLY_SURVIVAL_QUOTA_STGM = 500.0

def get_node_biological_state(node_id: str) -> dict:
    """Reads the current Stigmergic balance of the human operator's node."""
    state_path = STATE_DIR / f"{node_id.upper()}.json"
    if not state_path.exists():
        return {"id": node_id, "stgm_balance": 0.0, "hunger_level": "CRITICAL"}
    
    try:
        with open(state_path, "r") as f:
            state = json.load(f)
            balance = float(state.get("stgm_balance", 0.0))
            is_surviving = balance >= MONTHLY_SURVIVAL_QUOTA_STGM
            hunger = "SATISFIED" if is_surviving else "STARVING"
            return {
                "id": node_id,
                "stgm_balance": balance,
                "hunger_level": hunger
            }
    except Exception:
        return {"id": node_id, "stgm_balance": 0.0, "hunger_level": "CRITICAL"}

def route_inference_job(job_metadata: dict, available_nodes: list[str]) -> str:
    """
    Universal Basic Inference Core Algorithm.
    Routes jobs to the "hungriest" node first to ensure human operator survival.
    If multiple are starving, picks the one with the lowest balance.
    If all are surviving, routes based on pure latency/hardware limits (capitalist mode).
    """
    print(f"\n[ROUTER] Incoming Job | Target Pay: {job_metadata.get('stgm_reward')} STGM | Type: {job_metadata.get('job_type')}")
    
    starving_nodes = []
    satisfied_nodes = []

    for node in available_nodes:
        bio_state = get_node_biological_state(node)
        print(f"   [NODE METRIC] {node} | Balance: {bio_state['stgm_balance']:0.2f} STGM | Status: {bio_state['hunger_level']}")
        
        if bio_state['hunger_level'] in ["STARVING", "CRITICAL"]:
            starving_nodes.append(bio_state)
        else:
            satisfied_nodes.append(bio_state)
            
    # ── UBI Directive: Feed the Starving Operators First ──
    if starving_nodes:
        # Sort by poorest first
        starving_nodes.sort(key=lambda x: x['stgm_balance'])
        poorest = starving_nodes[0]
        print(f"   [UBI DIRECTIVE] Routing payload to poorest node: {poorest['id']}")
        return poorest['id']
        
    # ── Capitalist Directive: All quotas met ──
    print(f"   [CAPITALIST DIRECTIVE] All node human survival quotas met. Routing for raw efficiency.")
    # Fallback to random assignment or latency optimization
    # For now, pick a node at random
    elected = random.choice(satisfied_nodes)
    return elected['id']

if __name__ == "__main__":
    print("==================================================")
    print(" SIFTA UNIVERSAL BASIC INFERENCE (UBI) ENGINE LIVE")
    print("==================================================")
    
    # ── Test Execution ──
    MOCK_NODES = ["M1THER", "ALICE_M5"]
    
    job_1 = {"job_type": "SYNTAX_HEALING", "stgm_reward": 5.0}
    elected_node = route_inference_job(job_1, MOCK_NODES)
    print(f"\n[EXECUTION] Payload dispatched >> {elected_node}")
