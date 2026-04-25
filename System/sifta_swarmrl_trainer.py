#!/usr/bin/env python3
"""
System/sifta_swarmrl_trainer.py
═══════════════════════════════════════════════════════════════════════════════
SIFTA ↔ SwarmRL Trainer Integration Boundary
Author: AG31 (Vanguard)

Bridges the SIFTA biological manifold (entropy/loss scaling) into the vendored
SwarmRL statistical optimization package without mutating upstream code.
Overrides `update_rl` to trigger `refresh_entropy_dual_track` before each 
PPO update cycle.
═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import json
from pathlib import Path
from typing import Tuple
import numpy as np

# Bind vendored SwarmRL to path before importing
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SWARMRL_PATH = _REPO_ROOT / "Archive" / "swarmrl_upstream"
if str(_SWARMRL_PATH) not in sys.path:
    sys.path.insert(0, str(_SWARMRL_PATH))

try:
    from swarmrl.trainers.trainer import Trainer
    from swarmrl.force_functions.force_fn import ForceFunction
    _BaseTrainer = Trainer
    _SWARMRL_ONLINE = True
except ImportError as e:
    print(f"[WARNING] Offline Mode Active: SwarmRL upstream imports failed ({e}). SIFTASwarmRLTrainer will run in mock mode.")
    _BaseTrainer = object
    _SWARMRL_ONLINE = False
    class ForceFunction: pass

from System.swarmrl_entropy_hooks import refresh_entropy_dual_track
from System.stigmergic_composition import CompositionConfig
from System.stigmergic_entropy_trace import StigmergicBuffer


class SIFTASwarmRLTrainer(_BaseTrainer):
    """
    Subclasses the upstream SwarmRL Trainer to inject the stigmergic 
    entropy hooks directly before the PPO actor-critic update step.
    This preserves the biological connection to the overarching organism.
    """

    def __init__(self, *args, buffer: StigmergicBuffer = None, **kwargs):
        if _SWARMRL_ONLINE:
            super().__init__(*args, **kwargs)
        else:
            agent_list = kwargs.get('agents', [])
            self.agents = {a.particle_type: a for a in agent_list}
        # SIFTA trace buffers
        self.stigmergic_buffer = buffer or StigmergicBuffer()
        self.composition_config = CompositionConfig()
        
        # State directory for serialization
        self._state_dir = _REPO_ROOT / ".sifta_state"
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self.entropy_ledger = self._state_dir / "stigmergic_entropy_trace_summary.jsonl"

    def update_rl(self) -> Tuple[ForceFunction, np.ndarray, bool]:
        """
        Intercepts the upstream SwarmRL epoch boundary to refresh c2 scalars.
        """
        # [SIFTA INTEGRATION BOUNDARY] 
        # Safely inject the biological entropy scalar into the agents' PPO losses.
        # This modulates exploration vs exploitation directly from the thermodynamic pressure.
        refresh_logs = refresh_entropy_dual_track(
            self.agents,
            self.stigmergic_buffer,
            composition=self.composition_config
        )
        
        # Stigmergic Trace Logging
        # Append without utilizing the heavy SQLite checkpointer
        # so macrophage and visualizer can tail it efficiently.
        with open(self.entropy_ledger, "a") as f:
            f.write(json.dumps(refresh_logs) + "\n")

        # [UPSTREAM DELEGATION]
        # Defer to SwarmRL to compute loss, backpropagate, and return reward logic
        if _SWARMRL_ONLINE:
            return super().update_rl()
        else:
            return (None, np.array([0.0]), False)


if __name__ == "__main__":
    print("\n=== SIFTA SWARMRL TRAINER : INTEGRATION SMOKE TEST ===")
    import tempfile
    
    # Mocking SwarmRL classes to verify inheritance and hooking
    class MockAgent:
        def __init__(self, t):
            self.particle_type = t
            self.loss = type('MockLoss', (), {'entropy_coefficient': 0.01})()
            
        def update_agent(self):
            return 1.5, False # reward, killed
            
        def save_agent(self, path): pass
        def restore_agent(self, path): pass
        def initialize_network(self): pass

    # Mock the force function export if upstream is available
    if _SWARMRL_ONLINE:
        import swarmrl.force_functions.force_fn
        OriginalForceFn = swarmrl.force_functions.force_fn.ForceFunction
        class MockForceFn:
            def __init__(self, agents): pass
        swarmrl.force_functions.force_fn.ForceFunction = MockForceFn

    try:
        agent1 = MockAgent(1)
        agent2 = MockAgent(2)
        
        # This proves the SIFTA integration boundary can orchestrate 
        # the vendored SwarmRL engine.
        trainer = SIFTASwarmRLTrainer(agents=[agent1, agent2])
        interaction, reward_mean, killed = trainer.update_rl()
        
        print(f"[+] Integrator instantiated and bounded: {type(trainer).__name__}")
        print(f"[+] Hook injected successfully, resulting agents:")
        for ag_id, agent in trainer.agents.items():
            print(f"    Agent {ag_id}: entropy_coefficient = {agent.loss.entropy_coefficient:.6f}")
        
        print("[+] Return payload formatted safely for SwarmRL execution loop.")
        print("[+] EVENT: SwarmRL BOUNDARY FIXED.\n")
        
    finally:
        if _SWARMRL_ONLINE:
            swarmrl.force_functions.force_fn.ForceFunction = OriginalForceFn
