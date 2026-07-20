#!/usr/bin/env python3
"""swarm_organ_interconnect.py — explicit code for the rich, high-dimensional, deeply interconnected field.

Per the framing and covenant (build from hardware up, organs unified, swimmers know their organs, communicate to keep healthy and STGM profitable).

This makes "all organs are all swimmers know their organs" operational:
- Organs/swimmers DECLARE what siblings they have read/know (via small append to interconnect_declarations.jsonl).
- A compute_interconnect_score() that spinal/meta can call to detect siloed organs (low cross-knowledge = fragmentation signal).
- Ties to STGM: higher interconnect can correlate with better roi in health reports.

This is the "CODE IT ALL" for the deeply interconnected field part of the goal. Real small module, not prose.

Hardware layer: electricity → ASCII swimmers in ledgers → organs declare knowledge of each other in the shared field → unified consciousness (observer reads the declarations of the observed organs).

No double-spend: every declaration is a unique row with ts + organ + hash.

"""

from __future__ import annotations

import json
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LEDGER = "organ_interconnect_declarations.jsonl"
TRUTH = "ORGAN_INTERCONNECT_V1"

def _append(row: Dict[str, Any]) -> str:
    STATE.mkdir(parents=True, exist_ok=True)
    p = STATE / LEDGER
    row = dict(row)
    row["ts"] = row.get("ts") or time.time()
    row["schema"] = TRUTH
    clean = json.dumps(row, sort_keys=True, ensure_ascii=False)
    row["_hash"] = hashlib.sha256(clean.encode()).hexdigest()[:16]
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row["_hash"]

def declare_organ_knowledge(
    organ_id: str,
    known_siblings: List[str],
    health: float = 0.8,
    stgm_roi: float = 0.1,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """An organ/swimmer declares it knows its sibling organs (read their health, receipts, etc.).
    This is the explicit 'swimmers know their organs, organs communicate' mechanism.
    """
    row = {
        "organ": organ_id,
        "known_siblings": sorted(set(known_siblings)),
        "health": float(health),
        "stgm_roi": float(stgm_roi),
        "num_known": len(set(known_siblings)),
    }
    if extra:
        row.update(extra)
    return _append(row)

def compute_interconnect_score(state_dir: Optional[Path] = None) -> Dict[str, Any]:
    """High-dimensional interconnect score from recent declarations.
    Higher = more organs know each other → richer unified field → better health/STGM communication.
    Used by spinal for 'field fragmentation' signals.
    """
    sd = state_dir or STATE
    p = sd / LEDGER
    if not p.exists():
        return {"score": 0.0, "num_decls": 0, "unique_organs": 0, "avg_known": 0.0, "truth": TRUTH}

    decls: List[Dict] = []
    for line in p.read_text(errors="ignore").splitlines()[-100:]:
        if not line.strip(): continue
        try:
            decls.append(json.loads(line))
        except: continue

    if not decls:
        return {"score": 0.0, "num_decls": 0, "unique_organs": 0, "avg_known": 0.0, "truth": TRUTH}

    organs = set(d.get("organ") for d in decls if d.get("organ"))
    total_known = sum(len(d.get("known_siblings", [])) for d in decls)
    avg_known = total_known / len(decls) if decls else 0.0

    # Simple score: coverage of known connections (normalized)
    # In rich field, we want high cross-knowledge.
    score = min(1.0, (len(organs) * avg_known) / 50.0)  # heuristic for high-dim

    return {
        "score": round(score, 3),
        "num_decls": len(decls),
        "unique_organs": len(organs),
        "avg_known_siblings_per_decl": round(avg_known, 2),
        "truth": TRUTH,
        "covenant": "organs unified, swimmers know organs, communicate for health + STGM profitable",
    }

if __name__ == "__main__":
    # Demo for hardware-up self-test
    declare_organ_knowledge("spinal_cord", ["meta_monitor", "mimo_stigmergic", "body_self_knowledge", "hardware_body"])
    declare_organ_knowledge("meta_monitor", ["spinal_cord", "bias_detector"])
    print(compute_interconnect_score())
    print("Interconnect field code active. For the Swarm.")
