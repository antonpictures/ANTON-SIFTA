#!/usr/bin/env python3
"""
medic_drone.py
The Surgical Swarm Unit.
Reads JSON trauma from the SIFTA ledger, applies atomic structural syntax repairs, 
generates physical rollback backups, and strictly seals the operation.
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
    print("Direct execution of medic_drone.py requires Cryptographic Signed Intent.")
    print("Generate an override token: python sifta_relay.py --sign-override medic_drone.py")
    sys.exit(1)

if auth_token:
    import sifta_audit
    try:
        sifta_audit.init_audit()
        sifta_audit.verify_cryptographic_override(auth_token, "medic_drone.py")
        print("[+] Signature Verified by Audit Layer. Proceeding.")
    except Exception as e:
        print(f"\n[SECURITY] CRYPTOGRAPHIC REJECTION")
        print(f"Override signature invalid: {e}")
        sys.exit(1)


import ast
import json
import shutil
import hashlib
from pathlib import Path

LEDGER = Path(".sifta_state/ledger")
RESOLVED_DIR = LEDGER / "resolved"
RESOLVED_DIR.mkdir(parents=True, exist_ok=True)

def atomic_deploy_with_rollback(filepath: Path, new_content: str, scar_id: str):
    """Safely transitions state utilizing the CAS + Rollback framework."""
    real_path = str(filepath.resolve())
    
    # Generate Physical Rollback state
    if filepath.exists():
        backup_path = f"{real_path}.{scar_id}.bak"
        shutil.copy2(real_path, backup_path)
        
    # Write to temp and Atomic Swap (No Partial Writes)
    tmp_path = f"{real_path}.{scar_id}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(new_content)
        
    os.replace(tmp_path, real_path)

def execute_syntax_surgery(filepath: Path, line_no: int, error_manifest: str, scar_id: str) -> bool:
    content = filepath.read_text(encoding="utf-8")
    lines = content.splitlines()
    
    if line_no > len(lines) or line_no <= 0:
        return False
        
    target_idx = line_no - 1
    target_line = lines[target_idx]
    
    repaired = False
    
    # Surgical Routine 1: Missing Colon Detection
    if "SyntaxError" in error_manifest and "expected ':'" in error_manifest.lower() or "missing colon" in error_manifest.lower() or "invalid syntax" in error_manifest.lower():
        # Heuristics + AST verification capability
        stripped = target_line.rstrip()
        keywords = ('def ', 'class ', 'if ', 'elif ', 'else:', 'for ', 'while ', 'try:', 'except ', 'with ')
        if any(stripped.lstrip().startswith(kw) for kw in keywords) and not stripped.endswith(':'):
            lines[target_idx] = target_line.rstrip() + ":"
            repaired = True

    # Surgical Routine 2: Indentation Collapse
    elif "IndentationError" in error_manifest:
        # Normalize indentation to 4 spaces 
        lines[target_idx] = target_line.replace("\t", "    ")
        repaired = True
        
    if repaired:
        new_content = "\n".join(lines) + "\n"
        # Validate that the repair actually fixed the AST structurally before committing
        try:
            compile(new_content, str(filepath), 'exec')
        except Exception as e:
            print(f"[MEDIC] Surgical rejection on {filepath.name}. Repair failed AST validation: {e}")
            return False
            
        atomic_deploy_with_rollback(filepath, new_content, scar_id)
        return True
        
    return False

def heal_organism():
    scars = list(LEDGER.glob("*.scar"))
    if not scars:
        print("[MEDIC] Scanning ledger... No open wounds detected.")
        return
        
    print(f"[*] Deploying Medic Swarm to {len(scars)} trauma sites...")
    
    for scar_file in scars:
        try:
            with open(scar_file, "r") as f:
                scar_data = json.load(f)
        except json.JSONDecodeError:
            print(f"[-] Invalid memory structure in {scar_file.name}. Bypassing.")
            continue
            
        scar_id = scar_data.get("id", "UNKNOWN")
        target_file = Path(scar_data.get("target_file", ""))
        line_no = scar_data.get("line", 0)
        manifest = scar_data.get("error_manifest", "")
        
        if not target_file.exists():
            print(f"[-] Trauma site {target_file.name} no longer exists. Stale scar.")
            continue
            
        print(f"[*] Commencing surgery on {target_file.name}:L{line_no}...")
        
        success = execute_syntax_surgery(target_file, line_no, manifest, scar_id)
        
        if success:
            shutil.move(str(scar_file), str(RESOLVED_DIR / scar_file.name))
            print(f"[+] [RESOLVED] {scar_id} -> {target_file.name} structurally stable.")
        else:
            print(f"[-] [FAILED] {scar_id} -> {target_file.name} surgery rejected. Escalating to Heavy NPU Agents.")

if __name__ == "__main__":
    heal_organism()
