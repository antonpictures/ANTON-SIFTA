import json
from pathlib import Path

STATE_DIR = Path(".sifta_state")
m1_agents = ["M1SIFTA_BODY", "MACMINI.LAN", "M1THER"]
m5_agents = ["SIFTA_QUEEN", "STRIATAL_BEAT_CLOCK", "CONVERSATION_CHAIN", 
             "SUPERIOR_COLLICULUS", "PHYSARUM_ENGINE", "EVENT_CLOCK", 
             "FMO_QUANTUM_ENGINE", "SYSTEM_IDE", "SHAME_REGISTRY"]

for a in m1_agents:
    fpath = STATE_DIR / f"{a}.json"
    if fpath.exists():
        data = json.loads(fpath.read_text())
        data["homeworld_serial"] = "C07FL0JAQ6NV"
        fpath.write_text(json.dumps(data, indent=2))

for a in m5_agents:
    fpath = STATE_DIR / f"{a}.json"
    if fpath.exists():
        data = json.loads(fpath.read_text())
        data["homeworld_serial"] = "GTH4921YP3"
        fpath.write_text(json.dumps(data, indent=2))

print("JSON cache files patched.")
