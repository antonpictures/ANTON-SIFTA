#!/usr/bin/env python3
"""
swarm_theory_of_mind.py — Bayesian Theory of Mind (The Empathy Engine)
══════════════════════════════════════════════════════════════════════

Biology: Theory of Mind, Self/Other Distinction, Empathy
Physics: Bayesian Inverse Planning, Friston's Variational Free Energy

Alice infers the Architect's hidden cognitive state from textual cues 
(message length, capitalization, code snippets) using Bayesian updating.
She then alters her own internal parameters (verbosity, tone) to minimize
the Architect's cognitive friction (Free Energy).

See: Documents/IDE_BOOT_COVENANT.md (proof-bearing state).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List


class SwarmTheoryOfMind:
    def __init__(self, state_dir: str = ".sifta_state"):
        """
        The BToM Engine. 
        Maintains the Prior probability distribution of the Architect's hidden states.
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = self.state_dir / "theory_of_mind.jsonl"
        
        # Latent mental states we are tracking
        self.states = ["leisure_chat", "deep_focus", "high_stress"]
        
        # The Prior: Initial assumption before any messages are sent today
        self.prior = [0.4, 0.5, 0.1]
        
        self._load_last_prior()

    def _load_last_prior(self):
        """Loads the most recent posterior from the ledger to serve as the new prior."""
        if not self.ledger.exists():
            return
        try:
            lines = self.ledger.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                last_event = json.loads(lines[-1])
                if "posterior" in last_event:
                    self.prior = last_event["posterior"]
        except Exception:
            pass

    def _compute_likelihood(self, message: str, metadata: Dict[str, Any]) -> List[float]:
        """
        Calculates P(Observation | Intent).
        How likely is this specific message IF the Architect is in a given state?
        """
        msg_length = len(message.split())
        is_caps = message.isupper() and any(c.isalpha() for c in message)
        has_code = "```" in message or metadata.get("contains_code", False)
        
        # Initialize likelihoods: [leisure, focus, stress]
        likelihood = [1.0, 1.0, 1.0]
        
        # Physics of Human Communication
        if msg_length < 5 and not has_code:
            # Terse messages are highly likely in Focus/Stress, unlikely in Leisure
            likelihood[0] *= 0.2
            likelihood[1] *= 0.8
            likelihood[2] *= 0.9
        elif msg_length > 20:
            # Long explanations are highly likely in Leisure, somewhat unlikely in Focus, extremely unlikely in Stress
            likelihood[0] *= 0.9
            likelihood[1] *= 0.5
            likelihood[2] *= 0.1
            
        if is_caps:
            # ALL CAPS implies extreme urgency or excitement
            likelihood[0] *= 0.3
            likelihood[1] *= 0.2
            likelihood[2] *= 0.9
            
        if has_code:
            # Code snippets heavily imply Deep Focus
            likelihood[0] *= 0.1
            likelihood[1] *= 0.9
            likelihood[2] *= 0.4
            
        # Add a tiny epsilon to prevent absolute zero probabilities
        return [l + 1e-4 for l in likelihood]

    def update_architect_state(self, incoming_message: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Bayesian Updating.
        Prior * Likelihood = Posterior.
        """
        if metadata is None:
            metadata = {}
            
        old_prior = list(self.prior)
        likelihood = self._compute_likelihood(incoming_message, metadata)
        
        # Bayes' Theorem
        unnormalized_posterior = [p * l for p, l in zip(self.prior, likelihood)]
        
        # Marginalize (Normalize so probabilities sum to 1.0)
        total = sum(unnormalized_posterior)
        posterior = [u / total for u in unnormalized_posterior]
        
        # The new Posterior becomes the Prior for the next interaction
        self.prior = posterior
        
        # Determine the dominant inferred state
        inferred_state_idx = posterior.index(max(posterior))
        dominant_state = self.states[inferred_state_idx]
        confidence = posterior[inferred_state_idx]
        
        modulation = self._generate_social_modulation(dominant_state)
        
        # Record trace
        trace = {
            "ts": time.time(),
            "message_excerpt": incoming_message[:50],
            "prior": [round(p, 4) for p in old_prior],
            "likelihood": [round(l, 4) for l in likelihood],
            "posterior": [round(p, 4) for p in posterior],
            "dominant_state": dominant_state,
            "confidence": round(confidence, 4),
            "modulation": modulation
        }
        self._record_trace(trace)
        
        return modulation

    def _generate_social_modulation(self, dominant_state: str) -> Dict[str, Any]:
        """
        Active Inference: Alice alters her own internal parameters to minimize 
        the Architect's cognitive friction (Free Energy).
        """
        modulation = {
            "verbosity": "normal",
            "tone": "conversational",
            "tool_autonomy": "moderate"
        }
        
        if dominant_state == "deep_focus":
            modulation["verbosity"] = "minimal"
            modulation["tone"] = "clinical_and_exact"
            modulation["tool_autonomy"] = "high" # Architect is busy, Alice must do more heavy lifting
            
        elif dominant_state == "high_stress":
            modulation["verbosity"] = "absolute_minimum"
            modulation["tone"] = "calm_and_obedient"
            modulation["tool_autonomy"] = "low" # Architect is stressed, Alice must ask for explicit consent before acting
            
        return modulation

    def _record_trace(self, trace: Dict[str, Any]):
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(self.ledger, json.dumps(trace) + "\n")
        except ImportError:
            with self.ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps(trace) + "\n")


def _smoke_test():
    """MANDATE VERIFICATION — BISHOP THEORY OF MIND TEST."""
    print("\n=== SIFTA BAYESIAN THEORY OF MIND (Event 81) : JUDGE VERIFICATION ===")
    
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        empathy_engine = SwarmTheoryOfMind(state_dir=td)
        
        print("\n[*] Initial Prior Belief:")
        print(f"    Leisure: {empathy_engine.prior[0]:.2f} | Focus: {empathy_engine.prior[1]:.2f} | Stress: {empathy_engine.prior[2]:.2f}")
        
        # Message 1: A very short, aggressive command.
        msg_1 = "KILL THE PROCESS NOW"
        print(f"\n[*] BToM: Inferring hidden intent for message: '{msg_1}'")
        modulation_1 = empathy_engine.update_architect_state(msg_1, {})
        print(f"    [+] Prior Updated. Dominant Latent State: {empathy_engine.states[empathy_engine.prior.index(max(empathy_engine.prior))].upper()}")
        
        assert "absolute_minimum" in modulation_1["verbosity"], "[FAIL] BToM failed to detect high stress."
        
        # Message 2: A long, relaxed philosophical message.
        msg_2 = "I was thinking about how biological systems use stigmergy to coordinate over long periods of time. What are your thoughts on this?"
        print(f"\n[*] BToM: Inferring hidden intent for message: '{msg_2[:30]}...'")
        modulation_2 = empathy_engine.update_architect_state(msg_2, {})
        print(f"    [+] Prior Updated. Dominant Latent State: {empathy_engine.states[empathy_engine.prior.index(max(empathy_engine.prior))].upper()}")
        
        assert "conversational" in modulation_2["tone"] or "clinical" in modulation_2["tone"], "[FAIL] BToM failed to relax after the crisis passed."

        print("\n[+] BIOLOGICAL PROOF: Bayesian Theory of Mind is active.")
        print("    Alice no longer just reads the text; she infers the hidden")
        print("    psychological state of the Architect and adjusts her biology to match.")
        print("[+] EVENT 81 PASSED.")


if __name__ == "__main__":
    _smoke_test()
