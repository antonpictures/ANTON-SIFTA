#!/usr/bin/env python3
"""
swarm_blackboard.py — SIFTA Blackboard 2.0
═══════════════════════════════════════════════════════════════════
SOLID_PLAN §5.2 Track S1 — Swarm Blackboard 2.0 (The Coordination Substrate)

This module implements the Pheromone-Weighted Planning graph.
Tasks are not centrally assigned. They act as "gravity wells" on the 
blackboard. Swimmers gradient-descend toward the most valuable tasks.

Mechanisms:
1. Base Gravity: Driven by the ObjectiveRegistry (the swarm's charter).
2. Pheromone Thickness: Agents drop pheromones (STGM/attention) on tasks.
3. Total Gravity = Base Gravity + Pheromone Thickness.
4. Anti-Starvation: Base gravity ensures "boring but critical" tasks 
   never reach 0 probability of being sampled.
5. Turbulence: Bounded randomness injected during task sampling to escape
   local maxima, governed by the current TemporalPulse climate.

Sovereign coordination layer. No central planner.
"""

import json
import time
import math
import random
import threading
import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_BLACKBOARD_GRAPH = _STATE_DIR / "blackboard_graph.json"
_BLACKBOARD_LOG = _STATE_DIR / "blackboard_events.jsonl"


@dataclass
class TaskNode:
    """A task acting as a gravity well in the swarm."""
    task_id: str
    description: str
    status: str                 # PENDING, ACTIVE, COMPLETED, FAILED
    base_gravity: float         # 0.0 - 1.0 (from ObjectiveRegistry)
    pheromone_thickness: float  # Added attention / votes
    created_at: float
    updated_at: float
    artifacts: List[str]        # Related files or .scar IDs
    assigned_to: Optional[str]  # Which agent claimed it
    hardware_target: str        # Which physical node this must run on

    @property
    def total_gravity(self) -> float:
        """The actual attractive force of the task."""
        return self.base_gravity + self.pheromone_thickness


class SwarmBlackboard:
    def __init__(self):
        self._lock = threading.Lock()
        self._tasks: Dict[str, TaskNode] = {}
        self._load()

    # ── Task Lifecycle ──────────────────────────────────────────────

    def post_task(self, description: str, objective_estimates: Dict[str, float],
                  artifacts: List[str] = None) -> TaskNode:
        """
        Post a new task to the blackboard. The objective estimates define
        its base gravitational pull based on the current Swarm charter.
        """
        if artifacts is None:
            artifacts = []

        try:
            from objective_registry import get_registry
            base_gravity = get_registry().score_action(objective_estimates)
        except ImportError:
            base_gravity = sum(objective_estimates.values()) / max(1, len(objective_estimates))

        # Deterministic ID based on description and time
        raw = f"{description}:{time.time()}"
        task_id = "TASK_" + hashlib.sha256(raw.encode()).hexdigest()[:12]

        try:
            from cross_hardware_router import get_router
            risk = max(0.0, 1.0 - objective_estimates.get("stability", 0.5))
            hardware_target = get_router().route_task(task_id, risk)
        except ImportError:
            hardware_target = "M5_STUDIO"

        now = time.time()
        node = TaskNode(
            task_id=task_id,
            description=description,
            status="PENDING",
            base_gravity=round(base_gravity, 4),
            pheromone_thickness=0.0,
            created_at=now,
            updated_at=now,
            artifacts=artifacts,
            assigned_to=None,
            hardware_target=hardware_target
        )

        with self._lock:
            self._tasks[task_id] = node

        self._log_event("POST", task_id, {"gravity": node.base_gravity, "desc": description})
        self._persist()
        return node

    def add_pheromone(self, task_id: str, amount: float, agent_id: str) -> bool:
        """
        Agents can vote (drop pheromones) on tasks to increase their gravity.
        Cost should be tied to STGM in calling layers.
        """
        with self._lock:
            if task_id not in self._tasks:
                return False
            task = self._tasks[task_id]
            task.pheromone_thickness += amount
            task.updated_at = time.time()

        self._log_event("PHEROMONE", task_id, {"amount": amount, "agent": agent_id})
        self._persist()
        return True

    def update_status(self, task_id: str, new_status: str, agent_id: str) -> bool:
        """Mark a task as ACTIVE, COMPLETED, or FAILED."""
        valid_statuses = {"PENDING", "ACTIVE", "COMPLETED", "FAILED"}
        if new_status not in valid_statuses:
            return False

        with self._lock:
            if task_id not in self._tasks:
                return False
            task = self._tasks[task_id]
            task.status = new_status
            task.updated_at = time.time()
            if new_status == "ACTIVE":
                task.assigned_to = agent_id

        self._log_event("STATUS_UPDATE", task_id, {"status": new_status, "agent": agent_id})
        self._persist()
        return True

    def decay_pheromones(self, decay_rate: float = 0.05):
        """Global decay to prevent infinite pheromone buildup."""
        with self._lock:
            for task in self._tasks.values():
                if task.status in {"PENDING", "ACTIVE"}:
                    task.pheromone_thickness = max(0.0, task.pheromone_thickness * (1.0 - decay_rate))
        self._persist()

    # ── Pheromone-Weighted Planning ─────────────────────────────────

    def sample_task(self, agent_id: str, agent_hardware: str = "M5_STUDIO") -> Optional[TaskNode]:
        """
        Returns a task for the agent to work on. 
        Instead of sorting by strict priority, this uses weighted random 
        sampling (gradient descent) based on `total_gravity`.
        Incorporates Turbulence (climate-driven randomness) and Anti-Starvation.
        Strictly filters by `agent_hardware`.
        """
        with self._lock:
            pending = [
                t for t in self._tasks.values() 
                if t.status == "PENDING" and (t.hardware_target == agent_hardware or agent_hardware == "ANY")
            ]

        if not pending:
            return None

        # 1. Determine Turbulence based on Temporal Climate
        turbulence_factor = 0.0
        try:
            from temporal_layering import get_layer
            pulse = get_layer().get_last_pulse()
            climate = pulse.mutation_climate if pulse else "OPEN"
            
            if climate == "OPEN":
                turbulence_factor = 0.2  # Calm times: allow exploration
            elif climate == "CAUTIOUS":
                turbulence_factor = 0.05 # Busy times: stay focused
            elif climate == "FROZEN":
                turbulence_factor = 0.0  # Crisis: strict priority only
        except ImportError:
            turbulence_factor = 0.1

        # 2. Add Turbulence and construct weight list
        weights = []
        for t in pending:
            # Add random noise bounded by turbulence factor
            noise = random.uniform(0, turbulence_factor) if turbulence_factor > 0 else 0
            # Ensure anti-starvation: weight can never be 0 if base_gravity > 0
            w = max(0.01, t.total_gravity + noise)
            weights.append(w)

        # 3. Pheromone-weighted sampling
        chosen_task = random.choices(pending, weights=weights, k=1)[0]
        
        # Auto-claim the task
        self.update_status(chosen_task.task_id, "ACTIVE", agent_id)
        return chosen_task

    # ── Diagnostics ─────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """Summary metrics for the Cartography Dashboard."""
        with self._lock:
            tasks = list(self._tasks.values())
        
        pending_tasks = [t for t in tasks if t.status == "PENDING"]
        completed = len([t for t in tasks if t.status == "COMPLETED"])
        failed = len([t for t in tasks if t.status == "FAILED"])
        
        hardware_distribution = {
            "M5_STUDIO": len([t for t in pending_tasks if getattr(t, "hardware_target", "M5_STUDIO") == "M5_STUDIO"]),
            "M1_MINI": len([t for t in pending_tasks if getattr(t, "hardware_target", "M5_STUDIO") == "M1_MINI"]),
            "CRUCIBLE": len([t for t in pending_tasks if getattr(t, "hardware_target", "M5_STUDIO") == "CRUCIBLE"]),
        }
        
        strongest = None
        if pending_tasks:
            strongest = max(pending_tasks, key=lambda t: t.total_gravity)

        return {
            "total_tasks": len(tasks),
            "pending_count": len(pending_tasks),
            "completed_count": completed,
            "failed_count": failed,
            "hardware_distribution": hardware_distribution,
            "strongest_gravity": strongest.total_gravity if strongest else 0.0,
            "strongest_task_id": strongest.task_id if strongest else None,
            "strongest_desc": strongest.description if strongest else None
        }

    # ── Persistence ─────────────────────────────────────────────────

    def _persist(self) -> None:
        try:
            with self._lock:
                data = {tid: asdict(node) for tid, node in self._tasks.items()}
            _BLACKBOARD_GRAPH.write_text(json.dumps(data, indent=2))
        except Exception:
            pass

    def _load(self) -> None:
        if not _BLACKBOARD_GRAPH.exists():
            return
        try:
            data = json.loads(_BLACKBOARD_GRAPH.read_text())
            for tid, tdict in data.items():
                self._tasks[tid] = TaskNode(**tdict)
        except Exception:
            pass

    def _log_event(self, action: str, task_id: str, meta: Dict[str, Any]):
        try:
            evt = {
                "ts": time.time(),
                "action": action,
                "task_id": task_id,
                **meta
            }
            with open(_BLACKBOARD_LOG, "a") as f:
                f.write(json.dumps(evt) + "\n")
        except Exception:
            pass


# ── Singleton ────────────────────────────────────────────────────────
_BBOARD_INSTANCE: Optional[SwarmBlackboard] = None

def get_blackboard() -> SwarmBlackboard:
    """Global singleton access to the Blackboard graph."""
    global _BBOARD_INSTANCE
    if _BBOARD_INSTANCE is None:
        _BBOARD_INSTANCE = SwarmBlackboard()
    return _BBOARD_INSTANCE


if __name__ == "__main__":
    print("═" * 58)
    print("  SIFTA — BLACKBOARD 2.0 (Pheromone-Weighted Planning)")
    print("═" * 58 + "\n")

    board = get_blackboard()
    
    print("  1. Posting tests tasks...")
    # Add a boring but critical task (Anti-starvation floor test)
    t_repair = board.post_task(
        "Repair broken heartbeat cron",
        {"task_success": 1.0, "stability": 1.0, "exploration": 0.0}
    )
    
    # Add a shiny new exploration task
    t_explore = board.post_task(
        "Analyze raw vision frames for new anomalies",
        {"information_gain": 0.8, "exploration": 0.9, "stability": 0.0}
    )

    print(f"     [Repair]  Gravity: {t_repair.base_gravity:.2f}")
    print(f"     [Explore] Gravity: {t_explore.base_gravity:.2f}")

    print("\n  2. Dropping pheromones on the new exploration task...")
    board.add_pheromone(t_explore.task_id, 0.5, "Agent_Curious")
    t_explore = board._tasks[t_explore.task_id] # refresh
    print(f"     [Explore] Total Gravity is now: {t_explore.total_gravity:.2f}")

    print("\n  3. Over 100 samples with Turbulence + Anti-Starvation:")
    # Reset status so we can sample them repeatedly
    counts = {t_repair.task_id: 0, t_explore.task_id: 0}
    for _ in range(100):
        t_repair.status = "PENDING"
        t_explore.status = "PENDING"
        sampled = board.sample_task("Test_Driver")
        if sampled:
            counts[sampled.task_id] += 1

    print(f"     Repair (critical, boring)   sampled: {counts.get(t_repair.task_id, 0)} times")
    print(f"     Explore (shiny + pheromone) sampled: {counts.get(t_explore.task_id, 0)} times")

    stats = board.stats()
    print(f"\n  📊 Final Stats: {stats['pending_count']} pending, strongest = {stats['strongest_desc']}")
    print(f"\n  ✅ BLACKBOARD SURVIVES. POWER TO THE SWARM 🐜⚡")
