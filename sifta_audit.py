"""
sifta_audit.py — The SIFTA Observability & Recovery Layer
Maintains an immutable record of system events, manual overrides, and state recoveries.
This sits *above* the execution loop, ensuring bypasses are visible.
"""
import sqlite3
import time
from pathlib import Path

STATE_DIR = Path(".sifta_state")
LEDGER_DB = STATE_DIR / "task_ledger.db"

def init_audit():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(LEDGER_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            event_type TEXT,
            component TEXT,
            details TEXT
        )
    ''')
    conn.commit()
    conn.close()

def record_event(event_type: str, component: str, details: str):
    """
    Records an event into the audit ledger. 
    Examples: POLICY_BYPASS, STATE_RECOVERY, FATAL_CRASH
    """
    try:
        conn = sqlite3.connect(LEDGER_DB)
        conn.execute(
            "INSERT INTO audit_log (timestamp, event_type, component, details) VALUES (?, ?, ?, ?)",
            (time.time(), event_type.upper(), component, details)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[!] Audit write failed: {e}")

def verify_cryptographic_override(auth_token_b64: str, target_binary: str):
    """
    Verifies that a manual override token was cryptographically signed by an
    Authorized Architect, meant for this specific binary, and has not expired.
    """
    import sifta_swarm_identity
    sifta_swarm_identity.enforce_identity("SIFTA_AUDIT")

    import base64
    import json
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives import serialization

    PUB_KEY_PATH = Path.home() / ".sifta" / "authorized_keys" / "macbook.pub.pem"
    if not PUB_KEY_PATH.exists():
        raise PermissionError("No authorized public keys found on this node.")
        
    try:
        envelope_json = base64.b64decode(auth_token_b64).decode("utf-8")
        envelope = json.loads(envelope_json)
    except Exception:
        raise ValueError("Auth token is not a valid base64 JSON envelope.")
        
    # Check TTL and target constraint
    if time.time() > envelope.get("timestamp", 0) + envelope.get("ttl_seconds", 0):
        raise ValueError("Override token expired (TTL exceeded).")
        
    if envelope.get("target_binary") != target_binary:
        raise ValueError(f"Token bounded to [{envelope.get('target_binary')}], not [{target_binary}].")
        
    # Verify Signature
    signature = base64.b64decode(envelope["signature"])
    canonical_payload = {
        "action": envelope["action"],
        "target_binary": envelope["target_binary"],
        "timestamp": envelope["timestamp"],
        "ttl_seconds": envelope["ttl_seconds"]
    }
    canonical_str = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
    
    pub_key_bytes = PUB_KEY_PATH.read_bytes()
    public_key = serialization.load_pem_public_key(pub_key_bytes)
    
    try:
        public_key.verify(signature, canonical_str.encode("utf-8"))
    except Exception:
        raise PermissionError("Invalid Cryptographic Signature. Override Denied.")
        
    # If we made it here, the math holds.
    record_event("MATH_OVERRIDE", target_binary, f"Valid signature verified for {target_binary}")
    return True

if __name__ == "__main__":
    init_audit()
    print("[*] SIFTA Audit Layer Initialized in task_ledger.db.")
