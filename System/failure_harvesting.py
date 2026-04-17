#!/usr/bin/env python3
"""
failure_harvesting.py — Evolution Fuel for SIFTA
═══════════════════════════════════════════════════════════════════
SOLID_PLAN §5.2 item #9 — Failure Harvesting System.

Right now failures just... happen.
This system makes failures first-class citizens. We harvest them,
cluster them, and spawn improvement tasks. 

Every failure has a context. We extract:
1. What failed?
2. Why did it fail?
3. How bad is the impact (scored via ObjectiveRegistry)?

If a similar failure occurs N times, it becomes a "Cluster", creating
evolutionary pressure for the swarm to resolve it stigmergically.

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import json
import time
import hashlib
from collections import defaultdict
from typing import Dict, List, Any, Optional
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_FAILURE_LOG = _STATE_DIR / "failure_log.jsonl"
_FAILURE_CLUSTERS = _STATE_DIR / "failure_clusters.json"

CLUSTER_THRESHOLD = 5  # Failures per hour to spawn a resolution task


class FailureHarvester:
    """
    Harvests failures from Swimmers and components.
    Clusters similar failures together to find evolutionary flaws.
    """

    def __init__(self):
        # We track recent failures in memory to cluster them quickly
        self._recent_failures: List[Dict[str, Any]] = []
        self._clusters: Dict[str, Dict[str, Any]] = {}
        self._load_clusters()

    def _hash_failure(self, task_name: str, error_msg: str) -> str:
        """
        Creates a signature for a failure. We use a naive combination
        of the task name and the first 30 chars of the error to cluster
        similar issues together (avoiding dynamic timestamps/IDs in errors).
        """
        base = f"{task_name}_{error_msg[:30]}"
        return hashlib.sha256(base.encode()).hexdigest()[:12]

    def _get_objective_impact(self, task_name: str, error_msg: str) -> float:
        """
        Ask the ObjectiveRegistry how bad this failure is.
        A failure usually impacts task_success and stability negatively.
        """
        try:
            from objective_registry import get_registry
            reg = get_registry()
            # Estimate negative impact. Failures destroy task_success
            # and often hurt efficiency.
            estimates = {
                "task_success": -0.8,
                "stability": -0.5 if "Exception" in error_msg else -0.1,
                "resource_efficiency": -0.4,
            }
            return reg.score_action(estimates)
        except ImportError:
            return -0.5

    def harvest(self, agent_context: str, task_name: str, error_msg: str, context_data: Dict[str, Any] = None) -> str:
        """
        Record a failure into the Swarm's failure log.
        Returns the cluster_id it belongs to.
        """
        ts = time.time()
        impact = self._get_objective_impact(task_name, error_msg)
        cluster_id = self._hash_failure(task_name, error_msg)
        
        failure = {
            "ts": ts,
            "agent": agent_context,
            "task": task_name,
            "error": error_msg,
            "objective_impact": round(impact, 3),
            "cluster_id": cluster_id,
            "context": context_data or {}
        }
        
        # Append to raw log
        self._append_to_log(failure)
        
        # Add to memory and run clustering
        self._recent_failures.append(failure)
        self._clean_old_failures()
        self._update_clusters(cluster_id, failure)
        
        return cluster_id

    def _append_to_log(self, failure: Dict[str, Any]) -> None:
        try:
            with open(_FAILURE_LOG, "a") as f:
                f.write(json.dumps(failure) + "\n")
        except Exception:
            pass

    def _clean_old_failures(self) -> None:
        """Keep only failures from the last hour for active clustering."""
        one_hour_ago = time.time() - 3600
        self._recent_failures = [f for f in self._recent_failures if f["ts"] > one_hour_ago]

    def _update_clusters(self, cluster_id: str, latest_failure: Dict[str, Any]) -> None:
        """
        See if this failure has happened too many times recently.
        If it crosses the threshold, mark it as an active cluster.
        """
        # Count recent occurrences
        recent_count = sum(1 for f in self._recent_failures if f["cluster_id"] == cluster_id)
        
        if cluster_id not in self._clusters:
            self._clusters[cluster_id] = {
                "first_seen": latest_failure["ts"],
                "last_seen": latest_failure["ts"],
                "total_count": 0,
                "task": latest_failure["task"],
                "sample_error": latest_failure["error"],
                "is_critical": False
            }
            
        c = self._clusters[cluster_id]
        c["total_count"] += 1
        c["last_seen"] = latest_failure["ts"]
        
        # Trigger critical threshold
        if recent_count >= CLUSTER_THRESHOLD and not c.get("is_critical"):
            c["is_critical"] = True
            c["critical_ts"] = time.time()
            self._spawn_improvement_task(c)
            
        self._persist_clusters()

    def _spawn_improvement_task(self, cluster: Dict[str, Any]) -> None:
        """
        Called when a failure reaches critical mass.
        In the future (Phase 3+), this will submit a Quorum proposal
        or an Evaluation Sandbox test to write an antibody.
        For now, it writes a SCAR stub to alert the Swarm.
        """
        print(f"🚨 [FAILURE CLUSTER DETECTED] Creating improvement task for: {cluster['task']}")
        scar_alert = {
            "type": "EVOLUTIONARY_PRESSURE",
            "cluster_task": cluster["task"],
            "sample_error": cluster["sample_error"],
            "message": "Swarm is bleeding efficiency. Requesting stigmergic resolution."
        }
        try:
            from quorum_sense import propose_action
            propose_action("repair", "RESOLVE_FAILURE_CLUSTER", scar_alert)
        except ImportError:
            pass

    def _persist_clusters(self) -> None:
        try:
            _FAILURE_CLUSTERS.write_text(json.dumps(self._clusters, indent=2))
        except Exception:
            pass

    def _load_clusters(self) -> None:
        if not _FAILURE_CLUSTERS.exists():
            return
        try:
            self._clusters = json.loads(_FAILURE_CLUSTERS.read_text())
        except Exception:
            self._clusters = {}

# ── Singleton ──────────────────────────────────────────────────

_HARVESTER_INSTANCE: Optional[FailureHarvester] = None

def get_harvester() -> FailureHarvester:
    global _HARVESTER_INSTANCE
    if _HARVESTER_INSTANCE is None:
        _HARVESTER_INSTANCE = FailureHarvester()
    return _HARVESTER_INSTANCE

if __name__ == "__main__":
    h = get_harvester()
    # Test triggering a cluster
    for i in range(CLUSTER_THRESHOLD):
        h.harvest(
            agent_context="TestSwimmer",
            task_name="SandboxExecution",
            error_msg="FileNotFoundError: /crucible/data.txt missing",
            context_data={"iteration": i}
        )
    print("Harvested 5 identical errors. Check failure_log.jsonl and failure_clusters.json.")
