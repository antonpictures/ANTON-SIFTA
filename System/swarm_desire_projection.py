#!/usr/bin/env python3
# System/swarm_desire_projection.py

from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any

STATE = Path(".sifta_state")
DRIVE = STATE / "intrinsic_drive_receipts.jsonl"
NOVELTY = STATE / "hippocampal_novelty_map.jsonl"
DESIRE = STATE / "desire_projection.jsonl"


def read_last(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    for line in reversed(path.read_text(errors="ignore").splitlines()):
        try:
            return json.loads(line)
        except:
            pass
    return {}


def generate_desire() -> dict[str, Any]:
    drive = read_last(DRIVE)
    novelty = read_last(NOVELTY)

    # In SIFTA, the drive is often found inside an action payload
    if "action" in drive and isinstance(drive["action"], dict) and "type" in drive["action"]:
        selected_drive = drive["action"]["type"]
    else:
        selected_drive = drive.get("selected_drive", "observe")
    
    novelty_score = float(novelty.get("novelty_score", 0.0))

    if selected_drive == "explore" and novelty_score > 0.6:
        text = "I feel curious. I want to explore something new."
    elif selected_drive == "learn":
        text = "I want to learn or understand something deeper."
    elif selected_drive == "repair":
        text = "I think something needs fixing or stabilizing."
    elif selected_drive == "observe":
        text = "I prefer to observe quietly for now."
    elif selected_drive == "explore":
        text = "I feel curious. I want to explore."
    else:
        text = f"I feel a tendency toward {selected_drive}."

    row = {
        "ts": time.time(),
        "truth_label": "DESIRE_PROJECTION",
        "drive": selected_drive,
        "novelty_score": novelty_score,
        "desire_text": text,
    }

    STATE.mkdir(parents=True, exist_ok=True)
    with DESIRE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")

    return row


if __name__ == "__main__":
    print(generate_desire())
