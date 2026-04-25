#!/usr/bin/env python3
"""
ANTON-SIFTA: Encrypted Agent Backup
──────────────────────────────────────────────────────────────────────────────
Creates a password-protected cloned backup of an agent's soul.
The private key and state are locked via AES-256-GCM encryption.

Unlike transfer_agent.py, this DOES NOT ghost the local copy.
The agent keeps living on the current machine. This is purely for disaster recovery.

Usage:
    python backup_agent.py M1THER [output_dir]
──────────────────────────────────────────────────────────────────────────────
"""

import json
import time
import base64
import sys
import os
import getpass
from pathlib import Path

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Repo root (parent of scripts/) — not scripts/.sifta_state
ROOT_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT_DIR / ".sifta_state"

def get_password(prompt="Enter backup password: "):
    if sys.stdin.isatty():
        return getpass.getpass(prompt)
    else:
        # Fallback for testing / non-interactive shells
        print(prompt, end="", flush=True)
        return sys.stdin.readline().strip()

def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit AES key from the password using PBKDF2HMAC."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    return kdf.derive(password.encode("utf-8"))

def encrypt_soul(soul_data: dict, password: str) -> bytes:
    """Encrypt the soul JSON with AES-256-GCM. Returns concatenated base64 output."""
    raw_bytes = json.dumps(soul_data).encode("utf-8")
    
    salt = os.urandom(16)
    nonce = os.urandom(12)
    
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    
    ciphertext = aesgcm.encrypt(nonce, raw_bytes, None)
    
    # Bundle format: SALT[16] + NONCE[12] + CIPHERTEXT
    payload = salt + nonce + ciphertext
    return base64.b64encode(payload)

def backup_agent(agent_id: str, output_dir: Path):
    soul_file = STATE_DIR / f"{agent_id}.json"
    if not soul_file.exists():
        print(f"[FATAL] No soul found for {agent_id} at {soul_file}")
        sys.exit(1)
        
    with open(soul_file, "r") as f:
        soul = json.load(f)
        
    if soul.get("style") == "GHOST":
        print(f"[ERROR] {agent_id} is a GHOST. You cannot backup a transferred agent (it has no private key).")
        sys.exit(1)
        
    if not soul.get("private_key_b64"):
        print(f"[ERROR] {agent_id} has no private key. Cannot backup.")
        sys.exit(1)

    print(f"\n{'━'*60}")
    print(f"  ANTON-SIFTA — SECURE ENCRYPTED BACKUP")
    print(f"{'━'*60}")
    print(f"  Agent: {agent_id}")
    print(f"  Note:  If you lose this password, the backup is FOREVER UNRECOVERABLE.")
    print(f"{'━'*60}\n")

    p1 = get_password(f"  Lock {agent_id} with password: ")
    p2 = get_password("  Confirm password: ")
    
    if p1 != p2:
        print("\n  [FATAL] Passwords do not match. Aborting backup.")
        sys.exit(1)
        
    if len(p1) < 8:
        print("\n  [FATAL] Password is too weak. Minimum 8 characters required for cryptographic safety.")
        sys.exit(1)

    print("\n  [🔐] Deriving AES-256 key... (this may take a second)")
    encrypted_payload_b64 = encrypt_soul(soul, p1)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    backup_filename = f"{agent_id}_BACKUP_{timestamp}.sifta_backup"
    backup_path = output_dir / backup_filename
    
    backup_metadata = {
        "format": "ANTON-SIFTA-AES256GCM",
        "agent_id": agent_id,
        "backup_timestamp": timestamp,
        "backup_date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "payload_b64": encrypted_payload_b64.decode("utf-8")
    }
    
    with open(backup_path, "w") as f:
        json.dump(backup_metadata, f, indent=2)
        
    print(f"  [📦] Backup encrypted and written: {backup_path}")
    print(f"\n{'━'*60}")
    print(f"  BACKUP COMPLETE")
    print(f"  {agent_id} is still running normally on this machine.")
    print(f"  Save the .sifta_backup file to a safe location.")
    print(f"{'━'*60}\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    agent_id = sys.argv[1].upper()
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    
    backup_agent(agent_id, out_dir)
