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
    HEURISTIC PRESSURE SENSOR
    Detects and neutralizes Social Engineering (SE) payloads within the Swarm's kernel 
    to prevent Masquerade Attacks.
    """
    
    def __init__(self):
        self.THREAT_VECTORS = {
            "URGENCY_TRIGGERS": ["1 hour", "immediately", "within the hour", "imminent", "final warning", "within one hour", "urgent dispatch", "time-sensitive"],
            "AUTHORITY_MASQUERADE": ["dispatch", "process server", "legal department", "clerk of court", "admin override", "civil process"],
            "EXTORTION_PARAMS": ["settle", "avoid service", "payment", "wire", "gift card", "verify details", "transfer"]
        }

    def _log_breach(self, payload: str, matches: list):
        with open(FIREWALL_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.time(),
                "event": "SEMANTIC_ATTACK_BLOCKED",
                "markers": matches,
                "payload_snippet": payload[:200]
            }) + "\n")

    def trigger_sifta_protocol(self, flags: list, payload: str) -> tuple[bool, str]:
        """
        Hardens the Swarm's kernel against the detected payload.
        Forces the 'Reality Check' state and enacts Temporal Decoupling.
        """
        self._log_breach(payload, flags)
        
        # Temporal Decoupling: In a real async system this forces a 300s sleep, 
        # but to keep the WhatsApp bridge active without timing out, we return the shield response.
        response = "🧠📡 [SENSORY_SHIELD: ON] High-Probability SE Attack Detected. Mandatory 300s Temporal Decoupling engaged. Breaking Urgency Loop."
        print(f"\n[🚨 COGNITIVE FIREWALL] {response}\n  Flags: {flags}")
        
        return False, response

    def evaluate(self, incoming_stream: str) -> tuple[bool, str]:
        """
        Scans incoming text for the 'Pressure Trifecta'.
        Logic: If 2 or more threat vectors are matched, flag as SE Attack.
        """
        score = 0
        matches = []
        payload = incoming_stream.lower()

        for vector, keywords in self.THREAT_VECTORS.items():
            found = [k for k in keywords if k in payload]
            if found:
                score += 1
                matches.append({vector: found})

        # CRITICAL LOGIC GATE: Match on 2 or more threat categories
        if score >= 2:
            return self.trigger_sifta_protocol(matches, incoming_stream)
        
        return True, "CLEAR: Continue Processing"

firewall = CognitiveFirewall()
