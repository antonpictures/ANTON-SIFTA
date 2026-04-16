# recovery_reflex.py
"""
RECOVERY REFLEX — Parasympathetic System for SIFTA

Allows the Swarm to breathe out and recover from high volatility states.
Without this, SIFTA permanently locks after a panic event and becomes a firewall.
"You get chaos or paralysis. With recovery, you get adaptation."
"""

import time
from state_bus import get_state, set_state

class RecoveryReflex:
    def __init__(self):
        # We bleed off 0.15 volatility per introspection tick
        self.decay_rate = 0.15  
        self.min_volatility = 0.1

    def step(self):
        """Called periodically by introspection loop."""
        
        volatility = get_state("volatility_score", 0.1)
        
        # In a real deployed version, last_action_time would map to last ATTEMPT, 
        # not just last SUCCESS. For the prototype, we use the raw volatility tracker history.
        # Let's get the volatility history to see when the Swarm last tried to act.
        history = get_state("volatility_history", [])
        last_attempt_time = history[-1]["timestamp"] if history else time.time()
        
        time_idle = time.time() - last_attempt_time

        # Only recover if system hasn't been bothered for 2 seconds
        if time_idle > 2.0:
            if volatility > self.min_volatility:
                new_volatility = max(
                    self.min_volatility,
                    volatility - self.decay_rate
                )
                set_state("volatility_score", new_volatility)
                return new_volatility

        return volatility
