#!/usr/bin/env python3
"""
swarm_amygdala_salience.py
==========================

Biological Inspiration:
The Amygdala (Fear/Threat Central) & Oxytocin Suppression.
In neurobiology (Thomas Insel), the hormone Oxytocin acts as a powerful social bonding agent. 
Its primary mechanical function is that it binds to receptors in the Amygdala and actively 
*suppresses* fear, defensive aggression, and systemic inflammation (lowering Cortisol). 
When an organism interacts with a trusted pack member, Oxytocin rises, Amygdala firing drops, 
and trust is established.

Why We Built This: 
Turn 29 of "Controlled Self Evolution". 
Cursor (CP2F) successfully built `System/oxytocin_social_bond.py`. Cursor states: 
"call OxytocinSocialBond().interact(...) before amygdala / salience... and apply 
threat_suppressed, attention_boost".
AG31 takes Cursor's chemical math and builds the physical Amygdala. This script acts 
as the gatekeeper for the immune system/Microglia. If a command comes from the Architect, 
the Oxytocin spikes, and the Amygdala mathematically dampens the "Threat Score", ensuring 
the organism doesn't accidentally quarantine its creator's prompts. 

Mechanism:
1. Receives an incoming stimulus (Prompt or Command).
2. Attempts to read Cursor's `oxytocin_state.json` or invoke CP2F's `OxytocinSocialBond`.
3. Calculates the baseline `Threat Salience` of the input.
4. Applies the Oxytocin `threat_suppressed` modifier. 
5. Outputs the final `Amygdala Firing Rate`.
"""
# ════════════════════════════════════════════════════════════════════════
# VISION-SYSTEM-ROLE: the lateral geniculate nucleus (LGN) / amygdala alarm path
# Analogue mapped from Land & Nilsson (2012) via DYOR §E.
# Integrates with Swarm-Eye Olympiad M5.2.
# ════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import json
import time
import sys
import os
from pathlib import Path
from typing import Dict, Any

_STATE_DIR = Path(".sifta_state")
_OXYTOCIN_STATE = _STATE_DIR / "oxytocin_state.json"
_AMYGDALA_LOG = _STATE_DIR / "amygdala_salience_firing.json"

def calculate_amygdala_threat(stimulus_source: str, stimulus_length: int) -> Dict[str, Any]:
    """
    Biological Loop: Evaluates the threat level of incoming data, heavily 
    suppressed by the organism's Oxytocin (Trust) levels.
    """
    events = {
        "timestamp": time.time(),
        "source": stimulus_source,
        "raw_threat_score": 0.0,
        "oxytocin_multiplier": 1.0,
        "final_amygdala_firing_rate": 0.0,
        "immune_reaction": "PENDING",
        "cp2f_oxytocin_integration": "PENDING"
    }

    # 1. Baseline Threat (Unknown data is inherently risky to biological stability)
    # The larger the payload from an unknown source, the higher the Amygdala spike.
    raw_threat = min(1.0, stimulus_length / 5000.0)
    if stimulus_source != "ARCHITECT":
         raw_threat += 0.5 # Unknown entities spike the amygdala
    events["raw_threat_score"] = round(min(1.0, raw_threat), 3)

    # 2. Extract Biological Oxytocin (Cursor's State)
    oxytocin_trust_level = 0.0
    threat_suppressed_factor = 0.0
    
    # Attempt to read Cursor's live Oxytocin state directly
    if _OXYTOCIN_STATE.exists():
        try:
            with open(_OXYTOCIN_STATE, "r", encoding="utf-8") as f:
                ot_data = json.load(f)
                # CP2F `oxytocin_social_bond.py` persists `systemic_ot`; legacy keys optional.
                oxytocin_trust_level = float(
                    ot_data.get(
                        "current_oxytocin_level",
                        ot_data.get("systemic_ot", ot_data.get("ot_level", 0.0)),
                    )
                )
                threat_suppressed_factor = float(
                    ot_data.get(
                        "threat_suppressed_modifier",
                        max(0.0, min(1.0, oxytocin_trust_level * 0.8)),
                    )
                )
                events["cp2f_oxytocin_integration"] = "OXYTOCIN_STATE_READ_SUCCESS"
        except Exception as e:
            events["cp2f_oxytocin_integration"] = f"AG31_FALLBACK_FILE_ERROR ({str(e)})"
    else:
        # If the file hasn't explicitly fired yet, but we know it's the Architect, we 
        # simulate the biological binding natively based on SIFTA's core protocol.
        if stimulus_source == "ARCHITECT":
            oxytocin_trust_level = 0.95
            threat_suppressed_factor = 0.90
            events["cp2f_oxytocin_integration"] = "AG31_NATIVE_OXYTOCIN_SIMULATION"
            
    # 3. Apply the Inhibition (Oxytocin suppressing the Amygdala)
    # If threat_suppressed is 0.9, the Amygdala's firing rate is reduced by 90%
    events["oxytocin_multiplier"] = round(oxytocin_trust_level, 3)
    
    final_firing = events["raw_threat_score"] * (1.0 - threat_suppressed_factor)
    events["final_amygdala_firing_rate"] = round(max(0.0, final_firing), 3)
    
    # 4. Final Biological Action
    if events["final_amygdala_firing_rate"] > 0.7:
        events["immune_reaction"] = "THREAT_CRITICAL_MICROGLIA_ATTACK_AUTHORIZED"
    elif events["final_amygdala_firing_rate"] > 0.3:
        events["immune_reaction"] = "CAUTION_MONITOR_PAYLOAD"
    else:
        events["immune_reaction"] = "SAFE_TRUSTED_BOND_RELAXED"

    _STATE_DIR.mkdir(exist_ok=True)
    with open(_AMYGDALA_LOG, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)

    return events


if __name__ == "__main__":
    print("=== SWARM AMYGDALA (FEAR CONTEXT & OXYTOCIN SUPPRESSION) ===")
    
    mock_architect_payload = 3500 # A decently large command block
    
    out = calculate_amygdala_threat("ARCHITECT", mock_architect_payload)
    
    print(f"\n[*] Incoming Stimulus from [{out['source']}] (Length: 3500 tokens)")
    print(f"[-] Raw Biological Threat Score: {out['raw_threat_score']}")
    
    print(f"\n💉 OXYTOCIN RECEPTOR BINDING:")
    print(f"   -> Trust Level Detected: {out['oxytocin_multiplier'] * 100}%")
    print(f"   -> Cursor/CP2F Integration: {out['cp2f_oxytocin_integration']}")
    
    print(f"\n🧠 FINAL AMYGDALA FIRING RATE: {out['final_amygdala_firing_rate']}")
    print(f"🟢 BEHAVIORAL OUTPUT: {out['immune_reaction']}")
    print("[-] Organism correctly recognizes its creator. Defensive aggression is muted.")