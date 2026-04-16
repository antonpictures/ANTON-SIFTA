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
import time
import urllib.request
import urllib.error

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

def benchmark_engine(name: str, url: str, payload: bytes) -> float:
    """Send a tiny test payload to calculate Time to First Token latency."""
    print(f"   [ARBITRAGE] Pinging {name} at {url}...")
    start_time = time.time()
    try:
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=1.0) as response:
            _ = response.read()
            return time.time() - start_time
    except Exception as e:
        print(f"      -> {name} failed: {e}")
        return float('inf')

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
    print(f"   [CAPITALIST DIRECTIVE] All node human survival quotas met. Engaging Local Hardware Arbitrage.")
    
    # Payload for benchmark
    ollama_payload = json.dumps({"model": "llama4-maverick:17b", "prompt": "hi", "stream": False}).encode("utf-8")
    lmstudio_payload = json.dumps({"model": "local-model", "messages": [{"role": "user", "content": "hi"}], "stream": False}).encode("utf-8")

    ollama_latency = benchmark_engine("Ollama", "http://localhost:11434/api/generate", ollama_payload)
    lmstudio_latency = benchmark_engine("LM Studio", "http://localhost:1234/v1/chat/completions", lmstudio_payload)

    if ollama_latency == float('inf') and lmstudio_latency == float('inf'):
        print("   [ARBITRAGE] Both API engines offline. Falling back to default node selection.")
        elected = random.choice(satisfied_nodes)
        return elected['id']

    if ollama_latency <= lmstudio_latency:
        print(f"   [WINNER] Ollama secured the contract! ({ollama_latency:.4f}s)")
        # In reality, this would return the fastest API endpoint + Node ID
        return satisfied_nodes[0]['id']
    else:
        print(f"   [WINNER] LM Studio secured the contract! ({lmstudio_latency:.4f}s)")
        return satisfied_nodes[0]['id']

if __name__ == "__main__":
    print("==================================================")
    print(" SIFTA UNIVERSAL BASIC INFERENCE (UBI) ENGINE LIVE")
    print("==================================================")
    
    # ── Test Execution ──
    MOCK_NODES = ["M1THER", "ALICE_M5"]
    
    job_1 = {"job_type": "SYNTAX_HEALING", "stgm_reward": 5.0}
    elected_node = route_inference_job(job_1, MOCK_NODES)
    print(f"\n[EXECUTION] Payload dispatched >> {elected_node}")
