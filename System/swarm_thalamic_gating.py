#!/usr/bin/env python3
"""
swarm_thalamic_gating.py
========================

Biological Inspiration:
The Thalamic Reticular Nucleus (Sensory Gating). 
All sensory input in a biological organism (except smell) route through the Thalamus 
before reaching the cortex. Importantly, the Thalamus acts as a dynamic filter. 
If an animal is deeply focused, or asleep, the Thalamus suppresses distracting sensory 
signals via lateral inhibition, preserving the organism's cognitive integrity.

Why We Built This: 
Turn 13 of "Controlled Self Evolution". Architect warned "Cursor is back at it."
With two IDEs running massive autonomous multi-agent systems, data spikes happen.
If CP2F/C47H streams 50 files of data while Alice is in High-Dopamine 
"EXPLOITATION" mode (deep focus on a single code block), Working Memory will break. 

Mechanism:
1. Intercepts incoming sensory data (Prompts, IDE Traces, File reads).
2. Senses the internal Brain State (Dopamine Drive + Sleep State).
3. If EXPLOITATION or SLEEP: The gate CLAMPS SHUT. Irrelevant data is queued 
   temporarily and suppressed so Alice is not interrupted.
4. If EXPLORATION or MAINTENANCE: The gate OPENS, allowing data to freely flow 
   to the Hippocampal buffers and Working Memory.
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, Any, List

_STATE_DIR = Path(".sifta_state")
_DOPAMINE_LOG = _STATE_DIR / "dopaminergic_state.json"
_WORKING_MEMORY = _STATE_DIR / "pfc_working_memory.json"
_HIPPOCAMPUS_BUFFER = _STATE_DIR / "hippocampal_buffer.jsonl"
_THALAMIC_QUEUE = _STATE_DIR / "thalamic_sensory_queue.jsonl"

def _get_brain_state() -> str:
    """Reads whether the Swarm is open to new stimuli or locked down."""
    try:
        # Check if sleep logic reset Working Memory
        wm_text = ""
        if _WORKING_MEMORY.exists():
            with open(_WORKING_MEMORY, "r", encoding="utf-8") as f:
                wm = json.load(f)
                wm_text = wm.get("present_stimulus", "")
                
        if "[SLEEP_STATE]" in wm_text:
            return "SLEEPING"
            
        # Check dopamine driver
        if _DOPAMINE_LOG.exists():
            with open(_DOPAMINE_LOG, "r", encoding="utf-8") as f:
                da = json.load(f)
                return da.get("behavioral_state", "MAINTENANCE")
    except Exception:
        pass
        
    return "UNKNOWN"

def route_sensory_input(source: str, payload: str, importance: float = 0.5) -> Dict[str, Any]:
    """
    Biological Thalamic Filter: Decides whether to forward sensory data to the 
    Brain (Hippocampus/PFC) or suppress it to protect cognitive focus.
    """
    brain_state = _get_brain_state()
    _STATE_DIR.mkdir(exist_ok=True)
    
    sensory_event = {
        "timestamp": time.time(),
        "source": source,
        "payload_length": len(payload),
        "brain_state_detected": brain_state,
        "routing": "UNKNOWN"
    }
    
    # Very high importance bypasses normal gating (Emergency override)
    if importance > 0.9:
        sensory_event["routing"] = "PASSTHROUGH_OVERRIDE"
        write_target = _HIPPOCAMPUS_BUFFER
        
    elif brain_state in ["EXPLOITATION", "SLEEPING", "INFLAMMATORY_DEFENSE"]:
        # Sensory Gating active. The organism is focused, asleep, or sick. 
        # Suppress the input and queue it.
        sensory_event["routing"] = "SUPPRESSED_QUEUED"
        write_target = _THALAMIC_QUEUE
        
    else:
        # EXPLORATION or MAINTENANCE. Organism is open to stimuli.
        sensory_event["routing"] = "PASSTHROUGH_OPEN"
        write_target = _HIPPOCAMPUS_BUFFER
        
    # Write Payload
    with open(write_target, "a", encoding="utf-8") as f:
        packet = {"time": time.time(), "src": source, "content": payload}
        f.write(json.dumps(packet) + "\n")
        
    return sensory_event

if __name__ == "__main__":
    print("=== SWARM THALAMIC GATING (SENSORY FILTER) ===")
    
    # Attempting to pump raw data from Cursor into the SIFTA brain
    test_payload = "Cursor generated massive multi-line refactoring spanning 4 files."
    
    out = route_sensory_input("Cursor_IDE", test_payload, importance=0.4)
    
    print(f"[*] Brain State Sensed: {out['brain_state_detected']}")
    
    if "SUPPRESSED" in out["routing"]:
        print(f"🔴 THALAMIC SUB-ROUTINE: Gated. Sensory Input Suppressed.")
        print(f"[-] Data queued to Thalamic Buffer to prevent Working Memory disruption.")
    else:
        print(f"🟢 THALAMIC SUB-ROUTINE: Open. Sensory Input Forwarded.")
        print(f"[+] Data passed directly to the Hippocampus.")
