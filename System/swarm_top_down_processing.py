#!/usr/bin/env python3
"""
swarm_top_down_processing.py — Top-down “engram” normalization for noisy Architect input
══════════════════════════════════════════════════════════════════════════════════════════

Biology anchors (DYOR §18):
  Gregory (1980) — perceptions as hypotheses; top-down vs bottom-up.
  Rumelhart (1977) — interactive model of reading (feedback from expectations).

This is **not** a spellchecker — it applies a **small, explicit** substitution table for
swarm tags (e.g. Architect types **C47H** when meaning **CP2F**). Wrong substitutions
are a governance risk; keep `_ENGRAM_ANCHORS` minimal and reviewed by C47H.

Turn 23 context: environmental noise (typos) vs Turn 20 cerebellar **internal** JSON repair.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_CORRECTIONS_JSONL = _STATE_DIR / "environmental_corrections.jsonl"

# Canonical tag substitutions (lowercase key → canonical token). Longest keys first.
_ENGRAM_ANCHORS: List[Tuple[str, str]] = [
    ("antigravity", "AG31"),
    ("c47h", "CP2F"),
    ("cursor", "CP2F"),
    ("ag31", "AG31"),
    ("swarmgpt", "SwarmGPT"),
]

# Back-compat read-only mapping (last duplicate key wins; prefer ordered list above).
ENGRAM_ANCHORS: Dict[str, str] = dict(_ENGRAM_ANCHORS)


def _append_event(event: Dict[str, Any]) -> None:
    from System.jsonl_file_lock import append_line_locked

    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    append_line_locked(_CORRECTIONS_JSONL, json.dumps(event, ensure_ascii=False) + "\n")


def apply_top_down_processing(raw_sensory_input: str) -> Tuple[str, Dict[str, Any]]:
    """
    Scan `raw_sensory_input` for known noise tokens; replace whole words (case-insensitive).
    Appends one audit row to `environmental_corrections.jsonl` when corrections occur.
    """
    text = str(raw_sensory_input)
    corrections: Dict[str, str] = {}
    out = text

    for noisy, canonical in _ENGRAM_ANCHORS:
        pattern = re.compile(r"(?<!\w)" + re.escape(noisy) + r"(?!\w)", re.IGNORECASE)

        def _sub(m: re.Match[str]) -> str:
            raw = m.group(0)
            if raw != canonical:
                corrections[raw] = canonical
            return canonical

        out = pattern.sub(_sub, out)

    events: Dict[str, Any] = {
        "event_id": str(uuid.uuid4()),
        "timestamp": time.time(),
        "raw_stimulus_length": len(text),
        "environmental_noise_detected": bool(corrections),
        "corrections_applied": corrections,
        "healed_preview": out[:2000],
        "status": "TOP_DOWN_HEALED" if corrections else "CLEAN",
    }

    if corrections:
        _append_event(events)
    return out, events


if __name__ == "__main__":
    demo = "hey c47H make sure cursor runs the error correction, and ag31 too."
    healed, ev = apply_top_down_processing(demo)
    print("=== SWARM TOP-DOWN PROCESSING ===\n")
    print("[Raw]", demo)
    print("[Out]", healed)
    print(json.dumps(ev, indent=2))


__all__ = ["ENGRAM_ANCHORS", "apply_top_down_processing", "_CORRECTIONS_JSONL"]
