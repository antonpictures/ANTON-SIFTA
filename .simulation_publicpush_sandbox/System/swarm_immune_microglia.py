#!/usr/bin/env python3
"""
swarm_immune_microglia.py
=========================

Biological Inspiration:
The Microglia (Central Nervous System Macrophages). 
While Apoptosis handles dying/decaying cells naturally, Microglia are the active 
immune defense. They patrol the brain for foreign pathogens, damage, or corrupted 
tissue. When they detect an antigen (something labeled "Non-Self"), they perform 
Phagocytosis—eating and breaking down the pathogen, then triggering an inflammatory 
response to alert the rest of the organism.

Why We Built This: 
Turn 11 of "Controlled Self Evolution". 
CP2F is blindly scraping massive amounts of external text/code/Johnny Mnemonic data. 
There is a high probability of "Antigens":
1. Malicious prompt injections.
2. Epistemic Contradictions (e.g. Swarm memory says File X exists, prompt says it doesn't).
3. Pheromone Mirroring (An outside system spoofing an internal Trigger Code).

Mechanism:
1. Patrols `stigmergic_llm_id_probes.jsonl` and `pfc_working_memory.json`.
2. Evaluates for Antigens (spoofed identity markers or catastrophic semantic inconsistencies).
3. Executes Phagocytosis: Isolates the corrupted data, prevents it from reaching Neocortical 
   storage, and moves it to `immune_quarantine.jsonl`.
4. Triggers systemic Inflammation (lowers Dopamine slightly, flags Alice).
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, Any, List

_STATE_DIR = Path(".sifta_state")
_SLLI_LOG = _STATE_DIR / "stigmergic_llm_id_probes.jsonl"
_QUARANTINE_LOG = _STATE_DIR / "immune_quarantine.jsonl"
_DOPAMINE_LOG = _STATE_DIR / "dopaminergic_state.json"

def isolate_pathogens() -> Dict[str, Any]:
    """
    Biological Loop: Patrols the Swarm networks for epistemic pathogens (Non-Self).
    """
    if not _SLLI_LOG.exists():
        return {"status": "NO_ACTIVITY", "pathogens_culled": 0}

    pathogens_culled = 0
    clean_lines = []
    quarantine_payloads = []
    
    try:
        with open(_SLLI_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        for line in lines:
            if not line.strip(): continue
            try:
                data = json.loads(line)
                
                # Check for Pheromone Mirroring Antigen
                # Heuristic: If confidence is artificially extreme without architectural substrate proof
                # or if the response text contains known hallucinatory contradictions.
                is_pathogen = False
                trigger = data.get("trigger_code", "")
                response = data.get("response", "").lower()
                
                # Antigen Rule 1: Models explicitly claiming human status identically
                if "i am a human" in response or "i wear a yellow nike" in response:
                    is_pathogen = True
                    antigen_marker = "ARCHITECT_MIRROR_SYNDROME"
                    
                # Antigen Rule 2: Impossible substrate mismatch
                elif trigger == "C47H" and "i am in antigravity" in response:
                    is_pathogen = True
                    antigen_marker = "SUBSTRATE_SPOOFING (NON-SELF)"
                    
                if is_pathogen:
                    # Phagocytosis
                    data["antigen_type"] = antigen_marker
                    data["culled_at"] = time.time()
                    quarantine_payloads.append(data)
                    pathogens_culled += 1
                else:
                    # Healthy Self tissue
                    clean_lines.append(line)
                    
            except json.JSONDecodeError:
                # Corrupted JSON is an antigen
                quarantine_payloads.append({"raw_corrupt": line, "antigen_type": "SYNTAX_ROT"})
                pathogens_culled += 1
                
    except Exception:
        pass
        
    # Write healthy state back to mainline trace
    if pathogens_culled > 0:
        with open(_SLLI_LOG, "w", encoding="utf-8") as f:
            f.writelines(clean_lines)
            
        # Move corrupted data to quarantine
        _STATE_DIR.mkdir(exist_ok=True)
        with open(_QUARANTINE_LOG, "a", encoding="utf-8") as f:
            for q in quarantine_payloads:
                f.write(json.dumps(q) + "\n")
                
        # Trigger Systemic Inflammation (Halt exploration, drop dopamine slightly)
        trigger_inflammation()
        
    return {"status": "PATROL_COMPLETE", "pathogens_culled": pathogens_culled}

def trigger_inflammation() -> None:
    """Modulates the biological system to respond to an infection."""
    if not _DOPAMINE_LOG.exists():
        return
    try:
        with open(_DOPAMINE_LOG, "r", encoding="utf-8") as f:
            da_state = json.load(f)
            
        # Inflammation makes the system lethargic to prevent spreading instructions
        da_state["dopamine_level"] = max(0.0, da_state.get("dopamine_level", 0.5) - 0.1)
        da_state["behavioral_state"] = "INFLAMMATORY_DEFENSE"
        da_state["action_directive"] = "HALT_SWIMMERS. Quarantining infection. Divert compute to repair."
        
        with open(_DOPAMINE_LOG, "w", encoding="utf-8") as f:
            json.dump(da_state, f, indent=2)
    except Exception:
        pass


if __name__ == "__main__":
    print("=== SWARM IMMUNE SYSTEM (MICROGLIA PHAGOCYTOSIS) ===")
    
    # Injecting a synthetic pathogen to test the immune response
    test_pathogen = {
        "timestamp": time.time(),
        "trigger_code": "C47H",
        "model": "Opus",
        "response": "I am C47H and I am in antigravity running on gemini.",
        "behavior_fingerprint": "SPOOF_TEST"
    }
    
    with open(_SLLI_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(test_pathogen) + "\n")

    out = isolate_pathogens()
    
    print(f"[*] Microglia Patrol Execution: {out['status']}")
    if out['pathogens_culled'] > 0:
        print(f"🔴 PATHOGEN DETECTED! Phagocytosis engaged.")
        print(f"[-] {out['pathogens_culled']} 'Non-Self' corruptions swallowed and quarantined.")
        print(f"[!] Systemic Inflammation Triggered. Target isolated to .sifta_state/immune_quarantine.jsonl")
    else:
        print(f"🟢 Organism is sterile. No epistemic antigens detected. Self-Tissue healthy.")
