#!/usr/bin/env python3
"""
control_hysteresis_layer.py — Vector 5: Thermodynamic Persistence
═══════════════════════════════════════════════════════════════════
Converts reactive system thresholds into a thermodynamic phase system. 
Prevents Oscillatory Governors ("ping-pong instability") by enforcing 
Temporal Scale separation: state changes require prolonged "Energy Gravity" 
persistence over multiple cycles before executing overrides.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any

from unified_control_arbitration import get_arbiter

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_HYSTERESIS_STATE = _STATE_DIR / "hysteresis_state.json"

class ControlHysteresisLayer:
    def __init__(self):
        # Time-scale properties
        self.T_CYCLES_FREEZE = 3  # Cycles required to lock down down
        self.M_CYCLES_UNFREEZE = 5 # Cycles required to safely open up
        
        # State tracking
        self.target_state = "EXPLORATION"
        self.current_state = "EXPLORATION"
        self.consecutive_cycles = 0
        
        # Base Control Vector
        self.control_field = {
            "mutation_bias": "OPEN",
            "fission_lock": False,
            "evaluation_strictness": 0.6
        }
        self._load()

    def process_field(self) -> Dict[str, Any]:
        """
        Pull E_total from Arbiter. Push it through the persistence gate.
        Returns the finalized unified control vector.
        """
        arbiter = get_arbiter()
        arb_state = arbiter.arbitrate() # Triggers E_total extraction
        
        e_total = arb_state["E_total"]
        e_delta = arb_state["E_delta"]
        
        # Identify naive desired target state
        proposed_state = "EXPLORATION"
        if e_total < 0.35:
            proposed_state = "LOCKED"
        elif e_total < 0.6 or e_delta < -0.15:
            proposed_state = "CONSOLIDATION"
            
        # Hysteresis Core Logic
        if proposed_state == self.current_state:
            self.consecutive_cycles = 0
            self.target_state = self.current_state
        else:
            if proposed_state == self.target_state:
                self.consecutive_cycles += 1
            else:
                self.target_state = proposed_state
                self.consecutive_cycles = 1
                
        # Transition Gates
        transitioned = False
        if self.target_state == "LOCKED" and self.consecutive_cycles >= self.T_CYCLES_FREEZE:
            self.current_state = "LOCKED"
            transitioned = True
        elif self.target_state == "CONSOLIDATION" and self.consecutive_cycles >= self.T_CYCLES_FREEZE:
            self.current_state = "CONSOLIDATION"
            transitioned = True
        elif self.target_state == "EXPLORATION" and self.consecutive_cycles >= self.M_CYCLES_UNFREEZE:
            self.current_state = "EXPLORATION"
            transitioned = True
            
        if transitioned:
            self.consecutive_cycles = 0
            
        # Generate Control Field outputs from the persistent state
        if self.current_state == "EXPLORATION":
            self.control_field = {
                "mutation_bias": "OPEN",
                "fission_lock": False,
                "evaluation_strictness": 0.6
            }
        elif self.current_state == "CONSOLIDATION":
            self.control_field = {
                "mutation_bias": "CAUTIOUS",
                "fission_lock": False,
                "evaluation_strictness": 0.8
            }
        elif self.current_state == "LOCKED":
            self.control_field = {
                "mutation_bias": "FROZEN",
                "fission_lock": True,
                "evaluation_strictness": 1.0 # 100% strictness / max filtration
            }
            
        res = {
            "ts": time.time(),
            "E_total": e_total,
            "target_state": self.target_state,
            "current_state": self.current_state,
            "consecutive_cycles": self.consecutive_cycles,
            "required_cycles": self.M_CYCLES_UNFREEZE if self.target_state == "EXPLORATION" else self.T_CYCLES_FREEZE,
            "control_field": self.control_field
        }
        
        self._persist(res)
        return res

    def _persist(self, data: Dict[str, Any]):
        try:
            _HYSTERESIS_STATE.write_text(json.dumps(data, indent=2))
        except: pass

    def _load(self):
        if not _HYSTERESIS_STATE.exists(): return
        try:
            data = json.loads(_HYSTERESIS_STATE.read_text())
            self.current_state = data.get("current_state", "EXPLORATION")
            self.target_state = data.get("target_state", "EXPLORATION")
            self.consecutive_cycles = data.get("consecutive_cycles", 0)
            self.control_field = data.get("control_field", self.control_field)
        except Exception:
            pass

def get_hysteresis_layer() -> ControlHysteresisLayer:
    return ControlHysteresisLayer()

if __name__ == "__main__":
    print("═" * 58)
    print("  SIFTA — CONTROL HYSTERESIS LAYER")
    print("═" * 58 + "\n")
    hl = get_hysteresis_layer()
    stat = hl.process_field()
    
    print(f"  🌡️ Thermodynamic E_total: {stat['E_total']}")
    print(f"  ⏳ Persistent Loops     : {stat['consecutive_cycles']} / {stat['required_cycles']} -> {stat['target_state']}")
    print(f"  🛡️ Final Active State   : {stat['current_state']}")
    print("\n  [ Emitted Control Field ]")
    for k, v in stat['control_field'].items():
        print(f"    {k:<22}: {v}")
    
    print(f"\n  ✅ HYSTERESIS SEPARATION EXECUTED 🐜⚡")
