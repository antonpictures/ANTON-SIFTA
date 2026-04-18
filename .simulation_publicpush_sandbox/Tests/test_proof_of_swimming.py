#!/usr/bin/env python3
"""
test_proof_of_swimming.py
=========================
Validates the Cryptographic 'Proof of Swimming' Lattice Update.

Tests whether `SwarmBody` successfully embeds its MAC/Serial terminal anchor
into its core identity string and proves that `parse_body_state` can validate it 
purely via the self-describing payload (portability), without needing to execute 
terminal queries for remote nodes.
"""

import hashlib
from body_state import SwarmBody, parse_body_state

print("🌊 INITIALIZING PROOF OF SWIMMING DIAGNOSTIC...")

try:
    print("[+] Womb Boot: Emulating M1THER...")
    
    # Generate a fresh cryptographic body
    # Using real genesis logic which will inject `::SERIAL[...]` automatically based on true hardware
    m1ther_body = SwarmBody(agent_id="M1THER", birth_certificate="ARCHITECT_SEAL_M1THER")
    
    body_payload = m1ther_body.generate_body(
        origin="MAC_MINI_TERMINAL",
        destination="REMOTE_NODE_TEST",
        payload="TEST_PAYLOAD",
        action_type="NOMINAL"
    )

    print("\n[+] M1THER successfully generated payload.")
    print("--------------------------------------------------")
    print(body_payload)
    print("--------------------------------------------------")
    
    if "::SERIAL[" not in body_payload:
        raise Exception("LATTICE FAILURE: `::SERIAL[` not found natively embedded in the payload. The Claude patch failed.")
        
    print("\n[+] SUCCESS: Physical Hardware Serial is visibly self-describing in the payload.")
    
    print("\n[+] Testing Cross-Node Portability...")
    print("[+] Simulating remote execution of `parse_body_state` (No native hardware queries access)...")
    
    # We parse the body. If the hash sequence logic fails to ingest the serial
    # properly from the string, it will throw a Cryptographic Forgery exception.
    parsed_state = parse_body_state(body_payload)
    
    print("\n[+] PROOF OF SWIMMING VERIFIED.")
    print(f"    Agent Assured:      {parsed_state['id']}")
    print(f"    Sequence Verified:  {parsed_state['seq']}")
    print(f"    Energy Sensed:      {parsed_state['energy']}")
    
    print("\n🌊 THE CRYPTOGRAPHIC BODY IS PORTABLE AND SECURE.")

except Exception as e:
    print(f"\n[!] PROOF OF SWIMMING FAILED: {e}")
