#!/usr/bin/env python3
"""
swarm_crossmodal_binding.py — Multisensory Integration & Proto-Objects
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Implements true biological Perception natively via Object Tracking.
Signals that arrive within a specific temporal coincidence 
window (10-100ms) across different sensory substrates are fused 
into a singular Percept. 

Crucially, perception tracks the persistence of an entity. 
This module maintains Bayesian Object inference. If continuous visual/audio
coincidences line up, the `coherence` of the Proto-Object escalates, 
separating true environmental rhythm from isolated background anomalies.

Those fused Object pheromones then perturb the Swarm Oscillator 
with mathematical resistance, generating steady Emergent Attention.
"""

import time
import json
import hashlib
from pathlib import Path
from collections import deque
from typing import Dict, Any, Optional, List

MODULE_VERSION = "2026-04-19.v3"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_CROSSMODAL_PHEROMONES = _STATE / "crossmodal_pheromones.jsonl"


class SwarmCrossModalBinder:
    def __init__(self, window_ms: int = 80, ledger: Optional[Path] = None):
        # Time window in seconds where two separate fields must intersect to count as Perception
        self.window = window_ms / 1000.0
        # Circular buffer keeping sensory spike events
        self.events = deque(maxlen=256)
        # Prevent double-binding the same spike repeatedly. Pruned in lockstep
        # with `self.events` (see ingest_event); without this the set leaks
        # one entry per ingest forever and exhausts RAM in long-running swarms.
        # C47H audit 2026-04-19: bug found during crossmodal wiring review.
        self.bound_event_ids = set()
        
        # Bayesian Object Tracker
        self.proto_objects: List[Dict[str, Any]] = []

        self.ledger = ledger or _CROSSMODAL_PHEROMONES
        # Ensure the state directory exists
        if hasattr(self.ledger, 'parent'):
            self.ledger.parent.mkdir(parents=True, exist_ok=True)

    def ingest_event(self, source_type: str, magnitude: float, timestamp: Optional[float] = None, territory: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Takes raw spatial/temporal field spikes from Photonic or Acoustic fields.
        Returns the bound multisensory Object if a fusion occurs, else None.
        """
        if timestamp is None:
            timestamp = time.time()

        new_event = {
            "ts": timestamp,
            "source": source_type,
            "magnitude": magnitude,
            "territory": territory
        }

        # Evict the soon-to-fall-off event's ts from bound_event_ids in lockstep
        # with the bounded deque. The deque auto-evicts on append; the dedup set
        # must shrink with it or RAM grows without bound.
        if len(self.events) == self.events.maxlen:
            self.bound_event_ids.discard(self.events[0]["ts"])

        self.events.append(new_event)

        return self._attempt_bind(new_event)

    def _attempt_bind(self, new_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for e in reversed(self.events):
            if e is new_event:
                continue
                
            # Deduplication
            if e["ts"] in self.bound_event_ids or new_event["ts"] in self.bound_event_ids:
                continue

            dt = abs(e["ts"] - new_event["ts"])

            # Temporal coincidence binding across distinct sensorium channels
            if dt < self.window and e["source"] != new_event["source"]:
                self.bound_event_ids.add(e["ts"])
                self.bound_event_ids.add(new_event["ts"])
                return self._process_object(e, new_event, dt)
        return None

    def _process_object(self, e1: Dict[str, Any], e2: Dict[str, Any], dt: float) -> Dict[str, Any]:
        """
        Takes the coincidence cross-modal bind and traces it into a Proto-Object.
        Scales coherence to prevent un-patterned noise from gaining biological salience.
        """
        
        fused_ts = time.time()
        fused_magnitude = (e1["magnitude"] + e2["magnitude"]) / 2

        # In biological networks, tight sync (dt approaching 0) increases binding reinforcement
        sync_strength = (1.0 - (dt / self.window)) 
        effective_shock = fused_magnitude * (1.0 + sync_strength)

        # Basic object association: if a coincidence happens repeatedly within 2.0 seconds 
        # of a tracked object, assume it is the same rhythmic/structural entity.
        matched_obj = None
        for obj in self.proto_objects:
            if abs(fused_ts - obj["last_ts"]) < 2.0:
                matched_obj = obj
                break

        if matched_obj:
            matched_obj["history"].append(fused_magnitude)
            matched_obj["last_ts"] = fused_ts
            matched_obj["sources"].extend([s for s in [e1["source"], e2["source"]] if s not in matched_obj["sources"]])
            # Coherence escalates linearly with consistent hits (+0.15 per coincidence,
            # capped at 1.0). Hits-to-saturation: 1->0.20, 2->0.35, 3->0.50, 4->0.65,
            # 5->0.80, 6->0.95, 7->1.00. Logarithmic shaping is a future option.
            matched_obj["coherence"] = min(1.0, matched_obj["coherence"] + 0.15)
            working_object = matched_obj
        else:
            # Mint a new entity
            raw_id = f"{e1['source']}_{e2['source']}_{fused_ts}"
            persisted_hash = hashlib.md5(raw_id.encode()).hexdigest()[:12]
            working_object = {
                "object_id": persisted_hash,
                "first_ts": fused_ts,
                "last_ts": fused_ts,
                "sources": [e1["source"], e2["source"]],
                "history": [fused_magnitude],
                "coherence": 0.2,  # Start low. One clap is cheap.
            }
            self.proto_objects.append(working_object)
            
            # Prune ancient objects
            if len(self.proto_objects) > 50:
                self.proto_objects.pop(0)

        # Create the bound output using the structural tracker
        row = {
            "ts": fused_ts,
            "type": "crossmodal_object",
            "object_id": working_object["object_id"],
            "sources": working_object["sources"],
            "magnitude": effective_shock,
            "dt_sync_error": dt,
            "coherence": working_object["coherence"]
        }

        try:
            with open(self.ledger, "a") as f:
                f.write(json.dumps(row) + "\n")
                
            # Organism Wiring: If the object reaches biological coherence, it physically
            # stamps the Path-Graph Stigmergy with reality heat.
            # C47H BUG-17 fix: explicit commit() — write_potential is lazy by design
            # so a one-shot coherent-object event must flush itself or it vanishes
            # when the field reference is dropped at function exit.
            target_territory = e1.get("territory") or e2.get("territory")
            if target_territory and working_object["coherence"] > 0.4:
                try:
                    from System.swarm_potential_field import SwarmPotentialField
                    field = SwarmPotentialField()
                    field.write_potential(Path(target_territory).resolve(), effective_shock * 10.0)
                    field.commit()
                except Exception:
                    pass
                    
        except Exception:
            pass
            
        return row

# Global singleton for the live swarm OS.
_DEFAULT_BINDER: Optional[SwarmCrossModalBinder] = None

def get_crossmodal_binder() -> SwarmCrossModalBinder:
    global _DEFAULT_BINDER
    if _DEFAULT_BINDER is None:
        _DEFAULT_BINDER = SwarmCrossModalBinder()
    return _DEFAULT_BINDER

if __name__ == "__main__":
    # Smoke Test
    print("═" * 58)
    print("  SIFTA — PROTO-OBJECT PERCEPTION TRACKING SMOKE TEST")
    print("═" * 58 + "\n")

    import tempfile
    import shutil
    
    _tmp = Path(tempfile.mkdtemp())
    _tmp_ledger = _tmp / "crossmodal_pheromones.jsonl"
    
    try:
        binder = SwarmCrossModalBinder(window_ms=80, ledger=_tmp_ledger)

        print("[TEST] Evaluating biological coherence escalation (Repeated Claps)")
        
        # Beat 1
        b1 = binder.ingest_event("audio", 45.0, timestamp=1.0)
        p1 = binder.ingest_event("video", 60.0, timestamp=1.04)
        assert p1 is not None
        assert p1["coherence"] == 0.2
        print(f"  [PASS] Beat 1 generates novel object {p1['object_id'][:6]} (Coherence: {p1['coherence']:.2f})")
        
        # Beat 2
        b2 = binder.ingest_event("audio", 45.0, timestamp=1.5)
        p2 = binder.ingest_event("video", 60.0, timestamp=1.54)
        assert p2 is not None
        assert p2["object_id"] == p1["object_id"]
        assert p2["coherence"] == 0.35
        print(f"  [PASS] Beat 2 correctly associates! Object mapped. (Coherence: {p2['coherence']:.2f})")

        # Beat 3
        b3 = binder.ingest_event("audio", 45.0, timestamp=2.0)
        p3 = binder.ingest_event("video", 60.0, timestamp=2.04)
        assert p3["object_id"] == p1["object_id"]
        assert p3["coherence"] == 0.50
        print(f"  [PASS] Beat 3 scales biological salience. (Coherence: {p3['coherence']:.2f})")

        print("\n[SUCCESS] 3/3 Proto-Object tests passed.")
        print("Result: Spatial and Temporal fields map objects, not just noise.")
    finally:
        shutil.rmtree(_tmp, ignore_errors=True)
