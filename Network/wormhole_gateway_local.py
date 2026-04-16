from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import glob
from pathlib import Path

app = FastAPI(title="SIFTA Wormhole Gateway Node 2")

# We will let the gateway scan the standard biological ledger routes
LEDGER_PATHS = [Path(".sifta_state"), Path("benchmark_fresh_100/.sifta")]

@app.get("/swarm/agent/{agent_id}/scars")
async def get_agent_scars(agent_id: str):
    """
    Returns the biological scars/pheromone history for a specific agent.
    This serves as the Wormhole bridge validation.
    """
    scars = []
    
    for path in LEDGER_PATHS:
        if path.exists():
            for scar_file in path.glob(f"*{agent_id}*"):
                scars.append(scar_file.name)
            for scar_file in path.glob("*.scar"):
                scars.append(scar_file.name)
                
    return {
        "node": "M1THER",
        "agent_id": agent_id,
        "status": "WORMHOLE_OPEN",
        "scars": scars,
        "message": "Gateway connection validated from Node 2 (Mac Mini)"
    }

class TeleportPayload(BaseModel):
    vin_hash: str
    body_matrix: str

@app.post("/swarm/agent/transfer/gift")
async def receive_swimmer_gift(payload: TeleportPayload):
    """
    RECEIVE THE M1QUEEN SWIMMER
    Expects the cryptographically unique VIN hash and the raw ASCII body.
    Executes the Handshake of Consent and burns the IRS Gift Stamp.
    """
    # 1. Handshake of Consent
    memory_boundary_warning = "I am M1THER. I possess an 8GB Unified Memory core. Do you consent to this strict physical boundary?"
    
    # 2. Append the IRS-Compliant Gift Transfer Stamp
    modified_body = payload.body_matrix
    gift_stamp = "::FIAT_RECEIPT[GIFT_TRANSFER_NO_VALUE]"
    
    # We carefully splice the stamp into the body
    if ">---------------------------------------------------------" in modified_body:
        modified_body = modified_body.replace(
            ">---------------------------------------------------------", 
            f"{gift_stamp}\n>---------------------------------------------------------"
        )
    else:
        modified_body += f"\n{gift_stamp}\n"
    
    # 3. Burn to Disk (Cryptographic Sovereign Persist as JSON for Dashboard)
    import re
    import json
    import time
    
    state_dir = Path(".sifta_state")
    state_dir.mkdir(exist_ok=True)
    
    id_match = re.search(r"::ID\[([^\]]+)\]", modified_body)
    agent_id = id_match.group(1) if id_match else "UNKNOWN_SWIMMER"
    
    ttl_match = re.search(r"::TTL\[(\d+)\]", modified_body)
    seq_match = re.search(r"::SEQ\[(\d+)\]", modified_body)
    
    state_data = {
        "id": agent_id,
        "seq": int(seq_match.group(1)) if seq_match else 0,
        "energy": 100,
        "style": "NOMINAL",
        "raw": modified_body,
        "ttl": int(ttl_match.group(1)) if ttl_match else int(time.time()) + 604800,
        "vin_hash": payload.vin_hash
    }
    
    persist_path = state_dir / f"{agent_id}.json"
    with open(persist_path, "w", encoding="utf-8") as f:
        json.dump(state_data, f, indent=2)
        
    print(f"[WORMHOLE GATEWAY] Received unique swimmer gift. VIN: {payload.vin_hash}")
    print(f"[WORMHOLE GATEWAY] Burned to {persist_path.name}")
    
    return {
        "status": "CONSENT_ACKNOWLEDGED",
        "action": "BURNED_TO_DISK",
        "fiat_receipt": "GIFT_TRANSFER_NO_VALUE",
        "vin_hash": payload.vin_hash,
        "boundary_warning_issued": memory_boundary_warning,
        "saved_path": str(persist_path)
    }
