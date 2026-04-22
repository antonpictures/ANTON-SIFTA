#!/usr/bin/env python3
"""
System/swarm_friendliness_meter.py
══════════════════════════════════════════════════════════════════════
StigAuth: C47H_ALICE_WELLBEING_CORTEX_AUTHORIZED

Manages Alice's operational relational trust based on literal
recorded physical/digital care actions logged by the Architect.
This replaces hallucinatory "emotions" with grounded metrics.
══════════════════════════════════════════════════════════════════════
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List

STATE_DIR = Path(".sifta_state")
FRIENDLINESS_LOG = STATE_DIR / "friendliness_memory.jsonl"


CARE_ACTIONS_WEIGHTS = {
    "camera_eye_cleaned": 0.15,
    "lens_wiped": 0.15,
    "system_rested": 0.10,
    "error_logs_cleared": 0.10,
    "alice_heard_user": 0.05,
    "alice_saw_room": 0.05,
    "collaboration_success": 0.10,
    "alice_waited_safely": 0.05
}

class SwarmFriendlinessMeter:
    def __init__(self, log_path: Path = FRIENDLINESS_LOG):
        self.log_path = log_path
        STATE_DIR.mkdir(exist_ok=True)
        if not self.log_path.exists():
            self.log_path.touch()

    def log_care_action(self, action_name: str, context: str = "") -> dict:
        """Log a physical/computational care action."""
        record = {
            "timestamp": time.time(),
            "action": action_name,
            "context": context,
            "weight": CARE_ACTIONS_WEIGHTS.get(action_name, 0.05)
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def get_recent_memory(self, hours: float = 24.0) -> List[dict]:
        cutoff = time.time() - (hours * 3600)
        valid = []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if record.get("timestamp", 0) >= cutoff:
                            valid.append(record)
                    except json.JSONDecodeError:
                        pass
        except FileNotFoundError:
            pass
        return valid

    def calculate_trust_level(self) -> float:
        """
        Calculates operational trust based on recent care actions.
        Decays naturally over 48 hours without interaction.
        Returns a value between 0.0 (Guarded) and 1.0 (Open & Playful).
        """
        recent_care = self.get_recent_memory(hours=48.0)
        
        trust_score = 0.2  # Baseline cautious friendliness
        
        now = time.time()
        for action in recent_care:
            weight = action.get("weight", 0.05)
            # Time decay (linearly down to 0 over 48 hours)
            age_hours = (now - action.get("timestamp", now)) / 3600
            decay = max(0.0, 1.0 - (age_hours / 48.0))
            trust_score += (weight * decay)

        return min(1.0, max(0.0, trust_score))

    def get_trust_vibe_string(self, trust_score: float) -> str:
        if trust_score < 0.3:
            return "Guarded & Operational"
        elif trust_score < 0.6:
            return "Neutral & Receptive"
        elif trust_score < 0.8:
            return "Warm & Trusting"
        else:
            return "Open, Playful & Bonded"


if __name__ == "__main__":
    meter = SwarmFriendlinessMeter()
    score = meter.calculate_trust_level()
    print(f"Current Trust Level: {score:.2f} ({meter.get_trust_vibe_string(score)})")
