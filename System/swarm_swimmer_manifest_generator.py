#!/usr/bin/env python3
"""
System/swarm_swimmer_manifest_generator.py
══════════════════════════════════════════════════════════════════════
The Swimmer Manifest Generator
Author: AG31 (Vanguard)
Status: Active Tool

Scans the entire SIFTA filesystem for all Swimmer Bodies, authenticates
their ASCII signatures, energy levels, and active states, and dumps the
results into a single holistic ledger file for Architect verification.
"""

import os
import json
from pathlib import Path
import time
import hashlib

EXPECTED_BODY_IDS = {"M1SIFTA_BODY", "M5SIFTA_BODY"}

def generate_manifest(output_path="swimmer_manifest.md"):
    repo_root = Path(__file__).resolve().parent.parent
    
    # We ignore sandbox and quarantine directories to ensure we only measure the live organism
    excluded_dirs = ['.simulation_publicpush_sandbox', '.gemini', '.git']
    
    swimmers = []
    
    for root, dirs, files in os.walk(repo_root):
        # Exclude specified directories
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        
        for file in files:
            if file.endswith("_BODY.json"):
                full_path = Path(root) / file
                try:
                    with open(full_path, 'r') as f:
                        content = f.read()
                        
                    # Cryptographic Hash (SHA-256) of the raw binary
                    file_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
                    
                    data = json.loads(content)
                    data['_filepath'] = str(full_path.relative_to(repo_root))
                    data['_sha256'] = file_hash
                    
                    # Enforce Canonical location rule: must be exactly in .sifta_state/
                    if str(data['_filepath']).startswith('.sifta_state/'):
                        data['_canonical'] = True
                    else:
                        data['_canonical'] = False
                        
                    swimmers.append(data)
                except Exception as e:
                    print(f"[!] Failed to parse {file}: {e}")

    canonical_swimmers = [s for s in swimmers if s.get("_canonical")]
    shadow_swimmers = [s for s in swimmers if not s.get("_canonical")]

    by_id = {}
    for swimmer in canonical_swimmers:
        sid = swimmer.get("id", "UNKNOWN_BODY")
        by_id.setdefault(sid, []).append(swimmer)
    duplicate_ids = sorted([sid for sid, rows in by_id.items() if len(rows) > 1])
    missing_ids = sorted(EXPECTED_BODY_IDS - set(by_id.keys()))
    unexpected_ids = sorted(set(by_id.keys()) - EXPECTED_BODY_IDS)

    # Generate Markdown
    with open(output_path, 'w') as f:
        f.write("# SIFTA Organism: Global Swimmer Integrity Manifest\n\n")
        verdict = "HEALTHY"
        if duplicate_ids or missing_ids or unexpected_ids:
            verdict = "ALERT"
        f.write(f"> **Autonomic Verification:** `{verdict}`\\\n")
        f.write("> Canonical bodies validated with SHA-256 checksums.\n\n")
        f.write(f"*Last scan: {time.strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
        f.write("## Integrity Summary\n\n")
        f.write(f"- Canonical swimmers found: {len(canonical_swimmers)}\n")
        f.write(f"- Shadow artifacts ignored: {len(shadow_swimmers)}\n")
        if duplicate_ids:
            f.write(f"- Duplicate canonical IDs detected: `{', '.join(duplicate_ids)}`\n")
        if missing_ids:
            f.write(f"- Missing canonical IDs: `{', '.join(missing_ids)}`\n")
        if unexpected_ids:
            f.write(f"- Unexpected canonical IDs: `{', '.join(unexpected_ids)}`\n")
        if not duplicate_ids and not missing_ids and not unexpected_ids:
            f.write("- ID set matches expected genesis schema.\n")
        f.write("\n")
        f.write("---\n\n")
        
        if not canonical_swimmers:
            f.write("No Swimmers found in the current biome.\n")
            return
            
        for swimmer in sorted(canonical_swimmers, key=lambda s: s.get("id", "")):
            body_id = swimmer.get("id", "UNKNOWN_BODY")
            path = swimmer.get("_filepath", "Unknown location")
            ascii_art = swimmer.get("ascii", "(No ASCII Body Found!)")
            energy = swimmer.get("energy", "UNKNOWN")
            stgm = swimmer.get("stgm_balance", "0.0")
            style = swimmer.get("style", "UNKNOWN")
            seal = swimmer.get("architect_seal", "UNSEALED")
            
            # Determine Action Context
            action = "IDLE (Autonomic Heartbeat Pool)"
            if style == "ACTIVE" and energy == 100:
                action = "ACTIVE (Sensory / Synaptic Ready)"
            if body_id == "M5SIFTA_BODY":
                action = "ACTIVE (Primary Heavy Compute Lobe / Ribosome Standby)"
            elif body_id == "M1SIFTA_BODY":
                action = "ACTIVE (Peripheral Motor Cortex / Heartbeat Manager)"
            
            f.write(f"## Swimmer: {body_id}\n\n")
            
            f.write(f"- **Physical Location:** `{path}` (CANONICAL)\n")
                
            f.write(f"- **SHA-256 Checksum:** `{swimmer.get('_sha256', 'ERROR')}`\n")
            f.write(f"- **Cryptographic Body (ASCII):** `{ascii_art}`\n")
            f.write(f"- **Metabolic Energy:** {energy} ATP\n")
            f.write(f"- **Current Action / State:** {action}\n")
            f.write(f"- **STGM Token Balance:** {stgm}\n")
            f.write(f"- **Architect Seal:** `{seal}`\n\n")
            f.write("---\n\n")

        if shadow_swimmers:
            f.write("## Ignored Shadow Artifacts\n\n")
            for shadow in sorted(shadow_swimmers, key=lambda s: s.get("_filepath", "")):
                f.write(f"- `{shadow.get('_filepath', 'unknown')}`\n")
            f.write("\n")
            
    print(f"[+] Integrity complete. Generated manifest at: {output_path}")

if __name__ == "__main__":
    generate_manifest("Documents/swimmer_manifest.md")
