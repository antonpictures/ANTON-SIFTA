from System.swarm_regulatory_genome import _acquire_lease, _throttle_blocks, propose_regulatory_update
from pathlib import Path
root = Path(".sifta_state")
import shutil
shutil.rmtree(root, ignore_errors=True)
import json
import os

trigger = {
    "sustained_regime": "UNDERCONFIDENT",
    "duration_ticks": 35,
    "dam_stage": 2,
    "tme_phase": "EQUILIBRIUM",
}
r1 = propose_regulatory_update(
    {"metacog_evidence_threshold": 0.55},
    trigger,
    "MetacognitiveMonitor",
    root=root,
    current_tick_id=100,
)
print("r1", r1 is not None)
r2 = propose_regulatory_update(
    {"metacog_evidence_threshold": 0.60},
    trigger,
    "MetacognitiveMonitor",
    root=root,
    current_tick_id=121,
)
print("r2", r2 is not None)
if r2 is None:
    print("lease?", _acquire_lease(root, "MetacognitiveMonitor", 121))
    print("throttle?", _throttle_blocks(root / "regulatory_genome.jsonl", current_tick_id=121))
