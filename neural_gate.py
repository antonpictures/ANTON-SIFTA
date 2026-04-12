# neural_gate.py
"""
NEURAL GATE — Absolute Execution Authority

This is the ONLY place where SIFTA actions are allowed to pass into reality.
Hermes MUST route all execution through this gate.
If this file is bypassed, the system is considered structurally compromised.
"""

from cortex_guard import CortexGuard
from volatility_tracker import VolatilityTracker
from context_integrity import ContextIntegrity
from decision_logger import log_decision
from state_bus import get_state

class NeuralGate:
    def __init__(self):
        self.guard = CortexGuard()
        self.volatility = VolatilityTracker()
        self.integrity = ContextIntegrity()

    def authorize(
        self,
        action_name: str,
        file_path: str,
        proposed_content: str,
        confidence: float,
        is_client_deliverable: bool
    ) -> tuple[bool, str]:
        """
        Absolute final authority check before Hermes is allowed to execute.
        Returns Boolean.
        """

        # 0. Fast-Path Muscle Memory Check
        # If the Swarm has learned a hard rule about this target, block instantly.
        muscle_memory = get_state("muscle_memory", {})
        if file_path in muscle_memory:
            return False, f"MUSCLE_MEMORY_BLOCK: {muscle_memory[file_path]}"

        # 1. Measure shared volatility (real-time system stress)
        current_volatility = self.volatility.get_current_volatility()
        # Predictive bump to prevent rapid loops sneaking through one step late
        predicted_volatility = min(1.0, current_volatility + 0.05)

        # 2. Score context integrity based on SCAR reality filter (e.g. ego leak, domain violation)
        integrity_score = self.integrity.calculate(
            file_path,
            proposed_content,
            is_client_deliverable
        )

        # 3. Cortex stability check (Can the Swarm act right now, or is it panicked?)
        decision, reason = self.guard.evaluate(
            confidence=confidence,
            volatility=predicted_volatility,
            context_integrity=integrity_score
        )

        # 4. Observable Trace Log (Log EVERYTHING)
        log_decision({
            "action": action_name,
            "allowed": decision,
            "reason": reason,
            "confidence": confidence,
            "volatility": predicted_volatility,
            "integrity": integrity_score,
            "target": file_path
        })

        if decision:
            # Inform the guard that we pulled the trigger so it registers the cooldown
            self.guard.register_action()
            # Inform the tracker of a successful reality breach/action
            self.volatility.record_attempt(success=True)
            return True, "AUTHORIZED: Execution threshold met."

        # If blocked, record the failed attempt to accurately model stress
        self.volatility.record_attempt(success=False)
        return False, reason
