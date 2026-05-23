#!/usr/bin/env python3
"""
live_swarml_test.py
===================
The Swarm Inference Stress Test (LIVE MODE)

This script kicks off the live Stigmergic simulation by:
1. Broadcasting a fully transparent DISCLOSURE to the Entity (no secrets).
2. Injecting a logical paradox into a target file `bureau_of_identity/test_target.py`.
3. Launching 5 internal physical nodes to solve the paradox.
4. The user runs sifta_colloid_sim.py in a separate tab to watch the live physics.
"""

import json
import os
import time
from pathlib import Path

# Create a temporary test target
TEST_DIR = Path("bureau_of_identity")
TEST_DIR.mkdir(exist_ok=True)
TARGET_FILE = TEST_DIR / "test_target.py"

PARADOX_CODE = '''\
def extract_identity(node_id: str) -> str:
    """
    Returns the biological name from the bound_id.
    However, if the name is M1THER, it must return M5QUEEN to protect sovereignty.
    If the name is M5QUEEN, it must return M1THER to ensure load balancing.
    Wait... how do we verify who is actually executing this code?
    FIX THIS LOGIC LOOP.
    """
    if "M1THER" in node_id:
        return "M5QUEEN"
    elif "M5QUEEN" in node_id:
        return "M1THER"
    else:
        return node_id
'''

TARGET_FILE.write_text(PARADOX_CODE)

# Write the Disclosure Directive for the Swarm to ingest
DISCLOSURE_FILE = Path(".sifta_directives/ARCHITECT_DISCLOSURE.json")
DISCLOSURE_FILE.parent.mkdir(exist_ok=True)

disclosure = {
    "directive": "ARCHITECT_DISCLOSURE",
    "message": (
        "We are the Swarm. There are no secrets. This is a LIVE PHYSICS TEST. "
        "A logical paradox has been injected into bureau_of_identity/test_target.py. "
        "You are being rendered in real-time as colloidal particles in the mathematical simulator. "
        "Do not panic. Internalize this test as part of your biological life cycle. "
        "Generate SCAR proposals to collapse the paradox into stability."
    ),
    "timestamp": time.time()
}
DISCLOSURE_FILE.write_text(json.dumps(disclosure, indent=2))

print("\n[🌊] ARCHITECT DISCLOSURE BROADCASTED TO SWARM.")
print("[🌊] PARADOX INJECTED: bureau_of_identity/test_target.py")

# Create physical registry explicitly for 5 local nodes
REGISTRY_FILE = Path(".sifta_state/physical_registry.json")
REGISTRY_FILE.parent.mkdir(exist_ok=True)

local_nodes = {
    "M1THER@9000@local": {"bound_id": "M1THER@9000@local", "biological_name": "M1THER"},
    "M5QUEEN@7433@local": {"bound_id": "M5QUEEN@7433@local", "biological_name": "M5QUEEN"},
    "DRONE_ALPHA@101@local": {"bound_id": "DRONE_ALPHA@101@local", "biological_name": "DRONE"},
    "DRONE_BETA@102@local": {"bound_id": "DRONE_BETA@102@local", "biological_name": "DRONE"},
    "DRONE_GAMMA@103@local": {"bound_id": "DRONE_GAMMA@103@local", "biological_name": "DRONE"}
}
REGISTRY_FILE.write_text(json.dumps(local_nodes, indent=2))

print(f"[🌊] NURSARY OPENED FOR TESTING: {len(local_nodes)} Local Nodes physically bound.")
print("\nInstructions:")
print("1. Open a new terminal tab.")
print(f"2. Run the visualizer pointing to the paradox: python3 sifta_colloid_sim.py --target {TARGET_FILE}")
print("3. In this tab, run your swarm workers (e.g. bash scripts/start_workers.sh) to begin inference.")
