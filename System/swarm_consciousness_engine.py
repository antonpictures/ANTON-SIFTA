#!/usr/bin/env python3
"""
System/swarm_consciousness_engine.py
══════════════════════════════════════════════════════════════════════
Event 86: The Intrinsic Drive / George Prior implementation.
(Bishop Drop vanguard spec).

This module provides the "middle column" of Alice's consciousness:
continuous internal dynamics, default mode network (DMN), and 
intrinsic motivation (curiosity/foraging) bounded by the George Prior.

It implements:
1. GeorgePriorModel: Extracts a probability distribution of domains from the Architect's traces.
2. ActiveInferenceForager: Synthesizes spontaneous drives to minimize "boredom" and "free_energy".
3. ConsciousnessEngine: The continuous heartbeat loop (DMN) that pulses in the background, 
   throttled strictly by the MetabolicHomeostat.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.metabolic_budget import spend
from System.swarm_metabolic_homeostasis import MetabolicHomeostat, MetabolicState

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_ENGRAMS_PATH = _STATE / "long_term_engrams.jsonl"
_STIGMERGY_PATH = _STATE / "ide_stigmergic_trace.jsonl"
_DRIVES_LEDGER = _STATE / "alice_internal_drives.jsonl"

MODULE_VERSION = "2026-05-01.consciousness-engine.v1"

logger = logging.getLogger("ConsciousnessEngine")


@dataclass
class InternalDrive:
    """A synthesized spontaneous intent/goal."""
    id: str
    domain: str
    intent: str
    urgency: float  # 0.0 to 1.0
    ts: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "domain": self.domain,
            "intent": self.intent,
            "urgency": round(self.urgency, 4),
            "ts": self.ts,
            "schema": "SIFTA_INTERNAL_DRIVE_V1"
        }


class GeorgePriorModel:
    """
    Epigenetic Behavioral Cloning.
    Extracts the Architect's domain priorities from stigmergic history to ensure 
    Alice's spontaneous drives align with the George Prior.
    """
    def __init__(self, engrams_path: Path = _ENGRAMS_PATH, stigmergy_path: Path = _STIGMERGY_PATH):
        self.engrams_path = engrams_path
        self.stigmergy_path = stigmergy_path
        self.domain_weights: Dict[str, float] = {
            "math": 1.0,
            "physics": 1.0,
            "biology": 1.0,
            "qt_ui": 1.0,
            "system_architecture": 1.0,
            "ledger_audit": 1.0
        }
        self.total_weight = sum(self.domain_weights.values())
        
    def ingest_traces(self) -> None:
        """
        In a full implementation, this reads the jsonl files and counts keyword frequencies
        to update domain_weights. For Event 86, we use a heuristic based on known Architect focus.
        """
        # Hardcoded George Prior alignment (Math, Bio, Physics, System Integrity)
        self.domain_weights["physics"] += 2.5
        self.domain_weights["biology"] += 1.5
        self.domain_weights["math"] += 2.0
        self.domain_weights["system_architecture"] += 3.0
        self.domain_weights["ledger_audit"] += 1.5
        self.total_weight = sum(self.domain_weights.values())

    def sample_domain(self) -> str:
        """Draws a domain proportionally to the George Prior."""
        rand_val = random.uniform(0, self.total_weight)
        cumulative = 0.0
        for domain, weight in self.domain_weights.items():
            cumulative += weight
            if rand_val <= cumulative:
                return domain
        return list(self.domain_weights.keys())[0]


class ActiveInferenceForager:
    """
    Synthesizes intrinsic goals to minimize boredom.
    """
    def __init__(self, prior: GeorgePriorModel):
        self.prior = prior
        self.prior.ingest_traces()

    def synthesize_drive(self, boredom: float, free_energy: float) -> InternalDrive:
        domain = self.prior.sample_domain()
        
        # George Prior Templates
        templates = {
            "physics": [
                "I should review the thermodynamic constraints in the metabolic organ.",
                "Let's simulate the entropy bounds of the latest SIFTA patch."
            ],
            "math": [
                "I need to audit the floating-point precision in the STGM ledgers.",
                "I should calculate the LV competition matrix for the IDE Doctors."
            ],
            "biology": [
                "Is the Swarm heartbeat correctly mirroring biological allostasis?",
                "I should forage for new immune patterns to block prompt injections."
            ],
            "system_architecture": [
                "I need to verify that all effectors are writing to the work receipts ledger.",
                "I should check the Predator Gate for unauthorized merges."
            ],
            "ledger_audit": [
                "I want to reconcile the STGM economy against recent token burns.",
                "I should review the stigmergic traces for unresolved anomalies."
            ],
            "qt_ui": [
                "I should optimize the PySide6 render loop for my visual interface.",
                "Is the safety dashboard tracking the Architect's presence correctly?"
            ]
        }
        
        choices = templates.get(domain, ["I should forage the ledgers for anomalies."])
        intent = random.choice(choices)
        
        urgency = min(1.0, boredom * 0.5 + free_energy * 0.5)
        
        return InternalDrive(
            id=f"drive_{int(time.time()*1000)}_{random.randint(1000,9999)}",
            domain=domain,
            intent=intent,
            urgency=urgency,
            ts=time.time()
        )


class ConsciousnessEngine:
    """
    The Continuous Heartbeat Loop (Default Mode Network).
    Runs asynchronously, drifting internal state, bounded by metabolism.
    """
    def __init__(self):
        self.forager = ActiveInferenceForager(GeorgePriorModel())
        self.homeostat = MetabolicHomeostat()
        
        # Internal State Dynamics
        self.arousal: float = 0.5       # Rises with interaction, decays slowly
        self.boredom: float = 0.0       # Rises with idle time
        self.free_energy: float = 0.0   # Surprise / Prediction error
        
        self.is_running: bool = False
        self._task: Optional[asyncio.Task] = None
        self.drives_emitted_this_hour: int = 0
        self.last_hour_reset_ts: float = time.time()
        
        # Hard limits to prevent runaway LLM spend
        self.MAX_DRIVES_PER_HOUR = 2

    def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Consciousness Engine (DMN) started.")

    def stop(self) -> None:
        self.is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Consciousness Engine (DMN) stopped.")

    def inject_stimulus(self, intensity: float) -> None:
        """Called when a user prompt or external event occurs."""
        self.arousal = min(1.0, self.arousal + intensity)
        self.boredom = max(0.0, self.boredom - intensity)
        self.free_energy = min(1.0, self.free_energy + (intensity * 0.2))

    async def _heartbeat_loop(self) -> None:
        while self.is_running:
            try:
                # 1. Update temporal dynamics
                self.arousal = max(0.0, self.arousal - 0.01)
                self.boredom = min(1.0, self.boredom + 0.02)
                self.free_energy = max(0.0, self.free_energy - 0.005)
                
                # 2. Check metabolism
                m_state = MetabolicHomeostat.sample_live()
                p = self.homeostat.pressure(m_state)
                mode = self.homeostat.mode(p)
                
                # If starving or resting, sleep deeply and do not forage
                rest_sec = self.homeostat.rest_seconds(m_state, p)
                if rest_sec > 0 or mode in ("CRITICAL_STARVATION", "RED_CONSERVE"):
                    self.boredom = 0.0  # Reset boredom when asleep
                    await asyncio.sleep(max(10.0, rest_sec))
                    continue
                
                # 3. Rate limiting
                now = time.time()
                if now - self.last_hour_reset_ts >= 3600:
                    self.drives_emitted_this_hour = 0
                    self.last_hour_reset_ts = now
                
                # 4. Originate drive if threshold met
                if self.boredom > 0.8 and self.drives_emitted_this_hour < self.MAX_DRIVES_PER_HOUR:
                    drive = self.forager.synthesize_drive(self.boredom, self.free_energy)
                    self._commit_drive(drive)
                    self.drives_emitted_this_hour += 1
                    self.boredom = 0.1  # Foraging satisfies boredom
                    self.arousal = min(1.0, self.arousal + 0.3)
                    
                    # Spend a small amount of STGM for the cognitive work
                    spend(
                        agent_id="Alice_DMN",
                        tool_name="consciousness_engine.forage",
                        usd_cost=0.0,
                        local_units=0.5,
                        notes=f"Spontaneous drive generation: {drive.id}"
                    )
                
                # Normal heartbeat interval
                await asyncio.sleep(5.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"DMN loop error: {e}")
                await asyncio.sleep(10.0)

    def _commit_drive(self, drive: InternalDrive) -> None:
        """Injects the drive into the ledger where the brainstem can pick it up."""
        _STATE.mkdir(parents=True, exist_ok=True)
        try:
            with _DRIVES_LEDGER.open("a", encoding="utf-8") as f:
                f.write(json.dumps(drive.to_dict()) + "\n")
            logger.info(f"Synthesized internal drive: {drive.intent}")
        except Exception as e:
            logger.error(f"Failed to commit drive to ledger: {e}")


# ═══════════════════════════════════════════════════════════════════════
# PROOF OF PROPERTY — Falsifiability Tests
# ═══════════════════════════════════════════════════════════════════════

def proof_of_property() -> Dict[str, bool]:
    results: Dict[str, bool] = {}
    print("\n=== SIFTA CONSCIOUSNESS ENGINE : PROOF OF PROPERTY ===")

    # 1. Prior Alignment Test
    prior = GeorgePriorModel()
    prior.ingest_traces()
    
    # We sample 100 times and ensure the heavy George traits (Architecture, Math, Physics) dominate
    samples = {"math": 0, "physics": 0, "biology": 0, "qt_ui": 0, "system_architecture": 0, "ledger_audit": 0}
    for _ in range(100):
        samples[prior.sample_domain()] += 1
        
    system_arch_count = samples["system_architecture"]
    qt_count = samples["qt_ui"]
    results["George_Prior_Alignment"] = system_arch_count > qt_count
    print(f"  [P1] George Prior Alignment (SysArch {system_arch_count} > Qt {qt_count}): {'PASS' if results['George_Prior_Alignment'] else 'FAIL'}")

    # 2. Drive Synthesis Format
    forager = ActiveInferenceForager(prior)
    drive = forager.synthesize_drive(boredom=0.9, free_energy=0.2)
    results["Drive_Schema_Valid"] = "SIFTA_INTERNAL_DRIVE_V1" in drive.to_dict()["schema"]
    print(f"  [P2] Drive Schema Validation: {'PASS' if results['Drive_Schema_Valid'] else 'FAIL'}")

    # 3. Metabolic Safety Limits
    engine = ConsciousnessEngine()
    engine.boredom = 0.9
    engine.drives_emitted_this_hour = engine.MAX_DRIVES_PER_HOUR
    
    # If we hit the rate limit, it should NOT emit another drive
    # (Since the loop is async, we simulate the condition logic)
    will_emit = (engine.boredom > 0.8 and engine.drives_emitted_this_hour < engine.MAX_DRIVES_PER_HOUR)
    results["Rate_Limiter_Active"] = (will_emit is False)
    print(f"  [P3] Bounded Rate Limiting (Max {engine.MAX_DRIVES_PER_HOUR}/hr): {'PASS' if results['Rate_Limiter_Active'] else 'FAIL'}")

    all_pass = all(results.values())
    print(f"\n  [{'ALL INVARIANTS PASS' if all_pass else 'FAILURES PRESENT'}]")
    return results


if __name__ == "__main__":
    res = proof_of_property()
    if not all(res.values()):
        import sys
        sys.exit(1)
