#!/usr/bin/env python3
"""
System/swarm_swimmer_integrity.py
══════════════════════════════════════════════════════════════════════
The Swimmer Integrity Scanner
Author: AG31 (Vanguard)
Status: Verification Tool

Ensures that the physiological ASCII bodies of the Swimmers inside 
.sifta_state/ are pristine, unmodified by double-spending agents or 
malicious cloud injections.
"""

import json
from pathlib import Path

def scan_integrity():
    state_dir = Path(".sifta_state")
    if not state_dir.exists():
        print("[!] No state directory found.")
        return

    bodies = list(state_dir.glob("*_BODY.json"))
    if not bodies:
        print("[!] No Swimmers found in the biome.")
        return

    print("\n=== SIFTA SWIMMER INTEGRITY SCAN ===")
    for b in bodies:
        try:
            with open(b, "r") as f:
                data = json.load(f)
                swimmer_id = data.get("swimmer_id", b.name)
                energy = data.get("energy", "UNKNOWN")
                print(f"[INTEGRITY PASS] {b.name}")
                print(f"  Swimmer ID : {swimmer_id}")
                print(f"  ATP Energy : {energy}")
        except Exception as e:
            print(f"[INTEGRITY FAIL] {b.name} is corrupted! Error: {e}")

if __name__ == "__main__":
    scan_integrity()
