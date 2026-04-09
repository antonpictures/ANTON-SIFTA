import json
import time
from pathlib import Path

REP_DIR = Path(__file__).parent / ".sifta_reputation"
REP_DIR.mkdir(exist_ok=True)

def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    return max(min_val, min(value, max_val))

def _default_state(agent_id: str) -> dict:
    return {
        "agent_id": agent_id,
        "score": 0.50,
        "confidence": 0.10,
        "last_updated": int(time.time()),
        "events": {
            "successful_repairs": 0,
            "failed_repairs": 0,
            "false_signals": 0,
            "collusion_flags": 0,
            "success_streak": 0
        }
    }

def get_reputation(agent_id: str) -> dict:
    """Returns the reputation state of an agent. Creates a ledger entry if one doesn't exist."""
    agent_id = agent_id.upper()
    state_file = REP_DIR / f"{agent_id}.rep.json"
    
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
            
    # Default State for new citizens
    state = _default_state(agent_id)
    save_reputation(agent_id, state)
    return state

def save_reputation(agent_id: str, state: dict):
    agent_id = agent_id.upper()
    REP_DIR.mkdir(exist_ok=True)
    state_file = REP_DIR / f"{agent_id}.rep.json"
    
    state["last_updated"] = int(time.time())
    
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

def update_reputation(agent_id: str, event: str) -> dict:
    """
    Update an agent's reputation based on a behavioral event.
    Events: SUCCESS, FAILURE, FALSE_SIGNAL, COLLUSION
    """
    state = get_reputation(agent_id)
    event = event.upper()
    
    if event == "SUCCESS":
        state["score"] += 0.02
        state["events"]["successful_repairs"] += 1
        state["events"]["success_streak"] = state["events"].get("success_streak", 0) + 1
        
        # REDEMPTION EVENT (Recovery from Exile)
        if state["events"]["success_streak"] >= 3:
            state["score"] += 0.10  # Major recovery boost
            state["events"]["success_streak"] = 0
            print(f"  [✨ REDEMPTION] {agent_id} proved reliability over a streak. Major reputation boost recovered!")
            
    elif event == "FAILURE":
        state["score"] -= 0.03
        state["events"]["failed_repairs"] += 1
        state["events"]["success_streak"] = 0
    elif event == "FALSE_SIGNAL":
        state["score"] -= 0.05
        state["events"]["false_signals"] += 1
        state["events"]["success_streak"] = 0
    elif event == "COLLUSION":
        state["score"] -= 0.10
        state["events"]["collusion_flags"] += 1
        state["events"]["success_streak"] = 0

    # Clamp bounds to [0.0, 1.0]
    state["score"] = round(clamp(state["score"]), 3)
    
    # Confidence strictly increases with observed execution events
    state["confidence"] += 0.01
    state["confidence"] = round(clamp(state["confidence"]), 3)
    
    save_reputation(agent_id, state)
    
    # Visual logging
    if event in ["SUCCESS"]:
        print(f"  [⚖️  REPUTATION] {agent_id} credited for {event}. Score: {state['score']:.2f}")
    else:
        print(f"  [⚠️  REPUTATION] {agent_id} penalized for {event}. Score: {state['score']:.2f}")
        
    return state
