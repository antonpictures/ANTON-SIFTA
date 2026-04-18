#!/usr/bin/env python3
"""
sifta_ingestor.py
The Constitutional Gatekeeper for the SIFTA Life Fabric.
It assumes all incoming transport (Telegram, iCloud) is hostile.
Validates Ed25519 signatures, Nonces, and TTLs before writing to the Task Ledger.
"""
import json
import time
import sqlite3
import base64
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

STATE_DIR = Path(".sifta_state")
LEDGER_DB = STATE_DIR / "task_ledger.db"

STATE_DIR.mkdir(parents=True, exist_ok=True)

def init_dbs():
    conn = sqlite3.connect(LEDGER_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            source TEXT,
            timestamp REAL,
            intent TEXT,
            payload JSON,
            status TEXT
        )
    ''')
    conn.execute('CREATE TABLE IF NOT EXISTS nonces (nonce TEXT PRIMARY KEY)')
    conn.commit()
    conn.close()

def verify_crypto_envelope(packet: dict, public_key_pem: bytes):
    """DeepSeek-Architected Strict Gate Sequence."""
    
    # 1. Cheap Pre-Filter (BEFORE Crypto)
    required_keys = {"nonce", "timestamp", "intent", "target", "payload", "signature"}
    if not required_keys.issubset(packet.keys()):
        raise RuntimeError("[SECURITY] Malformed Schema. Burned before Crypto.")
        
    # 2. Signature Math (FIRST REAL GATE)
    try:
        pubkey = serialization.load_pem_public_key(public_key_pem)
        
        # Strict Canonical JSON (Attack-Proof Whitespace)
        canonical_obj = {
            "nonce": packet['nonce'],
            "timestamp": packet['timestamp'],
            "intent": packet['intent'],
            "target": packet['target'],
            "payload": packet['payload']
        }
        canonical_string = json.dumps(canonical_obj, sort_keys=True, separators=(",", ":"))
        
        signature_bytes = base64.b64decode(packet["signature"])
        pubkey.verify(signature_bytes, canonical_string.encode('utf-8'))
        
    except InvalidSignature:
        raise RuntimeError("[SECURITY] Ed25519 Signature Invalid. Hostile Override Detected.")
    except Exception as e:
        raise RuntimeError(f"[SECURITY] Envelope parsing failed: {e}")

    # 3. Trust the Data (Now that Auth Passed)
    # Check TTL
    current_time = time.time()
    if current_time > packet["timestamp"] + packet.get("ttl", 60):
        raise RuntimeError("[SECURITY] Packet TTL expired. Replay attack blocked.")

    return True

def ingest_command_envelope(raw_json: str, phone_pubkey: bytes):
    """The only public entrypoint to SIFTA's nervous system."""
    MAX_SIZE = 5 * 1024 * 1024 # 5MB limit
    if len(raw_json.encode('utf-8')) > MAX_SIZE:
        print("[-] Packet exceeds DOS bounds. Burned.")
        return None

    try:
        packet = json.loads(raw_json)
        
        # 1. & 2. & 3. Validate Shape, Auth Signature, and TTL limits
        verify_crypto_envelope(packet, phone_pubkey)
        
        # 4. Atomic Nonce Lock AND Ledger Write (Single Transaction)
        task_id = hashlib.sha256(f"{packet['nonce']}{packet['timestamp']}".encode()).hexdigest()
        
        conn = sqlite3.connect(LEDGER_DB)
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION")
            cursor.execute("INSERT INTO nonces VALUES (?)", (packet["nonce"],))
            cursor.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)", (
                task_id, packet.get("source", "UNKNOWN"), packet["timestamp"], 
                packet["intent"], json.dumps(packet["payload"]), "validated"
            ))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            conn.close()
            raise RuntimeError(f"[SECURITY] Double-spend Nonce detected: {packet['nonce']}")
        conn.close()
        
        print(f"[+] Envelope Cryptographically Validated. Written to Task Ledger as {task_id[:8]}")
        return task_id
        
    except json.JSONDecodeError:
        print("[-] Malformed JSON. Envelope Burned.")
    except RuntimeError as e:
        print(f"[-] {e}")

if __name__ == "__main__":
    init_dbs()
    # In a live system, this runs constantly listening to Telegram/iCloud
    print("[*] SIFTA Ingestor initialized. Constitutional Gates Locked.")
