import os
from pathlib import Path
from body_state import SwarmBody, load_agent_state
from repair import swim_and_repair

def main():
    agent_id = "KARPATHY_PRIME_0X1"
    seal = f"ARCHITECT_SEAL_{agent_id}"
    
    # 1. Baptize the agent
    print("--- [1] BAPTIZING NEW AGENT ---")
    body = SwarmBody(agent_id, seal)
    
    # 2. Upgrade Vocation to CODER
    print("\n--- [2] REQUESTING VOCATION CHANGE ---")
    body.request_vocation_change("CODER", seal)
    
    # Reload state to pass to repair.py
    state = load_agent_state(agent_id)
    
    # 3. Test on a bad script
    print("\n--- [3] DEPLOYING CODER AGENT TO FIX SCRIPT ---")
    swim_and_repair(
        target_dir="test_environment/bad_code.py",
        state=state,
        dry_run=False,
        provider="ollama",
        model="qwen3.5:0.8b"
    )
    
if __name__ == "__main__":
    main()
