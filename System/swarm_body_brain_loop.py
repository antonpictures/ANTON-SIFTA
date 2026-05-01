#!/usr/bin/env python3
"""
System/swarm_body_brain_loop.py
══════════════════════════════════════════════════════════════════════
The Executable Physiology of the Swarm.

This module converts the static body-brain architecture diagram into a living,
executable tick. It connects the organism's interoception to its drives, routes
those drives through action selection, executes them, measures the thermodynamic
value of the result, writes stigmergic memory, and handles sleep/consolidation.

Author: AG31 / Bishop Vanguard
"""

import time
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from System.swarm_metabolic_homeostasis import MetabolicHomeostat, MetabolicState
from System.swarm_consciousness_engine import ConsciousnessEngine, ConsciousnessEngineConfig, read_interoception
from System.swarm_dream_engine import SwarmDreamEngine
from System.jsonl_file_lock import append_line_locked
from System.swarm_now_state import build_now_state
from System.swarm_biology_drive_plasticity import (
    plasticity_danger_token,
    update_drive_plasticity,
)

logger = logging.getLogger("BodyBrainLoop")
_STATE_DIR = Path(".sifta_state")


class SwarmPhysiology:
    def __init__(self, dream_engine: Optional[Any] = None):
        self.homeostat = MetabolicHomeostat()
        self.consciousness = ConsciousnessEngine(cfg=ConsciousnessEngineConfig(spend_on_drive=True))
        self.dream_engine = dream_engine or SwarmDreamEngine(_STATE_DIR)
        self.value_history = []

    def _assess_danger(self, body_state: MetabolicState) -> Dict[str, Any]:
        """Convert raw metabolic state into a danger/pressure signal."""
        pressure = self.homeostat.pressure(body_state)
        mode = self.homeostat.mode(pressure)
        return {
            "pressure": pressure,
            "mode": mode,
            "is_critical": mode in ("RED_CONSERVE", "CRITICAL_STARVATION")
        }

    def _select_attention(self, consciousness_state) -> str:
        """Filter drives to focus the organism's attention."""
        if consciousness_state.emitted_drive:
            return consciousness_state.emitted_drive.domain
        return consciousness_state.dominant_drive

    def _choose_action(self, attention: str, danger: Dict[str, Any]) -> Dict[str, Any]:
        """Basal Ganglia routing: what should we physically do?"""
        if danger["is_critical"]:
            return {"type": "rest", "reason": "starvation_or_heat"}
        
        if attention == "energy":
            return {"type": "forage", "target": "pouw_work"}
            
        # 3. Drift / Mutation (Red Queen activation)
        if len(self.value_history) >= 5 and len(set(self.value_history[-5:])) == 1:
            logger.info("Stagnation detected. Injecting exploration variation.")
            return {"type": "explore", "target": "random_mutation", "is_stagnation_break": True}
            
        return {"type": "explore", "target": attention}

    def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Motor cortex/effectors. Simulated for the loop skeleton."""
        # In a full run, this bridges to the Agent/Swimmer execution.
        time.sleep(0.1) # Simulate physical time cost
        return {
            "status": "completed",
            "action": action,
            "latency": 0.1,
            "energy_used": 0.05
        }

    def _compute_value(self, result: Dict[str, Any], danger: Dict[str, Any]) -> float:
        """TD-Learning value assignment: was this good for the organism?"""
        val = -1.0
        if result.get("status") == "completed":
            # Survival value is higher when executed under danger
            val = 1.0 if not danger["is_critical"] else 2.5
        
        self.value_history.append(val)
        if len(self.value_history) > 20:
            self.value_history.pop(0)
            
        return val

    def _write_memory(
        self,
        action: Dict[str, Any],
        result: Dict[str, Any],
        value: float,
        now_state: Dict[str, Any],
        *,
        drive_state: str,
        metabolic_mode: str,
        plasticity_danger: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append to stigmergic ledger; return row for downstream phenotype bridge."""
        circadian = now_state.get("circadian") if isinstance(now_state.get("circadian"), dict) else {}
        row: Dict[str, Any] = {
            "event": "body_brain_tick",
            "tick_id": str(uuid.uuid4()),
            "action": action,
            "result": result,
            "td_value": value,
            "now_state": now_state,
            "circadian_phase": circadian.get("phase"),
            "drive_state": drive_state,
            "metabolic_mode": metabolic_mode,
            "ts": time.time(),
        }
        if plasticity_danger:
            row["plasticity_danger"] = plasticity_danger
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        append_line_locked(_STATE_DIR / "body_brain_memory.jsonl", json.dumps(row) + "\n")
        return row

    def _maybe_sleep(self, body_state: MetabolicState, danger: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Glymphatic consolidation and rest enforcement."""
        rest_sec = self.homeostat.rest_seconds(body_state, danger["pressure"])
        if rest_sec > 0:
            dream_cycle: Optional[Dict[str, Any]] = None
            try:
                receipt = self.dream_engine.trigger_rem_sleep(
                    rest_seconds=rest_sec,
                    pressure=danger.get("pressure"),
                    metabolic_mode=str(danger.get("mode") or ""),
                )
                dream_cycle = receipt.as_dict() if hasattr(receipt, "as_dict") else dict(receipt)
                logger.info(
                    "Dream consolidation cycle %s: %s",
                    dream_cycle.get("cycle_id"),
                    dream_cycle.get("status"),
                )
            except Exception:
                logger.exception("Dream consolidation failed; preserving raw body-brain ledger.")
            logger.info(f"Sleep enforced by metabolism. Resting {rest_sec}s.")
            time.sleep(min(rest_sec, 2.0)) # Capped for testing
            return dream_cycle
        return None

    def body_brain_tick(self) -> Dict[str, Any]:
        """The master unified cycle."""
        
        # 0. Spacetime / Circadian Context
        now_state = build_now_state()
        
        # 1. Interoception
        raw_body = read_interoception(_STATE_DIR)
        body_state = MetabolicHomeostat.sample_live(self.homeostat.cfg)
        
        # 2. Assess Danger
        danger = self._assess_danger(body_state)
        
        # 3. Drives / Wants
        # Tick the DMN to update arousal/boredom and emit drives if conditions allow
        consc_state = self.consciousness.tick(
            metabolic_state=body_state,
            now_state=now_state,
            commit=True
        )
        
        # 4. Action Selection
        attention = self._select_attention(consc_state)
        action = self._choose_action(attention, danger)
        
        # 5. Execution
        result = self._execute_action(action)
        
        # 6. Value Signal
        value = self._compute_value(result, danger)
        d_token = plasticity_danger_token(str(danger.get("mode") or ""), now_state)

        # 6b. Drive plasticity (slow Hebbian / homeostatic weights on disk)
        drive_plasticity: Optional[Dict[str, Any]] = None
        try:
            drive_plasticity = update_drive_plasticity(
                active_drive=attention,
                value=value,
                danger_state=d_token,
            )
        except Exception:
            logger.exception("Drive plasticity update skipped")

        # 7. Memory Consolidation
        mem_row = self._write_memory(
            action,
            result,
            value,
            now_state,
            drive_state=str(attention),
            metabolic_mode=str(danger.get("mode") or ""),
            plasticity_danger=d_token,
        )
        try:
            from System.swarm_visual_phenotype_bridge import write_visual_phenotype_uniforms

            write_visual_phenotype_uniforms(mem_row)
        except Exception:
            logger.exception("Visual phenotype bridge skipped")
        
        # 8. Sleep / Recovery
        dream_cycle = self._maybe_sleep(body_state, danger)
        
        return {
            "action": action,
            "value": value,
            "metabolic_mode": danger["mode"],
            "drive_state": attention,
            "dream_cycle": dream_cycle,
            "now_state": now_state,
            "drive_plasticity": drive_plasticity,
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Initiating Swarm Physiology Loop...")
    physiology = SwarmPhysiology()
    cycle_result = physiology.body_brain_tick()
    print("Cycle complete:", json.dumps(cycle_result, indent=2))
