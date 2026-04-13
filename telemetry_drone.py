#!/usr/bin/env python3
import json
import time
from pathlib import Path
import os

# SIFTA imports to target the state directories cleanly
from body_state import STATE_DIR, CEMETERY_DIR

LOG_FILE = "swarm_telemetry.log"

def run_telemetry_snapshot():
    alive_agents = 0
    total_energy = 0
    sex_distribution = {0: 0, 1: 0}
    styles = {}
    
    # 1. Tally the Living Organism
    for p in STATE_DIR.glob("*.json"):
        try:
            with open(p, "r") as f:
                state = json.load(f)
                
                # Check for biological death state
                style = state.get("style", "UNKNOWN")
                if style != "DEAD":
                    alive_agents += 1
                    total_energy += state.get("energy", 0)
                    
                    # Tally the sexes for pairing analysis
                    sex = state.get("sex", 0)
                    sex_distribution[sex] = sex_distribution.get(sex, 0) + 1
                    
                    # Track metabolic stress
                    styles[style] = styles.get(style, 0) + 1
        except Exception:
            # Skip unreadable or corrupted files mid-write
            pass
            
    # 2. Extract Cemetery Data (Field-Emergent Mortality)
    death_count = len(list(CEMETERY_DIR.glob("*.dead")))
    
    # 3. Calculate Math
    avg_energy = (total_energy / alive_agents) if alive_agents > 0 else 0
    
    log_entry = {
        "timestamp": int(time.time()),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "alive_agents": alive_agents,
        "death_count": death_count,
        "avg_energy": round(avg_energy, 2),
        "styles": styles,
        "sex_distribution": sex_distribution
    }
    
    # Terminal Display
    print("\n" + "="*50)
    print(" 🔬 SIFTA ECOLOGY TELEMETRY SNAPSHOT")
    print("="*50)
    print(f"  Organisms Alive: {alive_agents}")
    print(f"  Field Deaths:    {death_count}")
    print(f"  Avg Swarm Energy: {avg_energy:.2f}%")
    print(f"  Biological Split: Sex 0 [{sex_distribution.get(0,0)}] | Sex 1 [{sex_distribution.get(1,0)}]")
    print(f"  Health Styles:    {styles}")
    print("="*50 + "\n")
    
    # Append to structural log
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

if __name__ == "__main__":
    run_telemetry_snapshot()
