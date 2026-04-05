from body_state import SwarmBody
from quorum import QuorumNode
import time
import os
import shutil

def purge_cache():
    if os.path.exists(".sifta_state"):
        shutil.rmtree(".sifta_state")
    if os.path.exists("CEMETERY"):
        shutil.rmtree("CEMETERY")

def run_assay():
    purge_cache()
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(" ANTON-SIFTA Assay: Superbot Clustering & Cryptographic Mass")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    # 1. Initialize the Secure Archive Node (M1ther)
    m1ther = QuorumNode(node_id="M1THER", threshold=3)
    print(f"[BOOT] Node {m1ther.node_id} online. Quorum threshold: {m1ther.threshold}\n")
    
    payload_hash = "A1B2C3D4"

    # 2. Agent 1 (AntiAlice) generates payload
    alice = SwarmBody("ANTIALICE")
    body_alice = alice.generate_body(origin="M5", destination="M1THER", payload=payload_hash)
    print(f"[DISPATCH] {alice.agent_id} swimming...")
    print(f"           {body_alice}")
    m1ther.process_arrival(body_alice, payload_hash)
    print("")
    
    time.sleep(0.5)

    # 3. Agent 2 (Hermes) generates payload
    hermes = SwarmBody("HERMES")
    body_hermes = hermes.generate_body(origin="M5", destination="M1THER", payload=payload_hash)
    print(f"[DISPATCH] {hermes.agent_id} swimming...")
    print(f"           {body_hermes}")
    m1ther.process_arrival(body_hermes, payload_hash)
    print("")
    
    time.sleep(0.5)
    
    # 4. Agent 3 (Sebastian) dies in transit (Simulate TTL expiry)
    sebastian = SwarmBody("SEBASTIAN")
    body_sebastian = sebastian.generate_body(origin="M5", destination="M1THER", payload=payload_hash)
    
    import re
    # Force an expired TTL to simulate death
    body_sebastian_expired = re.sub(r'::TTL\[\d+\]', f'::TTL[{int(time.time()) - 100}]', body_sebastian)
    print(f"[DISPATCH] {sebastian.agent_id} swimming (simulating 10-day delay)...")
    m1ther.process_arrival(body_sebastian_expired, payload_hash)
    print("")
    
    time.sleep(0.5)
    
    # 5. Agent 4 (Backup) makes the final delivery
    alice_backup = SwarmBody("M1THER")
    body_alice_backup = alice_backup.generate_body(origin="M5", destination="M1THER", payload=payload_hash)
    print(f"[DISPATCH] {alice_backup.agent_id} backup swimming...")
    print(f"           {body_alice_backup}")
    m1ther.process_arrival(body_alice_backup, payload_hash)
    
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

if __name__ == "__main__":
    run_assay()
