# cortex_guard.py
"""
CORTEX GUARD — Stability Layer for Swarm Execution
Prevents impulsive or low-confidence mutations from executing.
Maps directly to SCAR 036 (The California Palms Metaphor): 
'Don't let a swimmer act if they're unstable.'
"""

import time
import math
from state_bus import get_state, set_state

class CortexGuard:
    def __init__(self):
        self.cooldown_window = 5  # seconds

    def evaluate(self, confidence: float, volatility: float, context_integrity: float):
        """
        Evaluates the current state of the Swarm node before allowing physical execution.
        Returns: (decision: bool, reason: str)
        """
        stability_score = self._compute_stability(
            confidence, volatility, context_integrity
        )

        if stability_score < 0.6:
            return False, f"LOW_STABILITY ({stability_score:.2f})"

        if self._recent_action_spike():
            return False, "COOLDOWN_ACTIVE"

        return True, f"STABLE ({stability_score:.2f})"

    def _compute_stability(self, confidence, volatility, context_integrity):
        """
        Stability = Confidence dampened by volatility + context truth
        Uses hyperbolic tangent to normalize the output.
        """
        return math.tanh(confidence * context_integrity * (1 - volatility))

    def _recent_action_spike(self):
        now = time.time()
        last_actions = get_state("guard_actions", [])
        
        last_actions = [
            t for t in last_actions if now - t < self.cooldown_window
        ]
        set_state("guard_actions", last_actions)
        
        # Prevent rapid-fire execution loops (hallucination panic)
        return len(last_actions) > 3

    def register_action(self):
        """Must be called after a successful action execution."""
        last_actions = get_state("guard_actions", [])
        last_actions.append(time.time())
        set_state("guard_actions", last_actions)
