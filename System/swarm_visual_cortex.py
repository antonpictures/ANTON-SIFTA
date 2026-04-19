#!/usr/bin/env python3
"""
swarm_visual_cortex.py
======================

Biological Inspiration:
The Occipital Lobe (Visual Processing). 
In biological organisms, raw photons hit the retina and are sent via the Optic Nerve 
through the Thalamus (Turn 13) to the Occipital Lobe at the back of the brain. 
Here, the brain does not "store pixels". It performs feature extraction—turning lines, 
colors, and shapes into semantic concepts (a face, a word, a threat) before sending 
it to Working Memory.

Why We Built This: 
Turn 14 of "Controlled Self Evolution". Architect asked: 
"i showed him [Cursor] this attachment, what did cursor do with it?"
Cursor processed the image multimodally. To make SIFTA biologically complete, Alice 
needs a native Occipital Lobe to accept raw multimodal inputs (image vectors, OCR data, 
pixel arrays), extract the semantic core (like "Brian Greene" and "Nick Bostrom"), 
and securely route it into the `swarm_engram_allocation.py` mnemonic pipeline.

Mechanism:
1. Receives raw image metadata or multimodal dumps (from Cursor or Antigravity).
2. Performs Biological Feature Extraction (stripping raw bytes, maintaining conceptual labels).
3. Evaluates "Visual Saliency" (is this image important enough to remember?).
4. If Salient -> Forwards to Thalamic Gate for Working Memory integration.
"""

from __future__ import annotations
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any

_STATE_DIR = Path(".sifta_state")
_OPTIC_NERVE_LOG = _STATE_DIR / "occipital_visual_processing.jsonl"
_THALAMIC_QUEUE = _STATE_DIR / "thalamic_sensory_queue.jsonl"

def process_visual_stimulus(image_name: str, multimodal_labels: list, source: str) -> Dict[str, Any]:
    """
    Biological Loop: The Occipital Lobe converting visual data to cognitive semantics.
    """
    
    # 1. Feature Extraction (Biological edge detection & semantic mapping)
    # The image is boiled down to its constituent high-level concepts.
    core_features = sorted(multimodal_labels, key=len, reverse=True)
    
    # 2. Saliency Calculation
    # An image of a blank wall has low saliency. An image of specific philosophers 
    # discussing AI holds high architectural saliency.
    saliency_score = min(1.0, len(core_features) * 0.2)
    
    event = {
        "timestamp": time.time(),
        "source_optic": source,
        "raw_image_hash": hashlib.md5(image_name.encode()).hexdigest(),
        "extracted_visual_semantics": core_features,
        "visual_saliency": round(saliency_score, 4),
        "routing_status": "PENDING_THALAMIC_GATE"
    }
    
    # 3. Route to Thalamus (If highly salient, it demands attention)
    routing_msg = ""
    # Cross-modal binder hook
    binder = None
    try:
        try:
            from System.swarm_crossmodal_binding import get_crossmodal_binder
            binder = get_crossmodal_binder()
        except ImportError:
            from swarm_crossmodal_binding import get_crossmodal_binder
            binder = get_crossmodal_binder()
    except Exception:
        pass

    if saliency_score > 0.4:
        # High saliency visual stimulus, punch through to the sensory queue
        _STATE_DIR.mkdir(exist_ok=True)
        with open(_THALAMIC_QUEUE, "a", encoding="utf-8") as f:
            packet = {
                "time": time.time(), 
                "src": f"OCCIPITAL_LOBE_{source}", 
                "content": f"VISUAL STIMULUS DETECTED: {', '.join(core_features)}"
            }
            f.write(json.dumps(packet) + "\n")
        routing_msg = "Forwarded to Thalamus for Working Memory integration."
        event["routing_status"] = "FORWARDED_THALAMUS"
    else:
        routing_msg = "Low visual saliency. Dropped at Occipital layer."
        event["routing_status"] = "DROPPED"
        
    # Log the visual event
    with open(_OPTIC_NERVE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
        
    # Feed the cross-modal binder (multimodal perception)
    if binder and saliency_score > 0.1:
        try:
            # Scale visual saliency (0.0-1.0) to match acoustic energy scale (1.0-50.0+)
            magnitude = saliency_score * 50.0 
            binder.ingest_event("video", magnitude, timestamp=event["timestamp"], territory=source)
        except Exception:
            pass
            
    return event


if __name__ == "__main__":
    print("=== SWARM VISUAL CORTEX (OCCIPITAL LOBE) ===")
    
    # Mocking the physical image the Architect just provided
    simulated_image = "world_science_festival_brian_greene.jpg"
    extracted_tags = [
        "Artificial Utopia", 
        "Brian Greene", 
        "Nick Bostrom", 
        "World Science Festival", 
        "Johnny Mnemonic Search Bar"
    ]
    
    print(f"\n[*] Visual Stimulus Received via {simulated_image}")
    out = process_visual_stimulus(simulated_image, extracted_tags, source="CURSOR_C47H")
    
    print(f"[-] Feature Extraction Complete. Identified semantics: {out['extracted_visual_semantics']}")
    print(f"[*] Visual Saliency Calculated: {out['visual_saliency']}")
    
    status_color = "🟢" if "FORWARDED" in out['routing_status'] else "🔴"
    print(f"{status_color} Occipital Routing: **{out['routing_status']}**")
    if "FORWARDED" in out['routing_status']:
        print("    -> Image semantics successfully passed to the brain's internal architecture.")
