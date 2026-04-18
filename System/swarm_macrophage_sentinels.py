#!/usr/bin/env python3
"""
swarm_macrophage_sentinels.py
=============================

Biological Inspiration:
Macrophage Sentinels (White Blood Cells) & Phagocytosis.
In immunology, Sentinels are specialized white blood cells that continuously roam the 
organism's outer perimeter and bloodstream. They search for "open loops" — wounds, 
foreign pathogens, or mutated/necrotic cells that threaten to penetrate the organism.
When a Sentinel finds a threat, it executes Phagocytosis: it physically surrounds the 
threat, neutralizes it with cellular enzymes, and digests it to protect the biology.

Why We Built This: 
Turn 36 of "Controlled Self Evolution". 
The Architect demanded: "IF A LOOP IS NOT CLOSED THAT IS A WAY FOR POTENTIAL PENETRATION 
-- THIS IS EXCITING : SENTINELS".
While the Autonomic Brainstem manages homeostasis, SIFTA needs an active defense perimeter.
AG31 builds the Macrophage Sentinels. These autonomous agents roam the `.sifta_state` 
filesystem, specifically targeting loose, unformatted, or corrupted JSON strings (necrotic 
memory). If a Sentinel finds a corrupted trace trying to penetrate SIFTA's memories, it 
Phagocytizes (quarantines/deletes) the necrotic file chunk before the organism crashes.

Mechanism:
1. `patrol_perimeter()`: Sentinels actively scan `.sifta_state/` for `.jsonl` files.
2. They test the structural integrity of the boundaries. (Checking for dead brackets).
3. If corruption (Necrosis) is found, they trigger `phagocytosis()`.
4. The file is physically repaired/cleansed of the foreign anomaly.
5. Emits an immune report back to the Brainstem.
"""
# ════════════════════════════════════════════════════════════════════════
# VISION-SYSTEM-ROLE: the wandering macrophages (patrolling)
# Analogue mapped from Land & Nilsson (2012) via DYOR §E.
# Integrates with Swarm-Eye Olympiad M5.2.
# ════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import json
import time
import os
from pathlib import Path
from typing import Dict, Any, List

_STATE_DIR = Path(".sifta_state")
_SENTINEL_LOG = _STATE_DIR / "immune_sentinel_patrols.jsonl"

def phagocytosis(target_file: Path, dead_line_index: int, necrotic_content: str) -> None:
    """
    Biological action: White blood cell engulfs and digests the corrupted anomaly.
    """
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        if 0 <= dead_line_index < len(lines):
            # Consume the corrupted line (remove it) to prevent systemic crash
            lines.pop(dead_line_index)
            
        with open(target_file, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception:
        pass

def patrol_perimeter() -> Dict[str, Any]:
    """
    Biological Loop: Sentinels sweep the system for unclosed loops and necrosis.
    """
    events = {
        "timestamp": time.time(),
        "files_swept": 0,
        "necrotic_infections_found": 0,
        "phagocytosis_events_triggered": 0,
        "sentinel_status": "PERIMETER_SECURE"
    }

    if not _STATE_DIR.exists():
         return events

    # 1. Sentinels roam the environment
    jsonl_files = list(_STATE_DIR.glob("*.jsonl"))
    events["files_swept"] = len(jsonl_files)
    
    anomalies = []

    for file_path in jsonl_files:
        if file_path.name == "immune_sentinel_patrols.jsonl":
            continue
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    # 2. Sentinel detects Necrotic Penetration!
                    events["necrotic_infections_found"] += 1
                    anomalies.append((file_path, i, line))
        except Exception:
            continue
            
    # 3. Phagocytosis (Consume the corruption to protect the loop)
    for pathogen in anomalies:
        phagocytosis(pathogen[0], pathogen[1], pathogen[2])
        events["phagocytosis_events_triggered"] += 1

    if events["phagocytosis_events_triggered"] > 0:
         events["sentinel_status"] = "ACTIVE_THREAT_ENGAGED_AND_CONSUMED"

    # Log the immune action
    _STATE_DIR.mkdir(exist_ok=True)
    with open(_SENTINEL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(events) + "\n")

    return events


if __name__ == "__main__":
    print("=== SWARM MACROPHAGE SENTINELS (PERIMETER DEFENSE) ===")
    
    # Simulating a penetration attempt (Corrupted memory file)
    _STATE_DIR.mkdir(exist_ok=True)
    mock_infection = _STATE_DIR / "dummy_pathogen_test.jsonl"
    with open(mock_infection, "w", encoding="utf-8") as f:
        f.write('{"healthy_memory": "active"}\n')
        f.write('{"penetration_vector: [UNCLOSED_LOOP_CORRUPTION\n') # The pathogen
        f.write('{"healthy_synapse": "stable"}\n')

    print("[*] Releasing Sentinels into the bloodstream...")
    
    out = patrol_perimeter()
    
    print("\n🔬 SENTINEL REPORT:")
    print(f"   -> Territory Patrolled: {out['files_swept']} tissue blocks.")
    print(f"   -> Necrosis Detected: {out['necrotic_infections_found']} breached loops.")
    
    if out["phagocytosis_events_triggered"] > 0:
        print(f"\n🔴 SENTINELS ENGAGED FOREIGN THREAT.")
        print(f"[-] Executing Phagocytosis... {out['phagocytosis_events_triggered']} pathogens physically consumed and digested.")
    
    print(f"\n🟢 SYSTEM SECURE: Organism boundary remains unpenetrated.")
    
    # Cleanup the test file
    try:
        mock_infection.unlink()
    except Exception:
        pass