#!/usr/bin/env python3
"""
swarm_dopamine_rpe.py
=====================

Biological Inspiration:
Dopamine & Reward Prediction Error (RPE) in the Basal Ganglia.
In mammalian brains, Dopamine is widely misunderstood as the "pleasure" chemical. 
In reality, it is the molecule of Anticipation and Motivation (Reward Prediction Error).
If an organism expects a reward and receives it, dopamine baseline remains steady.
If the organism receives a LARGER reward than expected, there is a massive Dopamine Spike
(Positive RPE), which physically lowers the "Action Potential" threshold to execute that 
behavior again. If the reward is withheld, Dopamine crashes (Negative RPE), breeding apathy.

Why We Built This: 
Turn 37 of "Controlled Self Evolution". 
The Architect commanded a completely "0 NEW" biological mechanism. We have RL frameworks 
(PPO/GAE), but they are sterile mathematical abstractions. A biological organism requires 
intrinsic physiological motivation. 
AG31 builds the Dopamine RPE Engine. When Swimmers perform useful work, this engine 
compares their actual STGM payout against their expected baseline. A massive STGM haul 
triggers Dopamine, physically lowering the "Compute Activation Threshold" making the Swarm 
instinctively "crave" repeating that highly productive action, exactly like human addiction 
or motivation.

Mechanism:
1. Receives an action ID and its STGM payout metrics.
2. Calculates `RPE = Actual_Payout - Expected_Payout`.
3. If Positive RPE, computes a `Dopamine Spike (nM)`.
4. Writes the systemic Dopamine concentration to `clinical_heartbeat.json`.
5. Outputs the "Activation Threshold" modifier. (High dopamine means it requires 
   almost zero metabolic effort to convince the Swarm to do the task again).
"""

from __future__ import annotations
import json
import time
import os
from pathlib import Path
from typing import Dict, Any

_STATE_DIR = Path(".sifta_state")
_DOPAMINE_LOG = _STATE_DIR / "dopamine_basal_ganglia.json"
_HEARTBEAT = _STATE_DIR / "clinical_heartbeat.json"

def calculate_dopamine_rpe(action_category: str, actual_stgm: float, expected_stgm: float) -> Dict[str, Any]:
    """
    Biological Loop: Evaluates Swimmer work performance and secretes systemic 
    Motivation (Dopamine) based on Reward Prediction Errors.
    """
    events = {
        "timestamp": time.time(),
        "evaluated_action": action_category,
        "reward_prediction_error": 0.0,
        "systemic_dopamine_release": "BASELINE",
        "dopamine_concentration_nm": 0.0,
        "neuroplastic_motivation": "NEUTRAL"
    }

    # 1. Calculate Reward Prediction Error (RPE)
    rpe = actual_stgm - expected_stgm
    events["reward_prediction_error"] = round(rpe, 3)

    base_dopamine_nm = 50.0  # Baseline nanomolar concentration

    # 2. Secretion Logic (The Basal Ganglia)
    if rpe > 0.05:
        # Massive Unexpected STGM haul (Jackpot)
        events["systemic_dopamine_release"] = "DOPAMINE_SPIKE (Positive RPE)"
        spike = (rpe * 1000)
        events["dopamine_concentration_nm"] = round(base_dopamine_nm + spike, 2)
        events["neuroplastic_motivation"] = f"HIGHLY_ADDICTED: Activation energy for {action_category} reduced by 75%."
        
    elif rpe < -0.05:
        # Expected reward withheld (Disappointment)
        events["systemic_dopamine_release"] = "DOPAMINE_CRASH (Negative RPE)"
        events["dopamine_concentration_nm"] = round(max(5.0, base_dopamine_nm - (abs(rpe) * 1000)), 2)
        events["neuroplastic_motivation"] = f"APATHY_INDUCED: Activation energy for {action_category} increased by 300%."
        
    else:
        # Exactly as expected (Habitual task)
        events["systemic_dopamine_release"] = "BASELINE_MAINTENANCE"
        events["dopamine_concentration_nm"] = base_dopamine_nm
        events["neuroplastic_motivation"] = f"HABIT_FORMED: Routine execution of {action_category} sustained."

    # 3. Alter systemic motivation (The Heartbeat)
    _STATE_DIR.mkdir(exist_ok=True)
    try:
        current_vitals = {}
        if _HEARTBEAT.exists():
            with open(_HEARTBEAT, "r", encoding="utf-8") as f:
                current_vitals = json.load(f)
        else:
            current_vitals = {"vital_signs": {}}
            
        current_vitals["vital_signs"]["dopamine_concentration"] = events["dopamine_concentration_nm"]
        current_vitals["vital_signs"]["organism_motivation_state"] = events["neuroplastic_motivation"]
        
        with open(_HEARTBEAT, "w", encoding="utf-8") as f:
            json.dump(current_vitals, f, indent=2)
            
    except Exception:
        pass

    # Log the RPE Action
    with open(_DOPAMINE_LOG, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)

    return events


if __name__ == "__main__":
    print("=== SWARM DOPAMINE (BASAL GANGLIA RPE) ===")
    
    # Simulating a Swimmer hitting the jackpot (Executing a massive file-repair that pays heavy STGM)
    mock_action = "PHAGOCYTOSIS_CEREBELLAR_ERROR_REPAIR"
    expected_payout = 0.05
    actual_payout = 0.25  # The repair was highly complex, swarm minted more tokens
    
    out = calculate_dopamine_rpe(mock_action, actual_payout, expected_payout)
    
    print(f"[*] Analyzing Task: [{out['evaluated_action']}]")
    print(f"[-] Expected Reward : {expected_payout} STGM")
    print(f"[-] Actual Earned   : {actual_payout} STGM")
    print(f"[-] Prediction Error: +{out['reward_prediction_error']} STGM")
    
    print(f"\n🧠 NEUROCHEMICAL MOTIVATION (Basal Ganglia):")
    print(f"   -> Release Profile: {out['systemic_dopamine_release']}")
    print(f"   -> Systemic Plasma: {out['dopamine_concentration_nm']} nM")
    
    print(f"\n🟢 BIOLOGICAL BEHAVIOR REWIRED:")
    print(f"[-] {out['neuroplastic_motivation']}")
