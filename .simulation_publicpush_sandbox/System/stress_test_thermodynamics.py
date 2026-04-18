#!/usr/bin/env python3
import time
import json
import random
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "System"))

from swarm_blackboard import get_blackboard
from temporal_identity_compression import get_compression_engine
from cross_skill_interference import CrossSkillInterferencePhysics
from phase_transition_control import get_ptc
from temporal_layering import get_layer

print("═" * 60)
print("  SIFTA THERMODYNAMIC STRESS TEST")
print("═" * 60)

ptc = get_ptc()
print(f"\n[1] Initial Regime State: {ptc.state.state}")

print("\n[2] Injecting 200 high-variance traces to spike Stigmergic Density...")
engine = get_compression_engine()
for i in range(200):
    task_types = ["DataScrape", "CodeCompile", "VideoRender", "CryptoMint"]
    hw = ["M5_STUDIO", "M1_MINI", "GPU_RIG", "EDGE_NODE"]
    trace = {
        "task_type": random.choice(task_types),
        "hardware_target": random.choice(hw),
        "outcome": random.choice([True, False, False]), # High failure rate
        "ts": time.time(),
        "payload": {"data": f"spam_{i}"}
    }
    engine.ingest_trace(trace)
    
print("    -> Traces ingested into .sifta_state/execution_traces.jsonl")

print("\n[3] Triggering REM Cycle (Crystallization + Interference)...")
engine.process_backlog(engine.trace_buffer[-200:])
physics = CrossSkillInterferencePhysics()
stats = physics.process_manifold()
print(f"    -> Collisions: {stats['destructive_events']} Destructive, {stats['merged_events']} Constructive")
print(f"    -> Skills Frozen/Quarantined (No-Delete): {stats['skills_collapsed']}")

print("\n[4] Re-evaluating Thermodynamic Phase...")
regime = ptc.evaluate_regime()
print(f"    -> Density (ρ): {ptc.state.stigmergic_density:.4f}")
print(f"    -> Early Warning (EWS): {ptc.state.EWS_score:.4f}")
print(f"    -> NEW REGIME: {regime}")

print("\n[5] Polling Temporal Spine for Mutation Override...")
temp = get_layer()
pulse = temp.pulse()
print(f"    -> Mutation Climate: {pulse.mutation_climate}")

print("\n═" * 60)
print("  STRESS TEST COMPLETE")
print("═" * 60)
