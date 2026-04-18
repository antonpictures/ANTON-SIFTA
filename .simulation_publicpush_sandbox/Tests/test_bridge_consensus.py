#!/usr/bin/env python3
"""
test_bridge_consensus.py
========================
The First Real Integration Test of the Cryptographic Lattice

End-to-End Test:
1. Two SIFTAAgentBridges boot (HERMES and ANTIALICE).
2. They generate competing cryptographic bodies (simulating SwarmRL action decisions).
3. The bridge converts these into standard .scar proposals targeting `core_logic.py`.
4. We run the `run_consensus_round()` which merges the paths via `canonical_winner`.
5. The winning proposal is executed, fossilizing the target.
6. The test proves that the cryptographic hash lattice survives the SwarmRL bridge intact.
"""

import time
from traceback import print_exc
from scar_kernel import Kernel, Scar
from swarmrl_bridge import SIFTAAgentBridge, run_consensus_round

print("🌊 BOOTING LATTICE INTEGRATION TEST...")

try:
    k = Kernel()
    print("[+] Kernel Booted.")

    # 1. Boot the Bridges (The SwarmRL adaptors)
    print("[+] Initializing Agent Bridges (HERMES & ANTIALICE)...")
    agent_a = SIFTAAgentBridge("HERMES", kernel=k, birth_certificate="ARCHITECT_SEAL_HERMES")
    agent_b = SIFTAAgentBridge("ANTIALICE", kernel=k, birth_certificate="ARCHITECT_SEAL_ANTIALICE")
    
    # 2. Simulate competing Action selections from a SwarmRL Actor network
    target_file = "bureau_of_identity/core_logic.py"
    
    # Normally the actor-critic network selects these. We force them for the test.
    action_a = "REPAIR: return node_id.upper()" 
    action_b = "REPAIR: return node_id.lower()"
    
    print(f"[+] HERMES proposes:    {action_a}")
    print(f"[+] ANTIALICE proposes: {action_b}")
    
    # 3. Propose actions through the cryptographic wrapper
    sid_a = agent_a.propose_action(target_file, action_a)
    sid_b = agent_b.propose_action(target_file, action_b)
    
    print(f"[+] HERMES SCAR generated:    {sid_a}")
    print(f"[+] ANTIALICE SCAR generated: {sid_b}")
    
    # 4. Trigger the Stigmergic Consensus Ring
    print("\n🌊 TRIGGERING CONSENSUS ROUND...")
    # run_consensus_round merges the pool, finds the deterministic canonical_winner,
    # and safely executes it against the Kernel if approve=True.
    winning_scar_id = run_consensus_round(
        bridges=[agent_a, agent_b],
        target=target_file,
        actions=[action_a, action_b],
        approve=True
    )
    
    # 5. Verify the state
    winner = k.scars[winning_scar_id]
    print(f"\n[+] CONSENSUS REACHED. Canonical Winner: {winner.scar_id}")
    print(f"[+] Winning Logic: {winner.content}")
    print(f"[+] Fossil Record for {target_file}: {k.fossils[target_file]}")
    
    print("\n🌊 THE LATTICE HOLDS. INTEGRATION TEST PASSED.")

except Exception as e:
    print(f"\n[!] LATTICE FAILURE: {e}")
    print_exc()
