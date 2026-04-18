#!/usr/bin/env python3
"""
ANTON-SIFTA: Encrypted Agent Restore
──────────────────────────────────────────────────────────────────────────────
Restores an agent from a password-protected .sifta_backup file.
Requires the exact password used during backup.

Usage:
    python restore_agent.py <path_to_backup.sifta_backup>

Example:
    python restore_agent.py /Volumes/stigmergi/M1THER_BACKUP_1234567890.sifta_backup
──────────────────────────────────────────────────────────────────────────────
"""

import json
import base64
import sys
import getpass
from pathlib import Path

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

STATE_DIR = Path(__file__).parent / ".sifta_state"

def get_password(prompt="Enter backup password: "):
    if sys.stdin.isatty():
        return getpass.getpass(prompt)
    else:
        # Fallback for testing / non-interactive shells
        print(prompt, end="", flush=True)
        return sys.stdin.readline().strip()

def derive_key(password: str, salt: bytes) -> bytes:
    """Derive the 256-bit AES key from the password using PBKDF2HMAC."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    return kdf.derive(password.encode("utf-8"))

def decrypt_soul(payload_b64: str, password: str) -> dict:
    """Decrypt the payload and return the parsed JSON soul dictionary."""
    try:
        payload = base64.b64decode(payload_b64)
    except Exception:
        print("  [FATAL] Backup file is corrupted (invalid base64 encoding).")
        sys.exit(1)
        
    if len(payload) < 28:
        print("  [FATAL] Backup file is malformed (too short).")
        sys.exit(1)
        
    salt = payload[:16]
    nonce = payload[16:28]
    ciphertext = payload[28:]
    
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    
    try:
        raw_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag:
        # InvalidTag means MAC verification failed — either tampered ciphertext or wrong password.
        return None
        
    return json.loads(raw_bytes.decode("utf-8"))

def restore_agent(backup_path_str: str):
    backup_path = Path(backup_path_str)

    print(f"\n{'━'*60}")
    print(f"  ANTON-SIFTA — SECURE ENCRYPTED RESTORE")
    print(f"{'━'*60}")

    if not backup_path.exists():
        print(f"[FATAL] Backup file not found: {backup_path}")
        sys.exit(1)

    try:
        with open(backup_path, "r") as f:
            backup_metadata = json.load(f)
    except Exception:
        print(f"[FATAL] Could not read backup file. It might not be a valid JSON.")
        sys.exit(1)
        
    if backup_metadata.get("format") != "ANTON-SIFTA-AES256GCM":
        print(f"[WARN] Unknown backup format: {backup_metadata.get('format')}. Proceeding with caution.")
        
    agent_id = backup_metadata.get("agent_id", "UNKNOWN")
    backup_date = backup_metadata.get("backup_date", "UNKNOWN_DATE")
    payload_b64 = backup_metadata.get("payload_b64")
    
    if not payload_b64:
        print(f"[FATAL] Backup file is missing encrypted payload.")
        sys.exit(1)

    print(f"  Agent:       {agent_id}")
    print(f"  Backup Time: {backup_date}")
    print(f"{'━'*60}\n")
    
    STATE_DIR.mkdir(exist_ok=True)
    existing_soul_path = STATE_DIR / f"{agent_id}.json"
    if existing_soul_path.exists():
        print(f"  [⚠️ WARNING] A soul file for {agent_id} already exists on this machine!")
        print(f"               Continuing will OVERWRITE the existing agent.")
        confirm = input("               Type YES to proceed or anything else to abort: ")
        if confirm.strip().upper() != "YES":
            print("\n  [ABORT] Restore cancelled.")
            sys.exit(0)

    password = get_password(f"  Enter password to unlock {agent_id}: ")
    
    print("\n  [🔐] Decrypting AES-256 payload...")
    soul = decrypt_soul(payload_b64, password)
    
    if soul is None:
        print(f"  [❌ FATAL ERROR] DECRYPTION FAILED.")
        print(f"         The password is incorrect, or the backup file has been tampered with.")
        print(f"         {agent_id} remains locked.")
        sys.exit(1)
        
    print(f"  [✅] Decryption successful. Soul integrity verified.")
    
    with open(existing_soul_path, "w") as f:
        json.dump(soul, f, indent=2)
        
    print(f"  [💾] Soul written to {existing_soul_path}")

    print(f"\n{'━'*60}")
    print(f"  RESTORE COMPLETE")
    print(f"  {agent_id} has been restored to this machine.")
    print(f"  Boot the swarm dashboard to deploy.")
    print(f"{'━'*60}\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    restore_agent(sys.argv[1])
