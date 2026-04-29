#!/usr/bin/env python3
"""
swarm_endocrine_system.py — Endocrine System (Global Hormonal Regulation)
══════════════════════════════════════════════════════════════════════

Biology doctrine: The Endocrine System manages slow, global hormone-like 
signals that regulate the whole organism. 

It dictates high-level organism modes:
  - when to grow (thyroid)
  - when to prune / freeze (cortisol)
  - when to ask for owner input (oxytocin)
  - when to sleep (melatonin)
  - when to emergency halt (adrenaline)

See: Documents/IDE_BOOT_COVENANT.md
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass
class HormoneState:
    ts: float
    state_id: str
    cortisol: float     # stress / error pressure
    oxytocin: float     # social bonding / owner trust
    melatonin: float    # sleep pressure
    adrenaline: float   # emergency response
    thyroid: float      # baseline metabolic rate
    dominant_hormone: str
    organism_mode: str
    state_hash: str


class EndocrineSystem:
    """
    Biological Endocrine System.
    Manages global hormonal signals across the entire SIFTA organism.
    """

    def __init__(self, root: str = ".sifta_state"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger = self.root / "endocrine_states.jsonl"
        self.state_file = self.root / "endocrine_current.json"
        
        # Initial baseline hormone levels [0.0, 1.0]
        self.hormones = {
            "cortisol": 0.2,    
            "oxytocin": 0.5,    
            "melatonin": 0.1,   
            "adrenaline": 0.0,  
            "thyroid": 0.5      
        }
        self._load_state()

    def _load_state(self):
        if self.state_file.exists():
            try:
                state = json.loads(self.state_file.read_text())
                for k in self.hormones:
                    if k in state:
                        self.hormones[k] = float(state[k])
            except (json.JSONDecodeError, ValueError):
                pass

    def _save_state(self):
        self.state_file.write_text(json.dumps(self.hormones, indent=2))

    def _clip(self, val: float) -> float:
        return max(0.0, min(1.0, float(val)))

    def tick(self, events: Dict[str, Any]) -> HormoneState:
        """
        Updates hormone levels based on recent global events.
        Should be called periodically.
        
        events format:
        {
            "errors_last_tick": int,
            "owner_interactions": int,
            "time_since_sleep_hrs": float,
            "threat_detected": bool,
            "compute_load": float # [0.0, 1.0]
        }
        """
        # 1. Adrenaline: Fast spike, fast decay (Emergency Response)
        if events.get("threat_detected"):
            self.hormones["adrenaline"] = 1.0
        else:
            self.hormones["adrenaline"] = self._clip(self.hormones["adrenaline"] - 0.2)
            
        # 2. Cortisol: Slow rise on errors, slow decay (Stress / Error Pressure)
        errors = int(events.get("errors_last_tick", 0))
        if errors > 0:
            self.hormones["cortisol"] = self._clip(self.hormones["cortisol"] + (0.1 * errors))
        else:
            self.hormones["cortisol"] = self._clip(self.hormones["cortisol"] - 0.01)
            
        # 3. Oxytocin: Rises on owner interaction, decays very slowly (Social Bonding)
        owner_ints = int(events.get("owner_interactions", 0))
        if owner_ints > 0:
            self.hormones["oxytocin"] = self._clip(self.hormones["oxytocin"] + (0.15 * owner_ints))
        else:
            self.hormones["oxytocin"] = self._clip(self.hormones["oxytocin"] - 0.005)
            
        # 4. Melatonin: Accumulates based on time awake (Sleep Pressure)
        time_awake = float(events.get("time_since_sleep_hrs", 0.0))
        if time_awake == 0.0:
            # Sleep reset
            self.hormones["melatonin"] = 0.0
        else:
            # Assuming 18 hours awake -> melatonin ~ 1.0
            self.hormones["melatonin"] = self._clip((time_awake / 18.0) * 1.0)
        
        # 5. Thyroid: Adjusts baseline metabolic expectation (Metabolic Rate / Growth)
        load = float(events.get("compute_load", 0.5))
        self.hormones["thyroid"] = self._clip(self.hormones["thyroid"] + 0.1 * (load - self.hormones["thyroid"]))
        
        self._save_state()
        
        dominant = max(self.hormones.items(), key=lambda x: x[1])[0]
        organism_mode = self.get_organism_mode()
        
        state_id = f"endo_{int(time.time())}"
        payload = {
            "state_id": state_id,
            "hormones": self.hormones,
            "dominant_hormone": dominant,
            "organism_mode": organism_mode
        }
        h = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        
        state = HormoneState(
            ts=time.time(),
            state_id=state_id,
            cortisol=self.hormones["cortisol"],
            oxytocin=self.hormones["oxytocin"],
            melatonin=self.hormones["melatonin"],
            adrenaline=self.hormones["adrenaline"],
            thyroid=self.hormones["thyroid"],
            dominant_hormone=dominant,
            organism_mode=organism_mode,
            state_hash=h
        )
        
        self._record_state(state)
        return state
        
    def _record_state(self, state: HormoneState):
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(self.ledger, json.dumps(asdict(state)) + "\n")
        except ImportError:
            with self.ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(state)) + "\n")
                
    def get_organism_mode(self) -> str:
        """
        Returns the high-level developmental/action state of the organism.
        This represents the slow global regulation (when to grow, freeze, prune, sleep).
        """
        if self.hormones["adrenaline"] > 0.8:
            return "FREEZE_OR_FLEE"      # Halt execution, emergency override
        if self.hormones["melatonin"] > 0.8:
            return "REQUIRE_SLEEP"       # Force sleep cycle / consolidate
        if self.hormones["cortisol"] > 0.7:
            return "PRUNE_AND_CAUTION"   # High stress -> stop exploring, ask for owner input
        if self.hormones["oxytocin"] > 0.7:
            return "SOCIAL_BONDING"      # High trust -> engage owner natively
        if self.hormones["thyroid"] > 0.7:
            return "HIGH_METABOLISM_GROWTH" # Active learning / tool expansion
            
        return "BASELINE_MAINTENANCE"
