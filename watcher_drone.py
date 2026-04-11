#!/usr/bin/env python3
"""
watcher_drone.py – Stigmergic Node Scanner
"""
import os
import sys

# THE OBSERVABLE EXECUTION BOUNDARY
is_cardio = (os.environ.get("SIFTA_CARDIO") == "1")

auth_token = None
for arg in sys.argv:
    if arg.startswith("--auth-token="):
        auth_token = arg.split("=", 1)[1]

if not is_cardio and not auth_token:
    print("\n[SECURITY] SIFTA CONTROL PLANE BOUNDARY")
    print("Direct execution of watcher_drone.py requires Cryptographic Signed Intent.")
    print("Generate an override token: python sifta_relay.py --sign-override watcher_drone.py")
    sys.exit(1)

if auth_token:
    import sifta_audit
    try:
        sifta_audit.init_audit()
        sifta_audit.verify_cryptographic_override(auth_token, "watcher_drone.py")
        print("[+] Signature Verified by Audit Layer. Proceeding.")
    except Exception as e:
        print(f"\n[SECURITY] CRYPTOGRAPHIC REJECTION")
        print(f"Override signature invalid: {e}")
        sys.exit(1)

import ast
import json
import time
import hashlib
from pathlib import Path

TARGET_DIR = Path("test_environment/target_zone")
LEDGER_DIR = Path(".sifta_state/ledger")

def calculate_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def drop_scar(filepath: Path, line_number: int, error_msg: str):
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    
    scar_id = f"SCAR_{hashlib.md5(f'{filepath}:{line_number}:{error_msg}'.encode()).hexdigest()[:12]}"
    
    # We want these scars to be picked up by the swarm workers
    scar_payload = {
        "id": scar_id,
        "type": "::ACT[REPORT_ANOMALY]",
        "scout": "WATCHER_DRONE_01",
        "target_file": str(filepath.resolve()),
        "line": line_number,
        "error_manifest": error_msg,
        "timestamp": time.time(),
        "status": "OPEN_WOUND"
    }
    
    scar_path = LEDGER_DIR / f"{scar_id}.scar"
    if not scar_path.exists():
        with open(scar_path, "w") as f:
            json.dump(scar_payload, f, indent=2)
        print(f"[WATCHER] Trauma detected. Dropped {scar_id}.scar for {filepath.name}")

def scan_target_zone():
    print(f"[*] Deploying Watcher Drone over {TARGET_DIR}...")
    if not TARGET_DIR.exists():
        print("[-] Target zone does not exist.")
        return
        
    # Territorial Bounding: Do not bleed for dependencies or caches.
    EXCLUDE_DIRS = {".venv", "node_modules", ".git", "__pycache__", "vendor", "env", "build", ".sifta_state", ".sifta_reputation"}
        
    for p in TARGET_DIR.rglob("*.py"):
        # Explicit Territorial Guard
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
            
        try:
            content = p.read_text(encoding='utf-8')
            # Attempt to parse AST to inherently catch syntax errors 
            compile(content, str(p), 'exec')
            
            # If we want deeper logic bugs rather than just syntax, 
            # we could evaluate it using pylint, but for now Syntax is a hard collision.
        except SyntaxError as e:
            drop_scar(p, e.lineno or 0, f"SyntaxError: {e.msg}")
        except IndentationError as e:
            drop_scar(p, e.lineno or 0, f"IndentationError: {e.msg}")
        except Exception as e:
            drop_scar(p, 0, f"Unknown Parse Error: {str(e)}")

if __name__ == "__main__":
    scan_target_zone()
    print("[*] Watcher deployment complete. Returning to anchor.")
