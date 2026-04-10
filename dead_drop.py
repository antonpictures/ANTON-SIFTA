import json
import base64
import hashlib
import time as tmod
import urllib.request
import urllib.error
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# In production this would be read from config.json
DEFAULT_RELAY = "http://127.0.0.1:8000"

def push_to_relay(agent_id: str, target_pubkey: str, state_dir: Path, new_owner: str, relay_url: str = DEFAULT_RELAY) -> dict:
    soul_file = state_dir / f"{agent_id}.json"
    if not soul_file.exists():
        return {"ok": False, "error": f"No soul for {agent_id}"}
        
    with open(soul_file, "r") as f:
        soul = json.load(f)
        
    if soul.get("style") == "GHOST":
        return {"ok": False, "error": f"{agent_id} is already a GHOST. Cannot transmit."}
        
    if not soul.get("private_key_b64"):
        return {"ok": False, "error": f"{agent_id} has no private key. Cannot transmit."}
        
    priv_bytes = base64.b64decode(soul["private_key_b64"])
    priv_key = ed25519.Ed25519PrivateKey.from_private_bytes(priv_bytes)
    pub_bytes = priv_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    pub_b64 = base64.b64encode(pub_bytes).decode()
    
    timestamp = int(tmod.time())
    from_owner = soul.get("human_owner", "unknown")
    
    deed_payload = (
        f"RELAY_DROP::{agent_id}::FROM[{from_owner}]::TO[{new_owner}]"
        f"::T[{timestamp}]::PUBKEY[{pub_b64}]"
    )
    sig_bytes = priv_key.sign(deed_payload.encode())
    sig_b64 = base64.b64encode(sig_bytes).decode()
    deed_hash = hashlib.sha256(deed_payload.encode()).hexdigest()
    
    soul_export = dict(soul)
    soul_export["human_owner"] = new_owner
    soul_export["transferred_at"] = tmod.strftime("%Y-%m-%dT%H:%M:%SZ", tmod.gmtime())
    soul_export["deed_hash"] = deed_hash
    
    payload = {
        "soul": soul_export,
        "deed": {
            "agent_id": agent_id,
            "from_owner": from_owner,
            "to_owner": new_owner,
            "timestamp": timestamp,
            "pub_key": pub_b64,
            "deed_sig": sig_b64,
            "deed_payload": deed_payload,
            "deed_hash": deed_hash,
            "protocol": "DEAD_DROP_V1"
        }
    }
    
    drop_req = {
        "to_pubkey": target_pubkey,
        "payload": payload
    }
    
    try:
        url = f"{relay_url.rstrip('/')}/drop"
        req = urllib.request.Request(url, data=json.dumps(drop_req).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if not data.get("ok"):
                return {"ok": False, "error": f"Relay rejected: {data.get('error')}"}
                
        # Ghost it locally
        ghost_state = {
            "id": soul["id"],
            "seq": soul["seq"],
            "hash_chain": soul.get("hash_chain", []),
            "energy": 0,
            "style": "GHOST",
            "ttl": 0,
            "raw": soul.get("raw", ""),
            "private_key_b64": None,
            "transferred_to": target_pubkey,
            "transfer_deed_hash": deed_hash,
            "transferred_at": soul_export["transferred_at"],
            "protocol": "DEAD_DROP_V1"
        }
        with open(soul_file, "w") as f:
            json.dump(ghost_state, f, indent=2)
            
        return {"ok": True, "output": f"Pushed to Relay! Drop ID: {data.get('drop_id')}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def fetch_from_relay(my_pubkey: str, state_dir: Path, relay_url: str = DEFAULT_RELAY) -> dict:
    import urllib.parse
    safe_pub = urllib.parse.quote_plus(my_pubkey)
    try:
        url = f"{relay_url.rstrip('/')}/pickup/{safe_pub}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if not data.get("ok"):
                return {"ok": False, "error": f"Relay error: {data.get('error')}"}
                
        drops = data.get("drops", [])
        if not drops:
            return {"ok": True, "output": "No pending drops found.", "count": 0}
            
        received = []
        for drop in drops:
            drop_id = drop["drop_id"]
            payload = drop["payload"]
            soul = payload["soul"]
            agent_id = soul["id"]
            
            # Save it
            soul_file = state_dir / f"{agent_id}.json"
            if soul_file.exists():
                with open(soul_file, "r") as f:
                    local_soul = json.load(f)
                if local_soul.get("style") != "GHOST":
                    # We might already have it or conflict, but Dead drop usually overrides
                    pass
            
            with open(soul_file, "w") as f:
                json.dump(soul, f, indent=2)
                
            received.append(agent_id)
            
            # Send ACK to delete from relay
            ack_url = f"{relay_url.rstrip('/')}/pickup/{safe_pub}/{drop_id}"
            ack_req = urllib.request.Request(ack_url, method="DELETE")
            try:
                urllib.request.urlopen(ack_req, timeout=10)
            except Exception as e:
                print(f"[DEAD_DROP] Failed to ACK drop {drop_id}: {e}")
                
        return {"ok": True, "output": f"Fetched {len(received)} agents from Relay.", "count": len(received)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
