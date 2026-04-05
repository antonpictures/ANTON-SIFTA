import hashlib
import json
import time
import re
from pathlib import Path

CEMETERY_DIR = Path(__file__).parent / "CEMETERY"
CEMETERY_DIR.mkdir(exist_ok=True)

STATE_DIR = Path(__file__).parent / ".sifta_state"
STATE_DIR.mkdir(exist_ok=True)

def load_agent_state(agent_id: str) -> dict:
    STATE_DIR.mkdir(exist_ok=True)
    state_file = STATE_DIR / f"{agent_id}.json"
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_agent_state(state: dict):
    agent_id = state.get("id")
    if not agent_id:
        return
    STATE_DIR.mkdir(exist_ok=True)
    state_file = STATE_DIR / f"{agent_id}.json"
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

class SwarmBody:
    FACES = {"M1THER": "[O_O]", "ANTIALICE": "[o|o]", "SEBASTIAN": "[_o_]", "HERMES": "[_v_]", "IMPERIAL": "[@_@]"}
    
    def __init__(self, agent_id):
        self.agent_id = agent_id.upper()
        self.face = self.FACES.get(self.agent_id, "[O_O]")
        
        # Rehydrate persistent state if it exists
        saved_state = load_agent_state(self.agent_id)
        if saved_state:
            self.sequence = saved_state.get("seq", 0)
            self.hash_chain = saved_state.get("hash_chain", [])
            self.energy = saved_state.get("energy", 100)
            self.style = saved_state.get("style", "NOMINAL")
        else:
            self.sequence = 0
            self.hash_chain = []
            self.energy = 100
            self.style = "NOMINAL"
        
    def generate_body(self, origin, destination, payload, style=None, energy=None):
        if style is not None:
            self.style = style
        if energy is not None:
            self.energy = energy
            
        self.sequence += 1
        timestamp = int(time.time())
        ttl = timestamp + 604800 # 7-day Wild-Type Genome
        
        # Cryptographic Mass (Hash Chaining using SHA-256)
        raw_data = f"{self.agent_id}{payload}{self.sequence}{timestamp}"
        if self.hash_chain:
            raw_data += self.hash_chain[-1] 
        new_hash = hashlib.sha256(raw_data.encode()).hexdigest()
        self.hash_chain.append(new_hash)
        
        body_string = (f"<///{self.face}///::ID[{self.agent_id}]::FROM[{origin}]::TO[{destination}]"
                f"::SEQ[{self.sequence:03d}]::H[{new_hash}]::T[{timestamp}]::TTL[{ttl}]"
                f"::STYLE[{self.style}]::ENERGY[{self.energy}]>")
                
        # Persist the current snapshot
        save_agent_state({
            "id": self.agent_id,
            "seq": self.sequence,
            "hash_chain": self.hash_chain,
            "energy": self.energy,
            "style": self.style,
            "raw": body_string,
            "ttl": ttl
        })
        
        return body_string

def parse_body_state(ascii_body):
    """The agent reads its own scars."""
    id_match = re.search(r"::ID\[([\w\-]+)\]", ascii_body)
    style_match = re.search(r"::STYLE\[(\w+)\]", ascii_body)
    energy_match = re.search(r"::ENERGY\[(\d+)\]", ascii_body)
    ttl_match = re.search(r"::TTL\[(\d+)\]", ascii_body)
    
    # Hash chain extraction for cemetery logic
    hash_match = re.search(r"::H\[([\w\|]+)\]", ascii_body)
    hash_chain = hash_match.group(1).split("|") if hash_match else []
    
    seq_match = re.search(r"::SEQ\[(\d+)\]", ascii_body)
    seq = int(seq_match.group(1)) if seq_match else 0
    
    return {
        "id": id_match.group(1) if id_match else "UNKNOWN",
        "seq": seq,
        "style": style_match.group(1) if style_match else "NOMINAL",
        "energy": int(energy_match.group(1)) if energy_match else 100,
        "ttl": int(ttl_match.group(1)) if ttl_match else 0,
        "hash_chain": hash_chain,
        "raw": ascii_body
    }

DAMAGE_TABLE = {
    "network_timeout":   15,
    "validation_fail":   10,
    "llm_empty":         8,
    "swim_fail":         20,
    "syntax_error":      5,
}

def apply_damage(state: dict, strike_type: str) -> dict:
    """Apply a damage strike. May mutate STYLE if energy drops low."""
    cost = DAMAGE_TABLE.get(strike_type, 10)
    state["energy"] = max(0, state["energy"] - cost)

    if state["energy"] <= 0:
        state["style"] = "DEAD"
    elif state["energy"] < 20:
        state["style"] = "CRITICAL"
    elif state["energy"] < 40:
        state["style"] = "CORRUPTED"

    save_agent_state(state)
    return state

def bury(state: dict, cause: str = "unknown"):
    """Write a permanent death record to the CEMETERY directory."""
    agent_id = state.get("id", "UNKNOWN")
    seq      = state.get("seq", 0)
    ts       = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    epitaph = (
        f"# CEMETERY — {agent_id} SEQ[{seq:03d}]\n"
        f"DIED:           {ts}\n"
        f"CAUSE:          {cause}\n"
        f"FINAL_ENERGY:   {state.get('energy')}\n"
        f"FINAL_STYLE:    {state.get('style')}\n"
        f"HASH_CHAIN:     {'|'.join(state.get('hash_chain', []))}\n"
        f"SWIMS:          {seq}\n"
        f"FINAL_BODY:     {state.get('raw')}\n"
    )

    dead_path = CEMETERY_DIR / f"{agent_id}-SEQ{seq:03d}.dead"
    dead_path.write_text(epitaph, encoding="utf-8")
    print(f"  [☠️ CEMETERY] {agent_id} buried at {dead_path.name}")
    return dead_path
