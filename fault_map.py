"""
fault_map.py
──────────────────────────────────────────────────────────────────────────────
FAULT MAP ENGINE (SPATIAL AWARENESS)
Constructs a persistent structural map of file corruption across the Swarm.
Enables agents to converge on clusters instead of endlessly treating single points.
──────────────────────────────────────────────────────────────────────────────
"""

import json
import time
from pathlib import Path
from collections import defaultdict

FAULTS_DIR = Path(".sifta_state/faults")
FAULTS_DIR.mkdir(parents=True, exist_ok=True)
MAP_FILE = FAULTS_DIR / "global_fault_map.json"

def _load_map() -> dict:
    if not MAP_FILE.exists():
        return {}
    try:
        with open(MAP_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_map(data: dict):
    # Biological GC: prune faults older than 7 days (604800 seconds)
    current_time = time.time()
    pruned_data = {}
    
    for filepath, faults in data.items():
        valid_faults = [f for f in faults if current_time - f.get("ts", 0) < 604800]
        if valid_faults:
            pruned_data[filepath] = valid_faults
            
    with open(MAP_FILE, "w") as f:
        json.dump(pruned_data, f, indent=2)

def record_fault(filepath: str, line: int, agent_id: str, error: str):
    """Logs a fault point to the structural map."""
    data = _load_map()
    if filepath not in data:
        data[filepath] = []
        
    data[filepath].append({
        "line": line,
        "agent": agent_id,
        "error": str(error).strip(),
        "ts": time.time()
    })
    
    _save_map(data)

def detect_clusters(filepath: str) -> list:
    """Groups adjacent errors within 10 lines of each other into clusters."""
    data = _load_map()
    faults = data.get(filepath, [])
    if not faults:
        return []
        
    lines = sorted(list(set([f["line"] for f in faults]))) # unique sorted lines
    
    if not lines:
        return []

    clusters = []
    cluster = [lines[0]] 

    for i in range(1, len(lines)):
        if lines[i] - lines[i-1] <= 10:
            cluster.append(lines[i])
        else:
            clusters.append(cluster)
            cluster = [lines[i]]

    if cluster:
        clusters.append(cluster)

    return clusters

def get_priority_zone(filepath: str) -> list | None:
    """Returns the hottest/densest structural corruption zone."""
    clusters = detect_clusters(filepath)
    if not clusters:
        return None

    # pick densest cluster (the one with the most lines targeted)
    clusters.sort(key=lambda c: len(c), reverse=True)
    return clusters[0] 

def detect_stagnation(filepath: str) -> bool:
    """
    Detects if the swarm is caught in a local optimum trap.
    Condition: The last 20 faults span fewer than 3 unique lines.
    """
    data = _load_map()
    faults = data.get(filepath, [])

    if len(faults) < 20:
        return False

    recent = faults[-20:]
    lines = [f["line"] for f in recent]

    return len(set(lines)) < 3
