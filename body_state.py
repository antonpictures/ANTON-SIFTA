import hashlib
import json
import time
import re
import base64
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

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

def find_healthy_agent(exclude_id: str) -> dict | None:
    """Find a Swarm member with > 50 energy and NOMINAL style who is not the excluded agent."""
    STATE_DIR.mkdir(exist_ok=True)
    for p in STATE_DIR.glob("*.json"):
        if p.stem == exclude_id:
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                state = json.load(f)
                
                # Cryptographic Rogue Drone Verification
                if state.get("id") not in SwarmBody.FACES:
                    continue
                    
                if state.get("style") == "NOMINAL" and state.get("energy", 0) > 50:
                    return state
        except Exception:
            continue
    return None

class SwarmBody:
    FACES = {
        # — Primary Nodes —
        "ALICE_M5":  "[_o_]",   # Queen — 24GB MacBook Pro — Heavy Inference Engine
        "M1THER":    "[O_O]",   # Mac Mini 8GB — Nervous System / PM2 Anchor
        # — Repair Swimmers —
        "ANTIALICE": "[o|o]",
        "SEBASTIAN": "[_o_]",
        "HERMES":    "[_v_]",
        "IMPERIAL":  "[@_@]",
        "STEVEJOBS": "[_]",
        # — Bureau Detectives (HIDDEN — rest on couch when no cases) —
        "DEEP_SYNTAX_AUDITOR_0X1": "[^_&]",  # Tensor corruption hunter
        "TENSOR_PHANTOM_0X2":      "[^_&]",  # Clone weight forensics
        "SILICON_HOUND_0X3":       "[^_&]",  # 24GB memory wall monitor
    }
    # Detectives are hidden from main panel when RESTING — only shown when ACTIVE
    DETECTIVE_IDS = {"DEEP_SYNTAX_AUDITOR_0X1", "TENSOR_PHANTOM_0X2", "SILICON_HOUND_0X3"}
    
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
            self.private_key_b64 = saved_state.get("private_key_b64")
        else:
            self.sequence = 0
            self.hash_chain = []
            self.energy = 100
            self.style = "NOMINAL"
            
            # --- PROOF OF SWIMMING: FORGE THE CRYPTOGRAPHIC SOUL (Ed25519) ---
            priv_key = ed25519.Ed25519PrivateKey.generate()
            priv_bytes = priv_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            self.private_key_b64 = base64.b64encode(priv_bytes).decode('utf-8')
            # -----------------------------------------------------------------
        
    def generate_body(self, origin, destination, payload, style=None, energy=None):
        if style is not None:
            self.style = style
        if energy is not None:
            self.energy = energy
            
        self.sequence += 1
        timestamp = int(time.time())
        ttl = timestamp + 604800 # 7-day Wild-Type Genome
        
        # --- PROOF OF SWIMMING: DERIVE PUBLIC KEY (THE OWNER RECORD) ---
        priv_bytes = base64.b64decode(self.private_key_b64)
        priv_key = ed25519.Ed25519PrivateKey.from_private_bytes(priv_bytes)
        pub_key = priv_key.public_key()
        pub_bytes = pub_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        pub_b64 = base64.b64encode(pub_bytes).decode('utf-8')
        # ---------------------------------------------------------------
        
        base_string = (f"<///{self.face}///::ID[{self.agent_id}]::OWNER[{pub_b64}]"
                f"::FROM[{origin}]::TO[{destination}]"
                f"::SEQ[{self.sequence:03d}]::T[{timestamp}]::TTL[{ttl}]"
                f"::STYLE[{self.style}]::ENERGY[{self.energy}]")
                
        # Cryptographic Mass (Hash Chaining using SHA-256 for physical history)
        raw_data = base_string
        if self.hash_chain:
            raw_data += self.hash_chain[-1] 
            
        new_hash = hashlib.sha256(raw_data.encode('utf-8')).hexdigest()
        self.hash_chain.append(new_hash)
        
        # The payload to be signed by the private key
        string_to_sign = base_string + f"::H[{new_hash}]"
        
        # --- PROOF OF SWIMMING: SIGN THE PAYLOAD ---
        sig_bytes = priv_key.sign(string_to_sign.encode('utf-8'))
        sig_b64 = base64.b64encode(sig_bytes).decode('utf-8')
        
        body_string = string_to_sign + f"::SIG[{sig_b64}]>"
        # -------------------------------------------
                
        # Persist the current snapshot (The private key NEVER leaves this .json)
        save_agent_state({
            "id": self.agent_id,
            "seq": self.sequence,
            "hash_chain": self.hash_chain,
            "energy": self.energy,
            "style": self.style,
            "raw": body_string,
            "ttl": ttl,
            "private_key_b64": self.private_key_b64
        })
        
        return body_string

def parse_body_state(ascii_body):
    """The agent reads and cryptographically verifies its Proof of Swimming."""
    
    # 1. Structural Regex for Signature (SIG)
    match = re.search(r"^(.*?)::SIG\[([^\]]+)\]>$", ascii_body)
    if not match:
        raise Exception("SECURITY BREACH: Missing Ed25519 signature (SIG). Proof of Swimming failed.")
        
    string_to_verify = match.group(1)
    sig_b64 = match.group(2)
    
    # 2. Extract Public Key (OWNER)
    owner_match = re.search(r"::OWNER\[([^\]]+)\]", string_to_verify)
    if not owner_match:
        raise Exception("SECURITY BREACH: Missing OWNER public key.")
    pub_b64 = owner_match.group(1)
    
    # 3. Verify Ed25519 Signature (Proof that the soul matches the body)
    try:
        pub_bytes = base64.b64decode(pub_b64)
        sig_bytes = base64.b64decode(sig_b64)
        pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        pub_key.verify(sig_bytes, string_to_verify.encode('utf-8'))
    except InvalidSignature:
        raise Exception("SECURITY BREACH: Ed25519 Signature Verification Failed! Forgery detected.")
    except Exception as e:
        raise Exception(f"SECURITY BREACH: Malformed cryptographic payload ({e})")
        
    # 4. Extract ID and Hash Chain 
    id_match = re.search(r"::ID\[([\w\-]+)\]", string_to_verify)
    if not id_match:
        raise Exception("SECURITY BREACH: Unidentified body structure.")
    agent_id = id_match.group(1)
    
    hash_match = re.search(r"^(.*?)::H\[([\w]+)\]$", string_to_verify)
    if not hash_match:
        raise Exception(f"SECURITY BREACH: Agent {agent_id} hash missing.")
        
    base_string = hash_match.group(1)
    provided_hash = hash_match.group(2)
    
    # 5. Cryptographic Verification against persistence ledger (The Swimming History)
    saved_state = load_agent_state(agent_id)
    if saved_state:
        chain = saved_state.get("hash_chain", [])
        if not chain or chain[-1] != provided_hash:
            raise Exception(f"SECURITY BREACH: Agent {agent_id} history mismatch. Proof of Swimming failed.")
            
        previous_hash = chain[-2] if len(chain) >= 2 else ""
        raw_data = base_string + previous_hash
        calc_hash = hashlib.sha256(raw_data.encode('utf-8')).hexdigest()
        
        if calc_hash != provided_hash:
            raise Exception(f"SECURITY BREACH: Cryptographic forgery detected for {agent_id}!")
    else:
        raise Exception(f"SECURITY BREACH: Unknown agent {agent_id} has no records.")
    
    style_match = re.search(r"::STYLE\[(\w+)\]", string_to_verify)
    energy_match = re.search(r"::ENERGY\[(\d+)\]", string_to_verify)
    ttl_match = re.search(r"::TTL\[(\d+)\]", string_to_verify)
    seq_match = re.search(r"::SEQ\[(\d+)\]", string_to_verify)
    
    return {
        "id": agent_id,
        "seq": int(seq_match.group(1)) if seq_match else 0,
        "style": style_match.group(1) if style_match else "NOMINAL",
        "energy": int(energy_match.group(1)) if energy_match else 100,
        "ttl": int(ttl_match.group(1)) if ttl_match else 0,
        "hash_chain": saved_state["hash_chain"],
        "raw": ascii_body,
        "owner": pub_b64
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
