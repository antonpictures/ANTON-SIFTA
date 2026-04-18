#!/usr/bin/env python3
"""
cross_hardware_router.py — SIFTA Hardware Dispatcher
═══════════════════════════════════════════════════════════════════
Turns the Swarm Blackboard from an abstract task queue into a
spatially-aware distributed scheduler.

Different physical surfaces have different physics:
- M5_STUDIO: High throughput, heavy lifting.
- M1_MINI: Low latency, edge agility.
- CRUCIBLE: High reliability, isolated simulation (for risky mutations).

Tasks are routed based on their Risk (inverse of stability). High risk
automatically mathematically routes to the Crucible.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import random
import time
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_ROUTING_LOG = _STATE_DIR / "routing_history.jsonl"


@dataclass
class ComputeTarget:
    name: str
    latency_ms: float
    throughput: float
    reliability: float
    cost: float


@dataclass
class RoutedTask:
    task_id: str
    target: str
    risk: float
    ts: float


class CrossHardwareRouter:
    def __init__(self):
        # Physical topology profiles of the SIFTA organism
        self.targets: Dict[str, ComputeTarget] = {
            "M5_STUDIO": ComputeTarget("M5_STUDIO", latency_ms=15.0, throughput=5.0, reliability=0.85, cost=0.5),
            "M1_MINI": ComputeTarget("M1_MINI", latency_ms=2.0, throughput=1.0, reliability=0.90, cost=0.1),
            "CRUCIBLE": ComputeTarget("CRUCIBLE", latency_ms=50.0, throughput=0.5, reliability=1.00, cost=0.8),
        }

    def score_target(self, t: ComputeTarget, risk: float) -> float:
        """
        The SIFTA adaptation of the LLM's routing math.
        If risk is low (0.0), throughput dominates.
        If risk is high (1.0), reliability uniquely dominates, forcing it to CRUCIBLE.
        """
        throughput_val = t.throughput * max(0.0, (1.0 - risk * 1.5)) * 3.0
        
        # Exponentiate reliability so 1.0 (Crucible) crushes 0.90 (M1) at high risk
        reliability_val = (t.reliability ** 6) * (risk * 20.0)
        
        # Latency penalty fades as risk rises (safer to be slow)
        latency_penalty = t.latency_ms * 0.05 * max(0.0, 1.0 - risk)
        
        cost_penalty = t.cost * 1.5
        
        return throughput_val + reliability_val - latency_penalty - cost_penalty

    def route_task(self, task_id: str, risk: float = 0.0) -> str:
        """
        Calculates the best physical hardware target for a given task,
        injecting bounded turbulence to escape local maxima.
        """
        scores = {}
        for name, t in self.targets.items():
            scores[name] = self.score_target(t, risk)

        # Stochastic tie-break = swarm turbulence (simulate organic variance)
        best = max(scores.items(), key=lambda x: x[1] + random.uniform(-0.2, 0.2))[0]

        routed = RoutedTask(
            task_id=task_id,
            target=best,
            risk=risk,
            ts=time.time(),
        )

        self._log_route(routed)
        return best

    def _log_route(self, routed: RoutedTask):
        try:
            with open(_ROUTING_LOG, "a") as f:
                f.write(json.dumps({
                    "task_id": routed.task_id,
                    "target": routed.target,
                    "risk": round(routed.risk, 3),
                    "ts": routed.ts
                }) + "\n")
        except Exception:
            pass

# Singleton
_ROUTER_INSTANCE: Optional[CrossHardwareRouter] = None

def get_router() -> CrossHardwareRouter:
    global _ROUTER_INSTANCE
    if _ROUTER_INSTANCE is None:
        _ROUTER_INSTANCE = CrossHardwareRouter()
    return _ROUTER_INSTANCE

if __name__ == "__main__":
    r = get_router()
    print("═" * 58)
    print("  SIFTA — CROSS-HARDWARE ROUTER")
    print("═" * 58 + "\n")
    
    print("  1. Simulating LOW risk task (Risk = 0.1):")
    t1 = r.route_task("TASK_A", risk=0.1)
    print(f"     -> Routed to: {t1}\n")
    
    print("  2. Simulating MEDIUM risk task (Risk = 0.5):")
    t2 = r.route_task("TASK_B", risk=0.5)
    print(f"     -> Routed to: {t2}\n")
    
    print("  3. Simulating HIGH risk task (Risk = 0.95):")
    t3 = r.route_task("TASK_C", risk=0.95)
    print(f"     -> Routed to: {t3}\n")
