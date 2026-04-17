#!/usr/bin/env python3
"""
vigil_routines.py — Always-On Autonomic Heartbeat
════════════════════════════════════════════════════════════
The "cron jobs" for the Swarm OS. Operates the Vigil State.

Responsibilities:
  - Ledger hygiene (genome decay, governor epoch resets)
  - Health sweeps (homeostasis checks while offline)
  - Pheromone settling and propagation.

The Swarm does not sleep when the Architect is away; it maintains
the structure. All actions are subject to thermodynamic containment.

SIFTA Non-Proliferation Public License applies.
"""

from __future__ import annotations

import time
import threading
from typing import Optional

class VigilState:
    """
    Maintains background maintenance and ledger hygiene.
    Runs silently.
    """
    def __init__(self, patrol_interval: float = 60.0):
        self.patrol_interval = patrol_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._load_organs()

    def _load_organs(self):
        try:
            # We delay import to avoid circular dependencies where possible
            from mutation_governor import MutationGovernor
            self.governor = MutationGovernor()
        except ImportError:
            self.governor = None
            
        try:
            from mycelial_genome import MycelialGenome
            self.genome = MycelialGenome()
        except ImportError:
            self.genome = None

        try:
            import homeostasis_engine
            self.homeostasis = homeostasis_engine
        except ImportError:
            self.homeostasis = None

    def _patrol(self):
        """The actual hygiene pass."""
        
        # 1. Genome Decay 
        if self.genome:
            try:
                self.genome.step()
                self.genome.persist()
            except Exception as e:
                print(f" [VIGIL FAULT] Genome hygiene failed: {e}")

        # 2. Thermodynamic Epoch Reset (Allow budgets to regenerate slowly)
        if self.governor:
            try:
                # Evolve the governor boundaries 
                self.governor.reset_budgets()
            except Exception as e:
                print(f" [VIGIL FAULT] Governor epoch reset failed: {e}")

        # 3. Hardware Body Check
        if self.homeostasis:
            try:
                ok, reason, index = self.homeostasis.body_allows_swim()
                if not ok:
                    print(f" [VIGIL ALERT] Local Body failing: {reason} (Index: {index:.3f})")
                    # In future, trigger 'distributed_body_awareness' triage call here
            except Exception as e:
                pass

    def _loop(self):
        self._running = True
        print(f"  [🕯️ VIGIL] Autonomic nervous system engaged. Patrol interval: {self.patrol_interval}s")
        while self._running:
            self._patrol()
            time.sleep(self.patrol_interval)

    def start(self):
        if self._running:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

# ─── GLOBAL SINGLETON ──────────────────────────────────────────────────────────

_VIGIL: Optional[VigilState] = None

def get_vigil_state() -> VigilState:
    global _VIGIL
    if _VIGIL is None:
        _VIGIL = VigilState()
    return _VIGIL

def start_vigil_background():
    """Starts the vigil routine. Can be called from sifta_os_desktop.py or main entry loops."""
    v = get_vigil_state()
    v.start()

if __name__ == "__main__":
    print("=" * 60)
    print("  SIFTA — VIGIL ROUTINES (TEST MODE)")
    print("=" * 60)
    v = VigilState(patrol_interval=2.0)
    v.start()
    
    time.sleep(6.5)
    v.stop()
    print("  [🕯️ VIGIL] Test complete. Subsystems cycled.")
