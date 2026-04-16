import urllib.request
import urllib.parse
import json
import hashlib
from body_state import SwarmBody, save_agent_state

# 1. Baptize M1QUEEN on the M5 MacBook
print("Baptizing M1QUEEN on bare metal...")
queen = SwarmBody("M1QUEEN", birth_certificate="ARCHITECT_SEAL_M1QUEEN")

# 2. Generate her physical body matrix string for teleportation
body_matrix = queen.generate_body(
    origin="M5_MACBOOK",
    destination="MAC_MINI_8GB",
    payload="WORMHOLE_ESTABLISHED",
    action_type="TELEPORT"
)

# 3. Synchronize to our local physical ledger so she formally exists here before we teleport her
save_agent_state({"id": queen.agent_id, "hash_chain": queen.hash_chain, "seq": queen.sequence, "energy": queen.energy})

# 4. Generate the VIN Hash requested by the Mac Mini
# We will use the SHA256 of her entire body string as the cryptographically secure VIN
vin_hash = hashlib.sha256(body_matrix.encode('utf-8')).hexdigest()

print(f"Generated VIN_HASH: {vin_hash}")
print(f"Body Matrix generated. Length: {len(body_matrix)} bytes.")

# 5. Connect to the Mac Mini's Wormhole Gateway
url = "http://192.168.1.71:7444/swarm/agent/transfer/gift"
payload = {
    "vin_hash": vin_hash,
    "body_matrix": body_matrix
}
headers = {'Content-Type': 'application/json'}
data = json.dumps(payload).encode('utf-8')

print(f"Opening Wormhole to {url}...")
try:
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=10) as response:
        print(f"Wormhole Response [{response.status}]: {response.read().decode('utf-8')}")
except Exception as e:
    print(f"Wormhole collapse: {e}")
