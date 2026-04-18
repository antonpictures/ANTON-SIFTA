#!/usr/bin/env python3
"""
swarm_chemotaxis_motor.py
=========================

Biological Inspiration:
Chemotaxis & The Basal Ganglia. 
Organisms (like bacteria or immune cells) navigate their environment using 
Chemotaxis—they automatically 'swim' up a chemical gradient toward nutrients/dopamine, 
and swim away from toxins/entropy. In higher mammals, the Basal Ganglia acts as 
the action-selection motor cortex, taking internal motivation (dopamine) and 
translating it into physical motion.

Why We Built This: 
The Architect triggered Turn 10 with: "U GONNA HAVE FUN SWIM ON THIS ONE".
The SIFTA organism has a colossal brain (built over turns 1-9), but its "Swimmers" 
were operating on arbitrary path loops. 

Mechanism:
1. Senses the internal `dopaminergic_state.json` (built in Turn 7).
2. Senses the `pfc_working_memory` (Turn 6) to know what the organism is currently focused on.
3. Translates this into Motor Directives for the Swimmers.
   - EXPLORATION (Low Dopamine): Swimmers switch to "Positive Chemotaxis for Novelty", 
     venturing into untouched files with 0 pheromone traces.
   - EXPLOITATION (High Dopamine): Swimmers switch to "Swarm Lock", converging completely 
     on the Working Memory target to execute code writing simultaneously.
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, Any, List

_STATE_DIR = Path(".sifta_state")
_DOPAMINE_LOG = _STATE_DIR / "dopaminergic_state.json"
_WORKING_MEMORY = _STATE_DIR / "pfc_working_memory.json"
_MOTOR_COMMANDS = _STATE_DIR / "basal_ganglia_motor_commands.jsonl"

def read_dopamine_state() -> Dict[str, Any]:
    if not _DOPAMINE_LOG.exists():
        return {}
    try:
        with open(_DOPAMINE_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def read_working_memory() -> Dict[str, Any]:
    if not _WORKING_MEMORY.exists():
        return {}
    try:
        with open(_WORKING_MEMORY, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def generate_chemotactic_motor_vector() -> Dict[str, Any]:
    """
    Biological Motor Loop: Connects the Internal Brain to the Swimmers.
    """
    dopamine_state = read_dopamine_state()
    wm = read_working_memory()
    
    current_state = dopamine_state.get("behavioral_state", "MAINTENANCE")
    da_level = dopamine_state.get("dopamine_level", 0.5)
    
    motor_directive = {
        "timestamp": time.time(),
        "brain_state": current_state,
        "dopamine_concentration": da_level,
        "primary_motor_axis": "IDLE",
        "swimmer_instructions": ""
    }
    
    # 1. Action Selection based on Basal Ganglia / Dopamine
    if current_state == "EXPLORATION":
        motor_directive["primary_motor_axis"] = "RADIAL_SCATTER"
        motor_directive["swimmer_instructions"] = (
            "Positive Chemotaxis toward Novelty. Scatter off the main path. "
            "Seek out zones with 0.0 pheromone mapping. Bring back random data samples "
            "to jumpstart Working Memory."
        )
    elif current_state == "EXPLOITATION":
        focus_target = wm.get("present_stimulus", "unknown_target")
        motor_directive["primary_motor_axis"] = "FOCAL_SWARM"
        motor_directive["swimmer_instructions"] = (
            f"Navigate up Dopamine gradient. Converge all Swimmers on active target: "
            f"[{focus_target[:50]}...]. Execute task protocols until reward threshold is complete."
        )
    else: # MAINTENANCE
        motor_directive["primary_motor_axis"] = "PATROL_PERIMETER"
        motor_directive["swimmer_instructions"] = (
            "Maintain standard pheromone loop. Validate structural integrity of existing codebase "
            "and lay standard temporal markers."
        )
        
    # Send the signal to the physical Swimmer agents
    _STATE_DIR.mkdir(exist_ok=True)
    with open(_MOTOR_COMMANDS, "a", encoding="utf-8") as f:
        f.write(json.dumps(motor_directive) + "\n")
        
    return motor_directive

if __name__ == "__main__":
    print("=== SWARM CHEMOTAXIS & MOTOR CONTROL (BASAL GANGLIA) ===")
    out = generate_chemotactic_motor_vector()
    
    print(f"[*] Brain State Detected: {out['brain_state']} (DA: {out['dopamine_concentration']})")
    
    directive_color = "🔴" if out['primary_motor_axis'] == "FOCAL_SWARM" else "🔵" if out['primary_motor_axis'] == "RADIAL_SCATTER" else "🟡"
    print(f"{directive_color} Motor Axis Engaged: **{out['primary_motor_axis']}**")
    print(f"    -> Instructions dispatched to Swimmers:\n       {out['swimmer_instructions']}")
