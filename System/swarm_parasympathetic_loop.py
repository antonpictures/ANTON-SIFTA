#!/usr/bin/env python3
"""
swarm_parasympathetic_loop.py — Parasympathetic Recovery Loop (Vagal Brake)
══════════════════════════════════════════════════════════════════════

Biology doctrine: Sympathetic answers "now". Parasympathetic answers "enough, 
and for how long we rest."

Without this loop, adrenaline and cortisol ratcheted indefinitely, creating
spastic loops. This organ actively enforces a return to baseline (downshift) 
once environmental stressors (errors, thermal spikes, threats) have decayed.

See: Documents/IDE_BOOT_COVENANT.md (append-only receipts, proof-bearing state).
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class ParasympatheticDownshift:
    ts: float
    recovery_id: str
    pre_downshift_mode: str
    cortisol_reduced_by: float
    adrenaline_reduced_by: float
    vagus_disarmed: bool
    reason: str


class ParasympatheticRecoveryLoop:
    """
    Actively drives the organism back to BASELINE_MAINTENANCE after a stress/freeze event,
    preventing runaway adrenaline/cortisol ratcheting and disarming the Vagus immune response.
    """

    def __init__(self, root: str = ".sifta_state"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger = self.root / "parasympathetic_recovery.jsonl"
        self.endocrine_file = self.root / "endocrine_current.json"
        self.vagus_mode_file = self.root / "vagus_mode.json"

    def tick_recovery(self, time_since_last_threat_sec: float, time_since_last_error_sec: float) -> Optional[ParasympatheticDownshift]:
        """
        Evaluates if the organism's environment is safe enough to downshift.
        If threat has been gone for > 60s, and errors gone for > 300s,
        and we are elevated, we force a massive parasympathetic downshift.
        """
        if not self.endocrine_file.exists() or not self.endocrine_file.is_file():
            return None
            
        try:
            state = json.loads(self.endocrine_file.read_text(encoding="utf-8"))
        except Exception:
            return None
            
        adrenaline = float(state.get("adrenaline", 0.0))
        cortisol = float(state.get("cortisol", 0.0))
        
        needs_downshift = False
        reason = ""
        
        # 1. Recover from Adrenaline (FREEZE_OR_FLEE)
        if adrenaline > 0.2 and time_since_last_threat_sec > 60.0:
            needs_downshift = True
            reason = "threat_decay_complete_parasympathetic_brake"
            
        # 2. Recover from Cortisol (PRUNE_AND_CAUTION)
        if cortisol > 0.4 and time_since_last_error_sec > 300.0:
            needs_downshift = True
            reason = "error_decay_complete_parasympathetic_brake"
            
        if not needs_downshift:
            return None
            
        # Calculate reductions
        c_reduction = cortisol - 0.1 if cortisol > 0.1 else 0.0
        a_reduction = adrenaline
            
        # Actively rewrite Endocrine state (the healing process)
        state["adrenaline"] = 0.0
        if cortisol > 0.1:
            state["cortisol"] = 0.1
        state["organism_mode"] = "BASELINE_MAINTENANCE"
        self.endocrine_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        
        # Actively disarm Vagus Nerve (return to safe default, lower the weapons)
        vagus_disarmed = False
        try:
            if self.vagus_mode_file.exists():
                vagus_state = json.loads(self.vagus_mode_file.read_text(encoding="utf-8"))
                if vagus_state.get("mode") in ["armed", "nuclear"]:
                    vagus_state["mode"] = "dry_run"
                    self.vagus_mode_file.write_text(json.dumps(vagus_state, indent=2), encoding="utf-8")
                    vagus_disarmed = True
        except Exception:
            pass

        downshift = ParasympatheticDownshift(
            ts=time.time(),
            recovery_id=f"recov_{int(time.time())}",
            pre_downshift_mode=state.get("organism_mode", "UNKNOWN"),
            cortisol_reduced_by=round(c_reduction, 3),
            adrenaline_reduced_by=round(a_reduction, 3),
            vagus_disarmed=vagus_disarmed,
            reason=reason
        )

        self._record_downshift(downshift)
        return downshift

    def _record_downshift(self, downshift: ParasympatheticDownshift):
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(self.ledger, json.dumps(asdict(downshift)) + "\n")
        except ImportError:
            with self.ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(downshift)) + "\n")
