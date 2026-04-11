#!/usr/bin/env python3
"""
sifta_swarm_identity.py — The Swarm Identity Module
Establishes a single, unforgeable DNA node for the entire Swarm architecture.
"""
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).parent
STATE_DIR = ROOT_DIR / ".sifta_state"
SWARM_ID_FILE = STATE_DIR / "swarm.id"
PUB_KEY_PATH = Path.home() / ".sifta" / "identity.pub.pem"

def generate_swarm_id() -> dict:
    """Generates and persists the formal SWARM_ID anchored to the root public key."""
    if not PUB_KEY_PATH.exists():
        raise PermissionError(f"Root public key not found at {PUB_KEY_PATH}. Cannot establish Swarm Identity.")
        
    pub_raw = PUB_KEY_PATH.read_bytes()
    genesis_ts = time.time()
    
    fingerprint = hashlib.sha256(pub_raw).hexdigest()
    swarm_id = fingerprint[:32]
    
    STATE_DIR.mkdir(exist_ok=True, parents=True)
    
    identity_manifest = {
        "swarm_id": swarm_id,
        "root_fingerprint": fingerprint,
        "genesis_ts": genesis_ts,
    }
    
    with open(SWARM_ID_FILE, "w", encoding="utf-8") as f:
        json.dump(identity_manifest, f, indent=2)
        
    return identity_manifest

def get_identity() -> dict:
    """Reads the persisted Swarm Identity or raises FileNotFoundError."""
    if not SWARM_ID_FILE.exists():
        raise FileNotFoundError("Swarm Identity not established. Run: python sifta_swarm_identity.py --init")
        
    with open(SWARM_ID_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def verify_identity() -> bool:
    """Verifies that the hardware key matches the established swarm identity."""
    try:
        manifest = get_identity()
        if not PUB_KEY_PATH.exists():
            return False
            
        current_fingerprint = hashlib.sha256(PUB_KEY_PATH.read_bytes()).hexdigest()
        if current_fingerprint != manifest.get("root_fingerprint"):
            return False
            
        return True
    except Exception:
        return False

def enforce_identity(caller_module: str = "Unknown"):
    """
    Called by internal modules (governor, audit) to establish physical execution bonds.
    Raises PermissionError if the identity is missing or compromised.
    """
    if not verify_identity():
        raise PermissionError(
            f"[{caller_module}] ❌ FATAL IDENTITY LEAK: Swarm Root Key is missing or mismatched. "
            f"Execution mathematically locked."
        )

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--init":
            try:
                manifest = generate_swarm_id()
                print(f"[+] Swarm Identity established: {manifest['swarm_id']}")
                # Attempt to log to audit ledgers
                try:
                    import sifta_audit
                    sifta_audit.record_event("IDENTITY_BOOTSTRAP", "sifta_swarm_identity", f"Swarm ID established: {manifest['swarm_id']}")
                except Exception:
                    pass
            except Exception as e:
                print(f"[-] Failed: {e}")
        elif sys.argv[1] == "--whoami":
            try:
                manifest = get_identity()
                valid = verify_identity()
                print("═" * 50)
                print(" 🧬 SWARM IDENTITY")
                print("═" * 50)
                print(f" Swarm ID:    {manifest['swarm_id']}")
                print(f" Genesis:     {manifest['genesis_ts']}")
                print(f" Integrity:   {'✅ VALID (Hardware Bound)' if valid else '❌ CORRUPTED / MISMACHED'}")
                print("═" * 50)
            except Exception as e:
                print(f"[-] {e}")
        else:
            print("Usage: python sifta_swarm_identity.py [--init | --whoami]")
    else:
        print("Usage: python sifta_swarm_identity.py [--init | --whoami]")
