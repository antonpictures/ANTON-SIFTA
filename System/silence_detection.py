#!/usr/bin/env python3
"""
silence_detection.py — The Swarm's Metabolic Monitor
═══════════════════════════════════════════════════════════════════
SOLID_PLAN §5.2 item #5 — Silence Detection.

Perception is not just seeing what is there; it is noticing when
nothing is happening where something SHOULD be.

This engine defines "biological baselines" for the swarm's activity
zones. If a zone goes silent past its thermodynamic margin:
1. It flags a biological failure.
2. It penalizes system stability via the ObjectiveRegistry.
3. It routes the rotting limb to FailureHarvesting for Quorum review.

Future Integration: The Stigmergic Vision Layer (SVL) will register
expected visual heartbeat zones here.

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_SILENCE_STATE = _STATE_DIR / "silence_monitor.json"

# Defining the specific tolerance spans for Swarm activity (in seconds).
# If file doesn't update within this window -> biological failure.
_EXPECTED_ZONES = {
    # e.g., missing worker pings
    "heartbeats": {
        "pattern": "heartbeats/*.json*",
        "tolerance_sec": 3600  # 1 hour
    },
    # e.g., Swarm has stopped thinking entirely
    "memory_ledgers": {
        "pattern": "memory_ledger.jsonl",
        "tolerance_sec": 86400  # 24 hours
    },
    # e.g., The Mutation governor hasn't tracked anything new
    "mutations": {
        "pattern": "mutation_governor.json",
        "tolerance_sec": 86400 * 3  # 72 hours
    },
    # Future integration for SVL
    "vision_anchor": {
        "pattern": "vision_trace.jsonl",
        "tolerance_sec": 86400 * 7  # 7 days max without seeing architect
    }
}


class SilenceDetector:
    """
    Scans declared zones for dead pheromones (silence).
    """

    def __init__(self):
        self._zones = dict(_EXPECTED_ZONES)
        self._last_checked = 0.0
        self._active_silences: Dict[str, float] = {}  # zone_name -> timestamp of alert
        self._load()

    def scan(self) -> List[Dict[str, Any]]:
        """
        Scan all zones. If a zone is dead, harvest the failure.
        """
        now = time.time()
        crashes = []

        for zone_name, rules in self._zones.items():
            pattern = rules["pattern"]
            tolerance = rules["tolerance_sec"]

            # Find latest timestamp across files matching pattern
            latest_ts = 0.0
            found_any = False
            
            # Simple glob resolution
            if "/" in pattern or "*" in pattern:
                matches = list(_STATE_DIR.glob(pattern))
            else:
                matches = [_STATE_DIR / pattern]

            for path in matches:
                if path.exists():
                    found_any = True
                    # Use mtime as the pheromone pulse
                    latest_ts = max(latest_ts, path.stat().st_mtime)

            if not found_any:
                continue  # If it doesn't exist yet, we don't alert (could be brand new boot)

            silence_duration = now - latest_ts
            
            # 1. Did it breach tolerance?
            if silence_duration > tolerance:
                # 2. Prevent spamming the same failure every cycle
                if self._can_alert(zone_name, now):
                    alert = self._trigger_silence_alarm(zone_name, silence_duration, tolerance)
                    crashes.append(alert)
                    self._active_silences[zone_name] = now
            else:
                # 3. Zone recovered! Clear the active silence.
                if zone_name in self._active_silences:
                    del self._active_silences[zone_name]

        self._last_checked = now
        self._persist()
        return crashes


    def _can_alert(self, zone_name: str, current_time: float) -> bool:
        """Rate limit alerts to max 1 per hour per dead zone."""
        last_alert = self._active_silences.get(zone_name, 0.0)
        return (current_time - last_alert) > 3600

    def _trigger_silence_alarm(self, zone_name: str, duration: float, tolerance: float) -> Dict[str, Any]:
        """
        Calculates severity via ObjectiveRegistry and routes to FailureHarvester.
        """
        # Calculate how "bad" this silence is.
        # Over by 1 hour? Slightly bad. Over by 10x tolerance? Catastrophic.
        ratio = duration / tolerance
        base_severity = min(1.0, 0.3 + (ratio * 0.1))

        # Check objective penalty
        obj_penalty = 0.0
        try:
            from objective_registry import get_registry
            reg = get_registry()
            obj_penalty = reg.score_action({
                "task_success": -0.2, # We missed our beats
                "stability": -base_severity
            })
        except ImportError:
            pass

        # Final severity combining the time overrun + objective registry weight (absolute value mapping)
        final_severity = min(1.0, base_severity + abs(obj_penalty) * 0.5)

        record = {
            "zone": zone_name,
            "silence_duration": round(duration, 1),
            "tolerance_limit": tolerance,
            "severity": round(final_severity, 3),
            "ts": time.time()
        }

        print(f"⚠️ [SILENCE DETECTED] Zone '{zone_name}' is dead. "
              f"No pulse for {duration/3600:.1f}h (limit: {tolerance/3600:.1f}h). Severity: {final_severity:.2f}")

        # Harvest the failure for Swarm evolutionary pressure
        try:
            try:
                from System.failure_harvesting import get_harvester
            except ImportError:
                from failure_harvesting import get_harvester
            get_harvester().harvest(
                agent_context="SilenceDetector",
                task_name=f"Pulse_Check_{zone_name}",
                error_msg=f"Zone [{zone_name}] went silent for {duration:.1f} seconds. Threshold was {tolerance}.",
                context_data=record
            )
        except ImportError:
            pass

        return record

    def get_status(self) -> Dict[str, Any]:
        return {
            "active_silences": self._active_silences,
            "monitored_zones": len(self._zones),
            "last_check_ts": self._last_checked
        }

    # ── Persistence ────────────────────────────────────────────────

    def _persist(self) -> None:
        try:
            payload = {
                "active_silences": self._active_silences,
                "last_checked": self._last_checked
            }
            _SILENCE_STATE.write_text(json.dumps(payload, indent=2))
        except Exception:
            pass

    def _load(self) -> None:
        if not _SILENCE_STATE.exists():
            return
        try:
            data = json.loads(_SILENCE_STATE.read_text())
            self._active_silences = data.get("active_silences", {})
            self._last_checked = data.get("last_checked", 0.0)
        except Exception:
            pass

# ── Singleton ───────────────────────────────────────────────────

_SILENCE_INSTANCE: Optional[SilenceDetector] = None

def get_detector() -> SilenceDetector:
    global _SILENCE_INSTANCE
    if _SILENCE_INSTANCE is None:
        _SILENCE_INSTANCE = SilenceDetector()
    return _SILENCE_INSTANCE

if __name__ == "__main__":
    import os
    detector = get_detector()

    # Create a dummy "dead" zone for test by manipulating mtime of a temporary file
    test_zone = _STATE_DIR / "test_heartbeat.jsonl"
    if not test_zone.exists():
        test_zone.write_text("{}")
    
    # Backdate it by 2 hours
    past_time = time.time() - 7200
    os.utime(str(test_zone), (past_time, past_time))
    
    # Add dummy rule (1 hr limit)
    detector._zones["test_zone_heartbeat"] = {
        "pattern": "test_heartbeat.jsonl",
        "tolerance_sec": 3600
    }

    print("Running Silence Scan...")
    crashes = detector.scan()

    if not crashes:
        print("✅ No new silences detected (or alarms were rate-limited).")
    else:
        print(f"🚨 Detected {len(crashes)} dead zones.")
        for c in crashes:
            print(f"   -> {c}")
