#!/usr/bin/env python3
"""
contradiction_engine.py — The Immune System for Beliefs
═══════════════════════════════════════════════════════════════════
SOLID_PLAN §5.2 item #4 — Contradiction Engine.

The Blackboard is the Swarm's shared memory. Swimmers write beliefs
onto it. But two Swimmers can write OPPOSITE beliefs about the same
thing and nobody catches it. Example:

  SCOUT writes:    { "port_4444": "open" }
  SENTINEL writes: { "port_4444": "closed" }
  
The Swarm now has two contradicting "facts." Without resolution,
any agent that reads the Blackboard gets corrupted state.

This engine:
  1. Scans the Swarm's state files for contradictions
  2. Scores severity using the ObjectiveRegistry
  3. If a contradiction exceeds severity threshold → routes to FailureHarvester
     and flags for human-gate or Quorum resolution

Grok's insight: "Stigmergy without rules is noise soup."
This is the contradiction antidote.

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_CONTRADICTION_LOG = _STATE_DIR / "contradiction_log.jsonl"
_CONTRADICTION_REGISTRY = _STATE_DIR / "contradiction_registry.json"

# Keys we always expect to be authoritative singletons — any split here
# is HIGH severity by default  
_SINGLETON_KEYS = {
    "port", "identity", "genesis", "owner", "node_serial",
    "master_key", "active_mission", "quorum_state"
}


class ContradictionEngine:
    """
    Scans the Swarm's belief state for contradictions.
    
    A contradiction is when two agents have written different non-null
    values for the same semantic key, and those values conflict.
    
    Severity tiers:
      CRITICAL (0.8-1.0): Identity, cryptographic roots, ports — resolve NOW
      HIGH     (0.5-0.8): Agent status, mission state
      LOW      (0.0-0.5): Soft facts, preference traces
    """

    SEVERITY_THRESHOLD = 0.5  # Below this → log only. Above → escalate.

    def __init__(self):
        self._active: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ── Core scan API ─────────────────────────────────────────────

    def scan_beliefs(self, beliefs: Dict[str, Any], source_a: str,
                     source_b: str) -> List[Dict[str, Any]]:
        """
        Compare two belief dicts (from two different agents/files).
        Return list of detected contradictions.

        Args:
            beliefs: merged dict of {key: {agent_a: val, agent_b: val}}
            source_a: name of first source (e.g. "M1THER.json")
            source_b: name of second source (e.g. "M5SIFTA_BODY.json")

        Returns:
            List of contradiction records
        """
        found = []
        for key, values in beliefs.items():
            if len(set(str(v) for v in values.values())) <= 1:
                continue  # All agree — no contradiction

            val_a = values.get(source_a)
            val_b = values.get(source_b)
            if val_a is None or val_b is None:
                continue  # Missing key, not a conflict

            severity = self._severity(key, val_a, val_b)
            c_id = self._contradiction_id(key, source_a, source_b)

            record = {
                "id": c_id,
                "key": key,
                "source_a": source_a,
                "source_b": source_b,
                "val_a": str(val_a)[:120],
                "val_b": str(val_b)[:120],
                "severity": round(severity, 3),
                "ts": time.time(),
                "resolved": False,
            }
            found.append(record)
            self._ingest(record)

        return found

    def scan_state_files(self, file_a: str, file_b: str,
                         watch_keys: Optional[List[str]] = None
                         ) -> List[Dict[str, Any]]:
        """
        Load two .sifta_state JSON files and scan their shared keys.

        Args:
            file_a, file_b: filenames relative to .sifta_state/
            watch_keys: if provided, only scan these keys
        """
        path_a = _STATE_DIR / file_a
        path_b = _STATE_DIR / file_b
        if not path_a.exists() or not path_b.exists():
            return []

        try:
            data_a = json.loads(path_a.read_text())
            data_b = json.loads(path_b.read_text())
        except Exception:
            return []

        # Build merged belief map for shared keys
        beliefs: Dict[str, Dict[str, Any]] = {}
        all_keys = set(data_a.keys()) & set(data_b.keys())
        if watch_keys:
            all_keys &= set(watch_keys)

        for k in all_keys:
            beliefs[k] = {file_a: data_a[k], file_b: data_b[k]}

        return self.scan_beliefs(beliefs, file_a, file_b)

    def assert_belief(self, agent: str, key: str, value: Any,
                      existing_beliefs: Optional[Dict[str, Any]] = None
                      ) -> Tuple[bool, str]:
        """
        Let an agent assert a new belief. If it contradicts existing
        registry belief, flag before writing.

        Returns:
            (is_safe_to_write, reason_message)
        """
        if existing_beliefs and key in existing_beliefs:
            old_val = existing_beliefs[key]
            if str(old_val) != str(value):
                severity = self._severity(key, old_val, value)
                if severity >= self.SEVERITY_THRESHOLD:
                    c_id = self._contradiction_id(key, "existing_beliefs", agent)
                    self._ingest({
                        "id": c_id,
                        "key": key,
                        "source_a": "existing_beliefs",
                        "source_b": agent,
                        "val_a": str(old_val)[:120],
                        "val_b": str(value)[:120],
                        "severity": round(severity, 3),
                        "ts": time.time(),
                        "resolved": False,
                    })
                    return False, f"[CONTRADICTION] Key '{key}': existing={old_val!r} vs {agent}={value!r} (severity={severity:.2f})"
        return True, "ok"

    # ── Internal helpers ──────────────────────────────────────────

    def _severity(self, key: str, val_a: Any, val_b: Any) -> float:
        """
        Score how severe this contradiction is [0, 1].
        Uses ObjectiveRegistry to weight impact on stability.
        """
        base = 0.2

        # Key-based severity
        lower = key.lower()
        for singleton in _SINGLETON_KEYS:
            if singleton in lower:
                base += 0.4
                break

        # Type mismatch is more confusing than value mismatch
        if type(val_a) != type(val_b):
            base += 0.2

        # Boolean flip is high-severity (e.g. open/closed, alive/dead)
        if isinstance(val_a, bool) and isinstance(val_b, bool):
            base += 0.3

        # ObjectiveRegistry: how does this hit stability?
        try:
            from objective_registry import get_registry
            reg = get_registry()
            # A contradiction always hurts stability and information quality
            impact_score = reg.score_action({
                "task_success": -0.3,
                "stability": -base,
                "information_gain": -0.2,
            })
            # Normalise: impact_score is in [-1, 0], turn into [0, 1]
            base = min(1.0, base + abs(impact_score) * 0.3)
        except ImportError:
            pass

        return min(1.0, base)

    def _contradiction_id(self, key: str, a: str, b: str) -> str:
        raw = f"{key}_{a}_{b}"
        return hashlib.sha256(raw.encode()).hexdigest()[:10]

    def _ingest(self, record: Dict[str, Any]) -> None:
        """Record contradiction and escalate if severe enough."""
        c_id = record["id"]

        # Upsert into active registry
        self._active[c_id] = record
        self._persist()

        # Write to append log
        try:
            with open(_CONTRADICTION_LOG, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass

        # Route severe contradictions to Failure Harvester
        if record["severity"] >= self.SEVERITY_THRESHOLD:
            self._escalate(record)

    def _escalate(self, record: Dict[str, Any]) -> None:
        """
        Severe contradiction: route to FailureHarvester and optionally
        propose a Quorum resolution task.
        """
        print(f"⚡ [CONTRADICTION DETECTED] key='{record['key']}' "
              f"severity={record['severity']:.2f} | "
              f"{record['source_a']}={record['val_a']!r} vs "
              f"{record['source_b']}={record['val_b']!r}")

        # Feed into Failure Harvesting so it counts toward evolutionary pressure
        try:
            try:
                from System.failure_harvesting import get_harvester
            except ImportError:
                from failure_harvesting import get_harvester
            get_harvester().harvest(
                agent_context="ContradictionEngine",
                task_name=f"Contradiction_{record['key']}",
                error_msg=f"{record['source_a']}={record['val_a']!r} "
                          f"vs {record['source_b']}={record['val_b']!r}",
                context_data=record,
            )
        except ImportError:
            pass

    def resolve(self, c_id: str, winning_value: Any, resolver: str = "human_gate") -> bool:
        """
        Mark a contradiction as resolved. Call this from the Neural Gate
        or Quorum after the Architect picks the authoritative value.
        """
        if c_id not in self._active:
            return False
        self._active[c_id]["resolved"] = True
        self._active[c_id]["resolved_by"] = resolver
        self._active[c_id]["winning_value"] = str(winning_value)
        self._active[c_id]["resolved_ts"] = time.time()
        self._persist()
        return True

    # ── Status & diagnostics ──────────────────────────────────────

    def open_contradictions(self) -> List[Dict[str, Any]]:
        """All unresolved contradictions, sorted by severity desc."""
        return sorted(
            [c for c in self._active.values() if not c.get("resolved")],
            key=lambda x: x["severity"],
            reverse=True,
        )

    def __repr__(self) -> str:
        open_c = len(self.open_contradictions())
        return f"<ContradictionEngine open={open_c} total={len(self._active)}>"

    # ── Persistence ───────────────────────────────────────────────

    def _persist(self) -> None:
        try:
            _CONTRADICTION_REGISTRY.write_text(
                json.dumps(self._active, indent=2)
            )
        except Exception:
            pass

    def _load(self) -> None:
        if not _CONTRADICTION_REGISTRY.exists():
            return
        try:
            self._active = json.loads(_CONTRADICTION_REGISTRY.read_text())
        except Exception:
            self._active = {}


# ── Singleton ──────────────────────────────────────────────────

_ENGINE_INSTANCE: Optional[ContradictionEngine] = None

def get_engine() -> ContradictionEngine:
    global _ENGINE_INSTANCE
    if _ENGINE_INSTANCE is None:
        _ENGINE_INSTANCE = ContradictionEngine()
    return _ENGINE_INSTANCE


if __name__ == "__main__":
    engine = get_engine()

    # Simulate PORT contradiction — two swimmers disagree on port status
    contradictions = engine.scan_beliefs(
        beliefs={
            "port_4444": {"SCOUT.json": "open", "SENTINEL.json": "closed"},
            "status":    {"SCOUT.json": "alive", "SENTINEL.json": "alive"},  # agree
            "identity":  {"SCOUT.json": "scout_01", "SENTINEL.json": "medic_99"},
        },
        source_a="SCOUT.json",
        source_b="SENTINEL.json",
    )

    print(f"\nFound {len(contradictions)} contradictions:\n")
    for c in contradictions:
        print(f"  [{c['severity']:.2f}] key='{c['key']}': "
              f"{c['source_a']}={c['val_a']!r} vs {c['source_b']}={c['val_b']!r}")

    print(f"\nEngine: {engine}")
    print(f"Open contradictions: {len(engine.open_contradictions())}")
