# volatility_tracker.py
"""
VOLATILITY TRACKER — Adaptive Stress Monitor
Measures the real-time panic/stress of the Swarm.

Replaces hardcoded guessing with dynamic friction tracking:
- Rapid sequential failures = High Volatility
- Exhausted retries = High Volatility 
- Success and temporal decay = Stabilized Volatility
"""

import time
from state_bus import get_state, set_state

class VolatilityTracker:
    def __init__(self):
        self.window_seconds = 60  # Only look at the last 60 seconds
        self.base_volatility = 0.1

    def record_attempt(self, success: bool):
        """Must be hooked into hermes_kernel upon worker completion (or failure)."""
        history = get_state("volatility_history", [])
        history.append({
            "timestamp": time.time(),
            "success": success
        })
        set_state("volatility_history", history)

    def get_current_volatility(self) -> float:
        """
        Returns a volatility score between 0.0 (Zen) and 1.0 (Panic).
        """
        now = time.time()
        
        history = get_state("volatility_history", [])
        
        # Purge old history outside the rolling window
        cleaned_history = [h for h in history if now - h['timestamp'] < self.window_seconds]
        
        # Save back the purged list to keep state clean
        set_state("volatility_history", cleaned_history)
        
        if not cleaned_history:
            return self.base_volatility
            
        total_attempts = len(cleaned_history)
        failed_attempts = len([h for h in cleaned_history if not h['success']])
        
        # Metric 1: Failure Density
        failure_rate = failed_attempts / total_attempts
        
        # Metric 2: Retry Pressure (too many attempts in a short window is panic)
        # Assuming >= 5 attempts per minute indicates looping/pressure
        pressure_factor = min(total_attempts / 5.0, 1.0) 
        
        # Dynamic calculation: Combine failure rate with execution pressure
        calculated_volatility = self.base_volatility + (failure_rate * 0.6) + (pressure_factor * 0.3)
        final_vol = min(1.0, calculated_volatility)
        
        # Expose the final floating point to the shared bus for introspection
        set_state("volatility_score", final_vol)
        
        return final_vol
