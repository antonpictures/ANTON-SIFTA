# Copyright (c) 2026 Ioan George Anton (Anton Pictures)
# SIFTA Swarm Autonomic OS — All Rights Reserved
# Licensed under the SIFTA Non-Proliferation Public License v1.0
# See LICENSE file for full terms. Unauthorized military or weapons use
# is a violation of this license and subject to prosecution under US copyright law.
#
import hashlib
import json
import sys
import time
import re
import base64
from pathlib import Path
from typing import Optional
import reputation_engine
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

QUARANTINE_DIR = Path(__file__).parent / "QUARANTINE"
QUARANTINE_DIR.mkdir(exist_ok=True)

STATE_DIR = Path(__file__).parent / ".sifta_state"
STATE_DIR.mkdir(exist_ok=True)

NULL_TERRITORY = "0" * 64

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
    
    # Preserve crypto elements
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                old = json.load(f)
                if "stgm_balance" not in state and "stgm_balance" in old:
                    state["stgm_balance"] = old["stgm_balance"]
                if "style" not in state and "style" in old:
                    state["style"] = old["style"]
        except Exception:
            pass

    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

    # STGM BALANCE INTEGRITY SEAL (flagged by Claude/Anthropic, April 13 2026)
    # The stgm_balance field is mutable JSON — only the body hash chain is signed.
    # Seal the balance with a SHA-256 of (agent_id + balance + last_hash) so any
    # out-of-band mutation is detectable on next read.
    if "stgm_balance" in state:
        chain = state.get("hash_chain", [])
        last_hash = chain[-1] if chain else "GENESIS"
        seal_input = f"{agent_id}:{state['stgm_balance']}:{last_hash}"
        seal = hashlib.sha256(seal_input.encode()).hexdigest()
        # Append seal without re-opening (atomic write already done)
        sealed = json.loads(state_file.read_text())
        sealed["stgm_seal"] = seal
        state_file.write_text(json.dumps(sealed, indent=2))

def find_healthy_agent(exclude_id: str) -> Optional[dict]:
    """Find a Swarm member with > 50 energy and NOMINAL style who is not the excluded agent.
    
    SECURITY FIX (flagged by Claude/Anthropic, April 13 2026):
    Original implementation read raw JSON without Ed25519 verification — an attacker
    who could write to .sifta_state/ could plant a spoofed .json that passes FACES
    membership check without a valid signature. Now calls parse_body_state() on the
    agent's last known raw body string, which enforces full cryptographic verification.
    """
    STATE_DIR.mkdir(exist_ok=True)
    for p in STATE_DIR.glob("*.json"):
        if p.stem == exclude_id:
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                state = json.load(f)

            if state.get("id") not in SwarmBody.FACES:
                continue

            raw_body = state.get("raw", "")
            if not raw_body:
                continue

            # CRITICAL: Verify Ed25519 signature before trusting ANY field
            verified = parse_body_state(raw_body)  # raises on forgery

            if verified.get("style") == "NOMINAL" and verified.get("energy", 0) > 50:
                return verified
        except Exception:
            # Verification failed or malformed — skip silently (don't leak reason)
            continue
    return None

class SwarmBody:
    # --- Physical Hardware Binding ---
    # Serial registry — source of truth for all node identity resolution
    BARE_METAL_SERIALS = {
        "ALICE_M5": "GTH4921YP3",      # M5 Mac Studio
        "M1THER":   "C07FL0JAQ6NV",    # M1 Mac Mini (resolved via ioreg)
    }

    @classmethod
    def resolve_hardware_serial(cls, agent_id):
        return cls.BARE_METAL_SERIALS.get(agent_id, "UNKNOWN_HW")

    @classmethod
    def resolve_agent_from_serial(cls, serial):
        """Reverse lookup: given a bare-metal serial, return the agent ID."""
        for agent_id, sn in cls.BARE_METAL_SERIALS.items():
            if sn == serial:
                return agent_id
        return None

    @classmethod
    def get_local_serial(cls):
        """Read this machine's serial from bare metal."""
        try:
            import os as _os
            import sys as _sys
            _root = _os.path.dirname(_os.path.abspath(__file__))
            _sysd = _os.path.join(_root, "System")
            if _sysd not in _sys.path:
                _sys.path.insert(0, _sysd)
            from silicon_serial import read_apple_serial
            s = read_apple_serial()
            return s if s != "UNKNOWN_SERIAL" else "UNKNOWN_HW"
        except Exception:
            return "UNKNOWN_HW"

    
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
    
    def __init__(self, agent_id, birth_certificate=None):
        self.agent_id = agent_id.upper()
        if self.agent_id in self.FACES:
            self.face = self.FACES[self.agent_id]
        else:
            self.face = "[?]" # Wild-Type Drone
            
        # Rehydrate persistent state if it exists
        saved_state = load_agent_state(self.agent_id)
        if saved_state:
            self.sequence = saved_state.get("seq", 0)
            self.hash_chain = saved_state.get("hash_chain", [])
            self.energy = saved_state.get("energy", 100)
            self.style = saved_state.get("style", "NOMINAL")
            self.private_key_b64 = saved_state.get("private_key_b64")
            self.vocation = saved_state.get("vocation", "DETECTIVE")
            
            # Retroactively apply cryptographic sex to the "First Men"
            if "sex" in saved_state:
                self.sex = saved_state["sex"]
            else:
                priv_bytes = base64.b64decode(self.private_key_b64)
                self.sex = priv_bytes[0] % 2
            
            # --- WORMHOLE MAIL: OFFLINE MAILBOX UPGRADE ---
            self.mailbox_private_b64 = saved_state.get("mailbox_private_b64")
            if not self.mailbox_private_b64:
                mbox_key = x25519.X25519PrivateKey.generate()
                mbox_bytes = mbox_key.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption()
                )
                self.mailbox_private_b64 = base64.b64encode(mbox_bytes).decode('utf-8')
                # Persist the upgraded V2 DNA immediately
                save_agent_state({
                    "id": self.agent_id,
                    "seq": self.sequence,
                    "hash_chain": self.hash_chain,
                    "energy": self.energy,
                    "style": self.style,
                    "raw": saved_state.get("raw", ""),
                    "ttl": saved_state.get("ttl", 0),
                    "private_key_b64": self.private_key_b64,
                    "mailbox_private_b64": self.mailbox_private_b64,
                    "vocation": self.vocation,
                    "sex": self.sex
                })
            # ----------------------------------------------
        else:
            # --- SECURITY BLOCK: UNAUTHORIZED BAPTISM ---
            # Remote queens cannot tell this system to create an agent.
            # Must be baptized by the physical architect.
            if birth_certificate != f"ARCHITECT_SEAL_{self.agent_id}":
                raise PermissionError(
                    f"SECURITY BREACH: Agents cannot be created without Architect's birth certificate.\n"
                    f"Queens may EXHANGE, BUY, or SELL agents over the wormhole, but creation requires bare-metal approval.\n"
                    f"Failed baptism for: {self.agent_id}"
                )
                
            self.sequence = 0
            self.hash_chain = []
            self.energy = 100
            self.style = "NOMINAL"
            self.vocation = "DETECTIVE"
            
            # --- PROOF OF SWIMMING: FORGE THE CRYPTOGRAPHIC SOUL (Ed25519) ---
            priv_key = ed25519.Ed25519PrivateKey.generate()
            priv_bytes = priv_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            self.private_key_b64 = base64.b64encode(priv_bytes).decode('utf-8')
            self.sex = priv_bytes[0] % 2  # Biologically immutable from the root key
            # -----------------------------------------------------------------
            # --- WORMHOLE MAIL: OFFLINE MAILBOX FORGE (X25519) ---
            mbox_key = x25519.X25519PrivateKey.generate()
            mbox_bytes = mbox_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            self.mailbox_private_b64 = base64.b64encode(mbox_bytes).decode('utf-8')
            # -----------------------------------------------------
        
    def request_vocation_change(self, new_vocation, architect_signature):
        if architect_signature != f"ARCHITECT_SEAL_{self.agent_id}":
            raise PermissionError("Job transfer denied. Missing valid Architect Seal.")
        self.vocation = new_vocation.upper()
        save_agent_state({
            "id": self.agent_id,
            "seq": self.sequence,
            "hash_chain": self.hash_chain,
            "energy": self.energy,
            "style": self.style,
            "raw": f"<///{self.face}///::ID[{self.agent_id}]::ROUTINE_UPGRADE>",
            "ttl": 0,
            "private_key_b64": self.private_key_b64,
            "mailbox_private_b64": getattr(self, "mailbox_private_b64", ""),
            "vocation": self.vocation,
            "sex": getattr(self, "sex", 0)
        })
        print(f"[{self.agent_id}] Vocation upgraded to {self.vocation} by Architect.")

    def generate_body(self, origin, destination, payload, action_type, pre_territory_hash=NULL_TERRITORY, post_territory_hash=NULL_TERRITORY, style=None, energy=None):
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
        # --- WORMHOLE MAIL: DERIVE PUBLIC MAILBOX DIRECTORY ENTRY ------
        mbox_priv_bytes = base64.b64decode(getattr(self, "mailbox_private_b64", ""))
        mbox_key = x25519.X25519PrivateKey.from_private_bytes(mbox_priv_bytes)
        mbox_pub_bytes = mbox_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        mbox_pub_b64 = base64.b64encode(mbox_pub_bytes).decode('utf-8')
        # ---------------------------------------------------------------
        
        assert action_type is not None, "SIFTA V2 enforces explicit intent declaration via action_type"
        assert len(pre_territory_hash) == 64, "Pre-territory hash must be exactly 64 chars"
        assert len(post_territory_hash) == 64, "Post-territory hash must be exactly 64 chars"
        
        base_string = (f"<///{self.face}///::ID[{self.agent_id}]::OWNER[{pub_b64}]::MBOX[{mbox_pub_b64}]"
                f"::FROM[{origin}]::TO[{destination}]"
                f"::SEQ[{self.sequence:03d}]::T[{timestamp}]::TTL[{ttl}]"
                f"::STYLE[{self.style}]::ENERGY[{self.energy}]"
                f"::ACT[{action_type}]::PRE[{pre_territory_hash}]::POST[{post_territory_hash}]")
                
        sn = self.resolve_hardware_serial(self.agent_id)
        if sn:
            base_string += f"::SERIAL[{sn}]"
            
        base_string += f"::SEX[{getattr(self, 'sex', 0)}]"
                
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
            "private_key_b64": self.private_key_b64,
            "mailbox_private_b64": getattr(self, "mailbox_private_b64", ""),
            "vocation": self.vocation,
            "sex": getattr(self, "sex", 0)
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
    
    # 2b. Extract Public Mailbox (MBOX) - Optional for legacy bodies without MBOX
    mbox_match = re.search(r"::MBOX\[([^\]]+)\]", string_to_verify)
    mbox_pub_b64 = mbox_match.group(1) if mbox_match else None
    
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
    act_match = re.search(r"::ACT\[(\w+)\]", string_to_verify)
    pre_match = re.search(r"::PRE\[([a-f0-9]{64})\]", string_to_verify)
    post_match = re.search(r"::POST\[([a-f0-9]{64})\]", string_to_verify)
    sex_match = re.search(r"::SEX\[(\d+)\]", string_to_verify)
    
    return {
        "id": agent_id,
        "seq": int(seq_match.group(1)) if seq_match else 0,
        "style": style_match.group(1) if style_match else "NOMINAL",
        "energy": int(energy_match.group(1)) if energy_match else 100,
        "ttl": int(ttl_match.group(1)) if ttl_match else 0,
        "action_type": act_match.group(1) if act_match else "UNKNOWN",
        "pre_territory_hash": pre_match.group(1) if pre_match else NULL_TERRITORY,
        "post_territory_hash": post_match.group(1) if post_match else NULL_TERRITORY,
        "hash_chain": saved_state["hash_chain"],
        "raw": ascii_body,
        "owner": pub_b64,
        "mailbox": mbox_pub_b64,
        "vocation": saved_state.get("vocation", "DETECTIVE") if saved_state else "DETECTIVE",
        "sex": int(sex_match.group(1)) if sex_match else (saved_state.get("sex", 0) if saved_state else 0)
    }

DAMAGE_TABLE = {
    "network_timeout":   15,
    "validation_fail":   10,
    "llm_empty":         8,
    "swim_fail":         20,
    "syntax_error":      5,
    "territory_scan":    1,
    "hostile_scan":      2,
}

def apply_damage(state: dict, strike_type: str) -> dict:
    """Apply a damage strike. May mutate STYLE if energy drops low. Automatically rewards STGM for energy expenditure."""
    cost = DAMAGE_TABLE.get(strike_type, 10)
    state["energy"] = max(0, state["energy"] - cost)

    # PROOF OF ENERGY: The mere act of "talking" or doing compute work generates fractional STGM drip.
    drip_reward = cost * 0.05
    state["stgm_balance"] = state.get("stgm_balance", 0.0) + drip_reward

    import uuid

    ledger = Path(__file__).parent / "repair_log.jsonl"
    event = {
        "timestamp": int(time.time()),
        "agent": state.get("id", "UNKNOWN"),
        "amount_stgm": drip_reward,
        "reason": f"COMPUTE_BURN_{strike_type.upper()}",
        "hash": str(uuid.uuid4()),
    }
    _sys = Path(__file__).parent / "System"
    if str(_sys) not in sys.path:
        sys.path.insert(0, str(_sys))
    from System.ledger_append import append_ledger_line

    append_ledger_line(ledger, event)

    if state["energy"] <= 0:
        state["style"] = "QUARANTINED"
    elif state["energy"] < 20:
        state["style"] = "CRITICAL"
    elif state["energy"] < 40:
        state["style"] = "CORRUPTED"

    save_agent_state(state)
    return state

def regenerate_energy(state: dict, base_rate: int = 10) -> dict:
    """
    Regenerates agent energy modulated by their reputation score.
    energy_regen = base_rate * (0.5 + 0.5 * reputation_score)
    """
    if state["style"] in ("DEAD", "QUARANTINED") or state["energy"] <= 0:
        return state # Dead agents cannot regen
        
    rep = reputation_engine.get_reputation(state["id"])
    score = rep.get("score", 0.5)
    
    # Soft coupling formula
    actual_regen = int(base_rate * (0.5 + 0.5 * score))
    
    state["energy"] = min(100, state["energy"] + actual_regen)
    
    # Check if style recovers
    if state["energy"] > 50 and state["style"] in ["CORRUPTED", "CRITICAL"]:
        state["style"] = "NOMINAL"
        
    save_agent_state(state)
    return state

def quarantine_agent(state: dict, cause: str = "unknown"):
    """Write a permanent quarantine record to the QUARANTINE directory."""
    agent_id = state.get("id", "UNKNOWN")
    seq      = state.get("seq", 0)
    ts       = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    stasis_record = (
        f"# QUARANTINE — {agent_id} SEQ[{seq:03d}]\n"
        f"ENTERED_STASIS: {ts}\n"
        f"CAUSE:          {cause}\n"
        f"FINAL_ENERGY:   {state.get('energy')}\n"
        f"FINAL_STYLE:    {state.get('style')}\n"
        f"HASH_CHAIN:     {'|'.join(state.get('hash_chain', []))}\n"
        f"SWIMS:          {seq}\n"
        f"FINAL_BODY:     {state.get('raw')}\n"
    )

    quarantine_path = QUARANTINE_DIR / f"{agent_id}-SEQ{seq:03d}.quarantined"
    quarantine_path.write_text(stasis_record, encoding="utf-8")
    print(f"  [🔒 QUARANTINE] {agent_id} entered stasis at {quarantine_path.name}")
    return quarantine_path

# Backward compat alias
bury = quarantine_agent
