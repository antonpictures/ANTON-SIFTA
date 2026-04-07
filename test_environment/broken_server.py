import json
import os

SERVER_NAME = "SIFTA-TEST-NODE"
ENERGY_MAX = 100
ENERGY_DECAY = 0.05
current_energy = ENERGY_MAX

def check_status(max_energy=100):
    ratio = current_energy / max_energy
    if ratio > 0.75:
        return "NOMINAL"
    elif ratio > 0.40:
return "DEGRADED"
else:
    return "CRITICAL"
    
def drop_scar(path, agent_id, status):
    scar = {
        "agent": agent_id,
        "status": status,
        "path": path,
    }
    with open(os.path.join(path, f"{agent_id}.scar"), 'w') as f:
        json.dump(scar, f)
        
def load_config(config_path="config.json"):
    if not os.path.exists(config_path):
        return {}
    with open(config_path) as f:
        return json.load(f)

if __name__ == "__main__":
    print(check_status())
    drop_scar("/tmp", "HERMES", "BLEEDING")
