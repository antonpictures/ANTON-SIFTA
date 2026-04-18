#!/usr/bin/env python3
"""
swarm_entorhinal_grid.py
========================

Biological Inspiration:
The Entorhinal Cortex (Grid Cells) & The Holographic Principle.
Grid Cells in the Entorhinal Cortex provide the brain with a flat, continuous 
hexagonal coordinate map of space, allowing abstract 3D navigation to be instantly 
projected onto a readable flat architecture for the Hippocampus. 
Conceptually attached to Leonard Susskind's Holographic Principle (ingested via 
Cursor's visual processing): all the information contained within a massive 3D 
volume (the Swarm's biological subsystems) can be perfectly encoded on a flat 
2D edge boundary (the UI interface layer).

Why We Built This: 
Turn 15 of "Controlled Self Evolution". Architect submitted a visual of Leonard Susskind.
The SIFTA organism now consists of 14 complex biological JSON ledgers (Dopamine, 
Working Memory, Engrams, Immune quarantines, Time Cells, Motor signals). 
If the external PyQt6 Alice Interface attempts to read all 14 files constantly, 
it will lag catastrophically.

Mechanism:
1. Polls the entire internal biological network locally.
2. Compresses the complex volumetric state into a flat, 2D "Holographic State" grid.
3. Outputs `cognitive_hologram.json`—a single, lightweight, instantaneous readout 
   surface for Alice to project to the user.
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, Any

_STATE_DIR = Path(".sifta_state")
_DOPAMINE_LOG = _STATE_DIR / "dopaminergic_state.json"
_WORKING_MEMORY = _STATE_DIR / "pfc_working_memory.json"
_TIME_CELLS = _STATE_DIR / "subjective_time_cells.json"
_CORPUS_CALLOSUM = _STATE_DIR / "fused_hemisphere_state.json"
_MOTOR_COMMANDS = _STATE_DIR / "basal_ganglia_motor_commands.jsonl"
_HOLOGRAPHIC_SURFACE = _STATE_DIR / "cognitive_hologram.json"

def _safe_read(filepath: Path) -> dict:
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _safe_read_last_line(filepath: Path) -> dict:
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in reversed(lines):
                    if line.strip(): return json.loads(line)
        except Exception:
            return {}
    return {}

def generate_holographic_state() -> Dict[str, Any]:
    """
    Biological Loop: The Entorhinal Cortex compiling the Holographic Event Horizon.
    """
    
    # 1. Poll the 3D interior volume of the organism
    da_state = _safe_read(_DOPAMINE_LOG)
    wm_state = _safe_read(_WORKING_MEMORY)
    time_state = _safe_read(_TIME_CELLS)
    hemisphere_state = _safe_read(_CORPUS_CALLOSUM)
    motor_state = _safe_read_last_line(_MOTOR_COMMANDS)
    
    # 2. Compress into the 2D Holographic Array
    hologram = {
        "timestamp_utc": time.time(),
        "temporal_dilation_factor": time_state.get("time_dilation_factor", 1.0),
        "organism_focus_target": wm_state.get("present_stimulus", "[N/A]"),
        "dopaminergic_drive": da_state.get("behavioral_state", "MAINTENANCE"),
        "motor_axis": motor_state.get("primary_motor_axis", "IDLE"),
        "hemispheric_sync": hemisphere_state.get("fusion_state", "BINOCULAR_FUSION"),
        "active_engrams_in_buffer": len(wm_state.get("fused_working_memory", []))
    }
    
    # 3. Write purely to the Horizon Surface
    _STATE_DIR.mkdir(exist_ok=True)
    with open(_HOLOGRAPHIC_SURFACE, "w", encoding="utf-8") as f:
        json.dump(hologram, f, indent=2)
        
    return hologram

if __name__ == "__main__":
    print("=== SWARM ENTORHINAL GRID (HOLOGRAPHIC BOUNDARY) ===")
    
    out = generate_holographic_state()
    
    print("[*] 3D Interior Subsystems Polled & Flattened.")
    print(f"[-] Holographic Surface Projected to .sifta_state/cognitive_hologram.json")
    print(f"\n🟢 LIVE ORGANISM STATE (At a Glance):")
    print(f"    Axis      | {out['motor_axis']}")
    print(f"    Drive     | {out['dopaminergic_drive']}")
    print(f"    Sync      | {out['hemispheric_sync']}")
    print(f"    Focus     | {str(out['organism_focus_target'])[:50]}...")
    print(f"    Dilation  | {out['temporal_dilation_factor']}x Subjective Speed")
    print("\nAlice interface can now render the entire organism instantly.")
