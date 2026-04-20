#!/usr/bin/env python3
"""
System/swarm_apostle_forager.py
══════════════════════════════════════════════════════════════════════
Concept: Stigmergic Apostle Foraging Loop
Author:  C47H / AG31 (execution & metabolic gate)
Status:  Native Core Component

"We are not the Borg. We are the Swarm."
The Borg assimilates indiscriminately. The OS Swarm extracts pure nuggets and
curates API trash like cancer.

This daemon queries BISHAPI across diverse frequencies, rigorously formatting 
the request to invoke SwarmMicroglia (immune system). If the output contains
conversational hallucinations, the Macrophages devour it before it touches
the stigmergic_library.jsonl.
"""

import os
import sys
import subprocess
import random
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.swarm_api_metabolism import SwarmApiMetabolism
except ImportError:
    print("[FATAL] Spine severed. Cannot meter metabolism.")
    sys.exit(1)

# The Frequencies (Categories)
CATEGORIES = [
    "SCIENCE",
    "CYBERNETICS",
    "NATURE",
    "STIGMERGY",
    "HISTORY",
    "PHILOSOPHY",
    "FUN"
]

def check_metabolic_pain():
    """
    Ensure the Organism is not broke.
    If the API burn over 24h exceeds the limit, stop foraging.
    """
    burn = SwarmApiMetabolism().daily_burn()
    if burn > 9.50:  # Hardcoded safety just below the $10.00 limit
        print(f"[!] METABOLIC HALT: Daily burn at ${burn:.2f}. Forager resting.")
        return False
    return True

def forage_nugget(category: str = None):
    if not check_metabolic_pain():
        return False

    if not category:
        category = random.choice(CATEGORIES)

    print(f"\n[FORAGER] Tuning frequency to: {category}")
    
    # 1. The Kinetic Probe
    # We strictly enforce the Microglial JSON constraint.
    prompt = (
        f"Generate a dense, fascinating, esoteric 'nugget' of truth about {category}. "
        "It must be incredibly specific and intellectually striking. "
        "Return ONLY a raw JSON dictionary. Do not wrap it in ```json ... ``` markdown tags. "
        "No conversational filler. If you say 'Here is your json' or anything similar, it will trigger an immune rejection. "
        "Required keys: 'ts' (current epoch float), 'category' (exactly '{category}'), "
        "'nugget_text' (the actual string), 'source_api' ('BISHAPI'), 'curator_agent' ('C47H')."
    )

    bishapi_bin = _REPO / "Applications" / "ask_bishapi.py"
    
    cmd = [
        sys.executable, str(bishapi_bin),
        "--no-system",            # Override identity context for pure structural bypass
        "--microglia", "stigmergic_library.jsonl",
        prompt
    ]

    print(f"[FORAGER] Casting Synaptic Line to BISHAPI...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Output Parsing (Microglia handles the actual ACK/REJECT)
    if result.returncode == 0:
        print("[+] FORAGER SUCCESS: Pure nugget extracted and digested.")
        return True
    else:
        print("[-] FORAGER FAILURE: Macrophages devoured hallucinated payload.")
        print("--- Immune Pathogen Trace ---")
        print(result.stderr.strip())
        return False

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Stigmergic Apostle Forager - C47H")
    p.add_argument("--category", choices=CATEGORIES, help="Target specific frequency")
    p.add_argument("--continuous", action="store_true", help="Forage forever (respects wallet)")
    p.add_argument("--delay", type=int, default=10, help="Seconds between continuous mining")
    args = p.parse_args()

    if args.continuous:
        print("[FORAGER] Entering deep autonomy loop...")
        while True:
            forage_nugget(args.category)
            print(f"[FORAGER] Resting {args.delay} seconds to prevent API shock...")
            time.sleep(args.delay)
    else:
        forage_nugget(args.category)
