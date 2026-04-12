import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from body_state import SwarmBody, save_agent_state

print("Starting baptism protocol for OPENCLAW QUEEN...")
agent_id = "OPENCLAW_QUEEN" 

try:
    # Require Architect Seal
    queen = SwarmBody(
        agent_id=agent_id, 
        birth_certificate=f"ARCHITECT_SEAL_{agent_id}"
    )

    # Save to disk
    save_agent_state({
        "id": queen.agent_id, 
        "hash_chain": queen.hash_chain, 
        "seq": queen.sequence, 
        "energy": queen.energy,
        "style": queen.style,
        "vocation": "QUEEN",
        "private_key_b64": queen.private_key_b64,
        "mailbox_private_b64": getattr(queen, "mailbox_private_b64", "")
    })
    
    print(f"SUCCESS: {agent_id} has been physically instantiated.")
    print(f"Ed25519 Identity forged. Sequence initialized to 0.")
    print(f"Energy at baseline 100.")
except Exception as e:
    print(f"BAPTISM FAILED: {e}")
