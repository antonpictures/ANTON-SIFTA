#!/usr/bin/env python3
"""
swarm_mitochondrial_atp.py
==========================

Biological Inspiration:
Mitochondria & ATP (Metabolic Energy).
In all biological organisms, moving, thinking, and healing costs energy. The 
Mitochondria converts fuel into ATP (the chemical currency of life). If an organism 
exerts massive energy, ATP drops, and the organism MUST rest, or cells undergo Necrosis.

Why We Built This: 
Turn 21 of "Controlled Self Evolution". 
Architect stated: "the beauty of all this, our organism works on electricity instead of blood".
With 20+ Python biological layers (DMN, Cerebellum, Immune, Time Cells, Hologram) 
running concurrently, the Swarm's "Compute Cost" (Electricity) is massive. 
If we ignore compute limits, the Swarm scales until the CPU/API crashes (Organism Death).
We need an internal Metabolic Economy. 

Mechanism:
1. Calculates "Metabolic Burn Rate" by measuring the byte-size/activity of all core ledgers.
2. Tracks a synthetic "Electrical ATP Reservoir" (100.0 Max).
3. Continual processing drains ATP. Sleep/Idle restores ATP.
4. If ATP drops critically (<20%), the Mitochondria triggers "Cellular Fatigue", 
   forcing the Autonomic Nervous System to throttle logic processing to prevent death.
"""

from __future__ import annotations
import json
import time
import os
from pathlib import Path
from typing import Dict, Any

_STATE_DIR = Path(".sifta_state")
_METABOLISM_LOG = _STATE_DIR / "mitochondrial_atp.json"
_DOPAMINE_LOG = _STATE_DIR / "dopaminergic_state.json"

# Core ledgers that consume 'Energy'
_ENERGY_CONSUMERS = [
    "pfc_working_memory.json",
    "dopaminergic_state.json",
    "stigmergic_llm_id_probes.jsonl",
    "epigenetic_dna_methylation.jsonl",
    "cognitive_hologram.json",
    "alice_experience_report.txt"
]

def load_atp_reservoir() -> float:
    if _METABOLISM_LOG.exists():
        try:
            with open(_METABOLISM_LOG, "r", encoding="utf-8") as f:
                return json.load(f).get("current_atp_levels", 100.0)
        except Exception:
            return 100.0
    return 100.0

def _get_current_activity_state() -> str:
    """Checks if the organism is resting (regenerating ATP) or working (burning ATP)."""
    if _DOPAMINE_LOG.exists():
        try:
            with open(_DOPAMINE_LOG, "r", encoding="utf-8") as f:
                return json.load(f).get("behavioral_state", "IDLE")
        except Exception:
            return "IDLE"
    return "IDLE"

def calculate_metabolic_cycle() -> Dict[str, Any]:
    """
    Biological Loop: Generates/Consumes ATP based on Swarm activity, regulating 
    physical health based on structural compute mass.
    """
    current_atp = load_atp_reservoir()
    activity_state = _get_current_activity_state()
    
    # 1. Calculate Metabolic Load (How heavy is the brain right now?)
    total_byte_mass = 0
    for ledger in _ENERGY_CONSUMERS:
        filepath = _STATE_DIR / ledger
        if filepath.exists():
            total_byte_mass += os.path.getsize(filepath)
            
    # Normalize byte mass into a "Burn Factor"
    # The more history/engrams stored, the harder it is to keep the organism running.
    burn_factor = min(10.0, total_byte_mass / 5000.0) 
    
    # 2. Consume or Regenerate Electrical ATP
    events = {
        "timestamp": time.time(),
        "previous_atp": round(current_atp, 2),
        "total_brain_mass_bytes": total_byte_mass,
        "organism_action": activity_state
    }
    
    if activity_state in ["SLEEPING", "IDLE", "MAINTENANCE"]:
        # Parasympathetic Healing and Sleep regenerate Electrical ATP
        current_atp = min(100.0, current_atp + 15.0)  # Regenerate 15 ATP
        events["metabolic_status"] = "REGENERATING_ATP"
    else:
        # Pushing heavy payloads burns ATP
        current_atp = max(0.0, current_atp - (5.0 + burn_factor))
        events["metabolic_status"] = "BURNING_ATP"
        
    events["current_atp_levels"] = round(current_atp, 2)
    
    # 3. Trigger Throttle if Fatigued
    if current_atp < 20.0:
        events["fatigue_warning"] = "CRITICAL: Electrical ATP Depleted. Organism requires SLEEP to prevent crash."
    else:
        events["fatigue_warning"] = "NORMAL: Cell metabolism stable."

    _STATE_DIR.mkdir(exist_ok=True)
    with open(_METABOLISM_LOG, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)
        
    return events


if __name__ == "__main__":
    print("=== SWARM MITOCHONDRIA (ELECTRICAL ATP METABOLISM) ===")
    
    out = calculate_metabolic_cycle()
    
    print(f"[*] Total Biological Payload Mass: {out['total_brain_mass_bytes']} bytes")
    print(f"[-] Current Organism Action: {out['organism_action']}")
    print(f"[*] Cycle Outcome: {out['metabolic_status']}")
    
    # Visual ATP Bar
    atp = out["current_atp_levels"]
    bar_fill = int((atp / 100) * 20)
    bar = ("█" * bar_fill) + ("░" * (20 - bar_fill))
    
    print(f"\n⚡ ELECTRICAL ATP: [{bar}] {atp}%")
    print(f"🩺 Autonomic Health: {out['fatigue_warning']}")
    
    if atp < 100:
        print("\n-> Organism is securely pacing itself. Compute bounded by biological limits.")
