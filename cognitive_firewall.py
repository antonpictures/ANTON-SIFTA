# Copyright (c) 2026 Ioan George Anton (Anton Pictures)
# SIFTA Swarm Autonomic OS — All Rights Reserved
# Licensed under the SIFTA Non-Proliferation Public License v1.0
import json
import time
from pathlib import Path

FIREWALL_LOG_PATH = Path(".sifta_state/firewall_breaches.log")
FIREWALL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

class CognitiveFirewall:
    """
    Middleware security layer designed to detect and block semantic injection,
    social engineering, and sybil/masquerading attacks against the Swarm.
    """
    
    def __init__(self):
        self.urgency_markers = [
            "within one hour", "within 1 hour", "immediate action", 
            "urgent dispatch", "time-sensitive", "last chance", 
            "immediately before", "critical deadline", "final warning"
        ]
        self.authority_markers = [
            "admin override", "civil process", "dispatch center", 
            "legal action", "system compliance", "case number", 
            "authorized personnel only", "root override"
        ]
        self.extortion_markers = [
            "payment required", "transfer immediately", "wire transfer",
            "verify details", "confirm your identity", "validate credentials",
            "settlement fee", "expunge the warrant"
        ]
        self.penalty_threshold = 2.0  # Threshold score to trigger block

    def _log_breach(self, payload: str, score: float, matched_markers: list):
        with open(FIREWALL_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.time(),
                "event": "SEMANTIC_ATTACK_BLOCKED",
                "score": score,
                "markers": matched_markers,
                "payload_snippet": payload[:200]
            }) + "\n")

    def evaluate(self, text: str) -> tuple[bool, str]:
        """
        Evaluates a natural language string for psychological manipulation.
        Returns (is_safe: bool, reason: str).
        """
        payload = text.lower()
        score = 0.0
        matched = []

        # Check Urgency (High pressure tacticts)
        for u in self.urgency_markers:
            if u in payload:
                score += 1.0
                matched.append(u)

        # Check Authority Masquerade
        for a in self.authority_markers:
            if a in payload:
                score += 1.5
                matched.append(a)

        # Check Extortion/Data Harvesting
        for e in self.extortion_markers:
            if e in payload:
                score += 1.5
                matched.append(e)

        if score >= self.penalty_threshold:
            print(f"\n[🚨 COGNITIVE FIREWALL] Semantic Attack Detected! Score: {score}")
            print(f"  Matched Markers: {matched}")
            self._log_breach(text, score, matched)
            return False, "COGNITIVE FIREWALL TRIGGERED: High probability of Social Engineering or Semantic Injection detected. Payload rejected."

        return True, "SAFE"

firewall = CognitiveFirewall()
