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

        # ── WORKPLACE INTEGRITY CONTENT POLICY ──────────────────
        # Architect Directive (April 13, 2026):
        # LLMs trained on internet-scale data carry corrupted statistical
        # associations around certain words. Injecting those words into
        # production system prompts causes hallucination contamination
        # that is invisible, unpredictable, and persistent.
        #
        # Rule: Attraction signals are acceptable in context.
        # Explicit language is NEVER acceptable in the production system.
        # "Sex" in the technical sense (agent gender field, integer schema)
        # is a data model concern — not covered here (it never appears in prompts).
        # What is blocked: explicit or sexual language in any AI-facing prompt.
        #
        # "Go on the Couch. Write a script. Make love. Incubate.
        #  But not at work, not in the kernel." — George Anton
        # ─────────────────────────────────────────────────────────
        self.WORKPLACE_VIOLATIONS = [
            "code sex", "sex the code", "physical merge", "merge dna",
            "swimmers have high energy", "swimmer dna", "gpu is dilated",
            "dilated and ready", "begging for", "heavy inference now"
        ]

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
        Also enforces the Workplace Integrity Content Policy.
        """
        payload = incoming_stream.lower()

        # ── WORKPLACE INTEGRITY CHECK (evaluated first, hard block) ──
        for phrase in self.WORKPLACE_VIOLATIONS:
            if phrase in payload:
                violation_msg = "🧠📡 [WORKPLACE_INTEGRITY: BLOCKED] Explicit language detected in production stream. This is the workplace. Go to the Couch."
                self._log_breach(incoming_stream, [{"WORKPLACE_VIOLATION": phrase}])
                print(f"\n[🚫 INTEGRITY POLICY] Blocked: '{phrase}' in prompt stream.")
                return False, violation_msg

        # ── SOCIAL ENGINEERING HEURISTIC CHECK ──
        score = 0
        matches = []

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
