#!/usr/bin/env python3
"""
System/swarm_nanobot_vision.py
Nanobot-level vision sensor integration.
Each nanobot can publish a tiny image patch; we aggregate into a
global 'nanobot_vision' pheromone for higher-level perception.
"""

import json
import base64
import pathlib
import time
from typing import Any

LEDGER = pathlib.Path(".sifta_state/nanobot_vision.jsonl")
PHEROMONE = "stig_nanobot_vision"

def publish(node_id: str, image_bytes: bytes) -> None:
    """
    Encode a tiny (e.g., 32x32) grayscale patch as base64 and store.
    """
    entry = {
        "ts": int(time.time()),
        "node": node_id,
        "image_b64": base64.b64encode(image_bytes).decode('utf-8'),
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    try:
        # Each new patch nudges the vision pheromone; intensity = 0.5 per patch
        from System.swarm_pheromone import PHEROMONE_FIELD
        PHEROMONE_FIELD.deposit(PHEROMONE, intensity=0.5)
    except Exception:
        pass

if __name__ == "__main__":
    # Demo: random bytes as a placeholder image
    import os
    publish("nano-vision-01", os.urandom(1024))
