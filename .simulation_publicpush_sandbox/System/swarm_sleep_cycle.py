#!/usr/bin/env python3
"""
swarm_sleep_cycle.py
====================

Biological Inspiration:
Slow-Wave Sleep (SWS), the Glymphatic System, and Offline Replay.
During waking hours, a brain accumulates metabolic waste and volatile data. 
During sleep, the Glymphatic system physically flushes neurotoxins from the brain.
Simultaneously, the Hippocampus "replays" the events of the day offline, 
which cements frail memories into permanent Neocortical engrams without 
interference from new sensory inputs.

Why We Built This: 
"Controlled Self Evolution" requires pacing. If CP2F and Alice continually 
ingest "Past and Present" without pause, context degrades, token limits max out, 
and hallucinations occur (neural fatigue).

Mechanism:
1. Glymphatic Flush: Physically empties the `hippocampal_buffer` and resets the 
   volatile `Working Memory`. (Saves token overhead).
2. Offline Replay: Scans the events experienced during the waking cycle and 
   pushes positive reinforcement signals to the `latent_synapses` layer entirely 
   offline, solidifying learning.
3. State Switch: Logs the transition from WAKING -> SLEEP -> WAKING.
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, Any

_STATE_DIR = Path(".sifta_state")
_HIPPOCAMPUS_BUFFER = _STATE_DIR / "hippocampal_buffer.jsonl"
_WORKING_MEMORY = _STATE_DIR / "pfc_working_memory.json"
_SYNAPSE_LOG = _STATE_DIR / "latent_synapses.jsonl"
_DREAM_REPORTS = _STATE_DIR / "dream_reports.jsonl"

def glymphatic_flush() -> Dict[str, Any]:
    """Clears short term volatile memory buffers mimicking biological brain detox."""
    events = {"buffers_cleared": []}
    
    # Empty Hippocampus (Episodic Cache)
    if _HIPPOCAMPUS_BUFFER.exists():
        _HIPPOCAMPUS_BUFFER.unlink()
        events["buffers_cleared"].append("hippocampal_buffer")
        
    # Empty Working Memory (Prefrontal Cortex)
    empty_wm = {
        "timestamp": time.time(),
        "present_stimulus": "[SLEEP_STATE]",
        "past_associates_retrieved": 0,
        "fused_working_memory": []
    }
    with open(_WORKING_MEMORY, "w", encoding="utf-8") as f:
        json.dump(empty_wm, f, indent=2)
    events["buffers_cleared"].append("pfc_working_memory")

    try:
        from System.glymphatic_pulse_gate import record_pulse

        record_pulse(
            "glymphatic_flush_complete",
            source="swarm_sleep_cycle",
            meta={"buffers_cleared": events["buffers_cleared"]},
        )
    except Exception:
        pass

    return events

def offline_replay() -> Dict[str, Any]:
    """
    Offline systems consolidation. 
    Strengthens all valid long-term memories without waiting for RL rewards.
    """
    events = {"synapses_replayed": 0, "consolidation_boost": 0.05}
    if not _SYNAPSE_LOG.exists():
        return events
        
    synapses = []
    try:
        with open(_SYNAPSE_LOG, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                syn = json.loads(line)
                # Apply the offline replay boost
                syn["synaptic_weight"] = round(float(syn.get("synaptic_weight", 1.0)) + events["consolidation_boost"], 4)
                synapses.append(syn)
                events["synapses_replayed"] += 1
    except Exception:
        pass
        
    # Save the consolidated synapses
    if synapses:
        with open(_SYNAPSE_LOG, "w", encoding="utf-8") as f:
            for s in synapses:
                f.write(json.dumps(s) + "\n")
                
    return events

def trigger_sleep_cycle() -> Dict[str, Any]:
    """
    Executes the biological sleep loop.
    """
    hippocampal: Dict[str, Any] = {}
    try:
        from System.hippocampal_replay_scheduler import HippocampalReplayScheduler

        h = HippocampalReplayScheduler()
        hippocampal["tick"] = h.tick().to_dict()
        hippocampal["replay_session"] = h.execute_replay_session(max_replays=15).to_dict()
    except Exception:
        hippocampal = {}

    flush_results = glymphatic_flush()
    replay_results = offline_replay()
    
    dream_report = {
        "timestamp": time.time(),
        "cycle": "SLOW_WAVE_SLEEP",
        "toxins_flushed": len(flush_results["buffers_cleared"]),
        "synapses_consolidated_offline": replay_results["synapses_replayed"],
        "hippocampal_replay": hippocampal,
        "status": "RESTED",
    }
    
    _STATE_DIR.mkdir(exist_ok=True)
    with open(_DREAM_REPORTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(dream_report) + "\n")
        
    return dream_report

if __name__ == "__main__":
    print("=== SWARM GLYMPHATIC DETOX & SLEEP CYCLE ===")
    print("[*] Transitioning system to Sleep State...")
    out = trigger_sleep_cycle()
    
    print(f"[-] GLYMPHATIC FLUSH: Detoxing volatile buffers ({out['toxins_flushed']} buffers cleared).")
    print(f"[+] OFFLINE REPLAY: Consolidating Engrams ({out['synapses_consolidated_offline']} synapses strengthened).")
    print("\nSleep Cycle Complete. Swarm is RESTED and ready for new waking stimulus.")
