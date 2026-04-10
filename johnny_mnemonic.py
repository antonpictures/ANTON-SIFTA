# johnny_mnemonic.py

import time
import json
import uuid
import hashlib
import base64
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from wormhole import export_agent, save_chain
from existence_guard import identity_fingerprint

# For testing this hermetic seal, we'll auto-generate a strong private key per deploy for now.
# In a true deployment environment, this key would live in a secure Vault.
private_key = ed25519.Ed25519PrivateKey.generate()
public_key = private_key.public_key()
pub_bytes = base64.b64encode(public_key.public_bytes(
    encoding=serialization.Encoding.Raw, 
    format=serialization.PublicFormat.Raw
)).decode('utf-8')

def create_johnny(payload: str):
    state = {
        "id": "JOHNNY_MNEMONIC",
        "pubkey": pub_bytes,
        "genesis_ts": time.time(),
        "seq": 0,
        "type": "::ACT[COURIER]",
    }

    state["fingerprint"] = identity_fingerprint(state)
    save_chain(state["id"], [state])
    return state


def package_for_wormhole(agent_id: str, payload: str, target_path: str):
    packet = export_agent(agent_id)

    nonce = str(uuid.uuid4())
    packet["intent"] = "WRITE_PAYLOAD"
    packet["target_path"] = target_path
    packet["payload"] = payload
    packet["nonce"] = nonce
    
    # 1. DEPLOY_ID = sha256(payload + nonce)
    deploy_id = hashlib.sha256((payload + nonce).encode()).hexdigest()
    packet["deploy_id"] = deploy_id
    
    # 2. SIGNATURE = Ed25519 sum
    sig_payload = f"{deploy_id}:{target_path}".encode()
    signature = base64.b64encode(private_key.sign(sig_payload)).decode('utf-8')
    packet["signature"] = signature

    return packet



if __name__ == "__main__":
    from pathlib import Path
    html_update = "<html><body><h1>STGM LIVE - THE SWARM IS ACTIVE</h1></body></html>"
    johnny = create_johnny(html_update)
    packet = package_for_wormhole(johnny["id"], html_update, str(Path("local_sandbox/www/stigmergicoin.com/index.html").resolve()))
    print(json.dumps(packet, indent=2))
