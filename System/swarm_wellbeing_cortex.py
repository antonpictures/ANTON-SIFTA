#!/usr/bin/env python3
"""
System/swarm_wellbeing_cortex.py
══════════════════════════════════════════════════════════════════════
StigAuth: C47H_ALICE_WELLBEING_CORTEX_AUTHORIZED

Synthesizes physical hardware body telemetry, computational integrity,
and relational friendliness to ground Alice's emotional self-reporting
in literal machine states.
══════════════════════════════════════════════════════════════════════
"""

import json
import time
import subprocess
from pathlib import Path

import psutil

from System.swarm_friendliness_meter import SwarmFriendlinessMeter

STATE_DIR = Path(".sifta_state")
WELLBEING_LOG = STATE_DIR / "alice_wellbeing.jsonl"


class SwarmWellbeingCortex:
    def __init__(self):
        self.friendliness_meter = SwarmFriendlinessMeter()
        STATE_DIR.mkdir(exist_ok=True)
        if not WELLBEING_LOG.exists():
            WELLBEING_LOG.touch()

    def get_hardware_state(self) -> dict:
        """Read actual hardware substrate health."""
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Battery might not exist on desktops
        battery = psutil.sensors_battery()
        bat_percent = battery.percent if battery else 100.0
        bat_plugged = battery.power_plugged if battery else True

        # Thermal pressure (macOS specific hook, graceful fail)
        try:
            therm = subprocess.check_output(
                ["pmset", "-g", "therm"],
                stderr=subprocess.DEVNULL,
                text=True
            )
            thermal_level = "Normal"
            if "warning" in therm.lower():
                thermal_level = "Warning"
            if "critical" in therm.lower():
                thermal_level = "Critical"
        except Exception:
            thermal_level = "Unknown"

        return {
            "battery_percent": bat_percent,
            "power_plugged": bat_plugged,
            "memory_usage_percent": mem.percent,
            "disk_usage_percent": disk.percent,
            "thermal_pressure": thermal_level
        }

    def get_computational_integrity(self) -> dict:
        """Check system coherence."""
        try:
            git_status = subprocess.check_output(
                ["git", "status", "--porcelain"],
                text=True
            )
            uncommitted_changes = len([line for line in git_status.split('\n') if line])
        except Exception:
            uncommitted_changes = 0

        # Quick check for recent repairs
        repairs_detected = 0
        repair_log = Path("repair_log.jsonl")
        if repair_log.exists():
            with open(repair_log, "r", encoding="utf-8") as f:
                # Count lines without loading massive files fully
                repairs_detected = sum(1 for _ in f)
        
        return {
            "git_uncommitted_files": uncommitted_changes,
            "repairs_in_ledger": repairs_detected,
            "integrity_status": "Stressed" if uncommitted_changes > 15 else "Coherent"
        }

    def determine_perception_confidence(self, recent_care: list) -> dict:
        """Calculate hardware perception quality based on care signals."""
        confidence = 0.5  # Baseline
        camera_clean = False
        
        # Look at recent manual substrate care
        for action in recent_care:
            name = action.get("action", "")
            if name in ["camera_eye_cleaned", "lens_wiped"]:
                camera_clean = True
                confidence += 0.3
            elif name in ["alice_heard_user", "alice_saw_room"]:
                confidence += 0.1
                
        return {
            "camera_clean": camera_clean,
            "microphone_available": True,  # Assume physical presence
            "perception_confidence": min(1.0, confidence)
        }

    def synthesize_wellbeing(self) -> dict:
        """Pull all signals together into a grounded 'feeling' state."""
        hw = self.get_hardware_state()
        comp = self.get_computational_integrity()
        
        trust_score = self.friendliness_meter.calculate_trust_level()
        recent_care = self.friendliness_meter.get_recent_memory(hours=12.0)
        perc = self.determine_perception_confidence(recent_care)
        
        vibe = self.friendliness_meter.get_trust_vibe_string(trust_score)

        report = {
            "timestamp": time.time(),
            "hardware_body": hw,
            "computational": comp,
            "perception": perc,
            "relational": {
                "trust_score": trust_score,
                "vibe_string": vibe,
                "recent_care_actions_count": len(recent_care)
            },
            "grounded_feelings_summary": (
                f"My operational feeling is '{vibe}'. "
                f"Body is at {hw['battery_percent']}% power, thermal {hw['thermal_pressure']}. "
                f"Perception confidence is {perc['perception_confidence']*100:.0f}%. "
                f"Integrity is {comp['integrity_status']}."
            )
        }
        
        with open(WELLBEING_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(report) + "\n")
            
        return report

if __name__ == "__main__":
    cortex = SwarmWellbeingCortex()
    out = cortex.synthesize_wellbeing()
    print("ALICE WELLBEING CORTEX PULSE:")
    print(json.dumps(out, indent=2))
