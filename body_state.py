import hashlib
import time
import re

class SwarmBody:
    FACES = {"M1THER": "[O_O]", "ANTIALICE": "[o|o]", "SEBASTIAN": "[_o_]", "HERMES": "[_v_]"}
    
    def __init__(self, agent_id):
        self.agent_id = agent_id.upper()
        self.face = self.FACES.get(self.agent_id, "[O_O]")
        self.sequence = 0
        self.hash_chain = []
        
    def generate_body(self, origin, destination, payload, style="NOMINAL", energy=100):
        self.sequence += 1
        timestamp = int(time.time())
        ttl = timestamp + 604800 # 7-day Wild-Type Genome
        
        # Cryptographic Mass (Hash Chaining)
        raw_data = f"{self.agent_id}{payload}{self.sequence}{timestamp}"
        if self.hash_chain:
            raw_data += self.hash_chain[-1] 
        new_hash = hashlib.md5(raw_data.encode()).hexdigest()
        self.hash_chain.append(new_hash)
        
        return (f"<///{self.face}///::ID[{self.agent_id}]::FROM[{origin}]::TO[{destination}]"
                f"::SEQ[{self.sequence:03d}]::H[{new_hash}]::T[{timestamp}]::TTL[{ttl}]"
                f"::STYLE[{style}]::ENERGY[{energy}]>")

def parse_body_state(ascii_body):
    """The agent reads its own scars."""
    style_match = re.search(r"::STYLE\[(\w+)\]", ascii_body)
    energy_match = re.search(r"::ENERGY\[(\d+)\]", ascii_body)
    ttl_match = re.search(r"::TTL\[(\d+)\]", ascii_body)
    
    return {
        "style": style_match.group(1) if style_match else "NOMINAL",
        "energy": int(energy_match.group(1)) if energy_match else 100,
        "ttl": int(ttl_match.group(1)) if ttl_match else 0
    }
