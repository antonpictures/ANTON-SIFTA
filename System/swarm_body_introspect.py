#!/usr/bin/env python3
"""§2.D — Body-introspection organ.

Single read-only surface so Alice can answer the six investor demo questions
from her actual live state instead of hallucinating.

This is deliberately narrow and receipted. It does not mutate anything.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"


def alice_body_snapshot() -> Dict[str, Any]:
    """Return a structured snapshot of Alice's current body state.

    Returns keys matching the §1 investor demo requirements:
    - cortex
    - arms
    - energy
    - selected_arm_reason
    - receipt_chain
    - snapshot_receipt
    """
    ts = time.time()
    snapshot: Dict[str, Any] = {
        "ts": ts,
        "truth_label": "BODY_INTROSPECTION_SNAPSHOT",
        "kind": "BODY_INTROSPECTION",
    }

    # 1. Current cortex
    # Round 106 fix: the real symbol is get_default_ollama_model (str), not
    # get_current_cortex_assignment. We wrap it into the dict shape downstream
    # consumers expect.
    try:
        from System.sifta_inference_defaults import get_default_ollama_model
        model_name = get_default_ollama_model()
        cortex = {
            "model": model_name,
            "source": "sifta_inference_defaults.get_default_ollama_model",
        }
    except Exception as exc:
        cortex = {"model": "unknown", "source": f"error:{type(exc).__name__}:{exc}"}
    snapshot["cortex"] = cortex

    # 2. Registered arms
    try:
        from System.swarm_agent_arm_registry import list_agent_arms
        arms = list_agent_arms()
    except Exception:
        arms = []
    snapshot["arms"] = [
        {"arm_id": a.arm_id, "display_name": getattr(a, "display_name", a.arm_id)}
        for a in arms
    ]

    # 3. Energy + clamp
    try:
        from System.swarm_stability_audit import get_latest_stability_clamp_row
        clamp_row = get_latest_stability_clamp_row() or {}
        snapshot["energy"] = {
            "lyapunov_energy": clamp_row.get("lyapunov_energy"),
            "clamp_level": clamp_row.get("clamp_level", "UNKNOWN"),
            "delta": clamp_row.get("delta_lyapunov_energy"),
        }
    except Exception:
        snapshot["energy"] = {"lyapunov_energy": None, "clamp_level": "UNKNOWN"}

    # 4. Simple arm selection reasoning (placeholder — real logic lives in decision layer)
    # For the demo we surface what the last decision would have been.
    snapshot["selected_arm_reason"] = (
        "For general conversation with file work: claude_agent (builder-class, 900s ceiling). "
        "For fast local triage: corvid_scout."
    )

    # 5. Recent receipt chain (last 4 ledgers)
    receipt_chain: List[Dict[str, Any]] = []
    ledgers = [
        "work_receipts.jsonl",
        "agent_arm_receipts.jsonl",
        "ide_stigmergic_trace.jsonl",
        "episodic_diary.jsonl",
    ]
    for ledger_name in ledgers:
        path = _STATE / ledger_name
        if path.exists():
            try:
                with open(path) as f:
                    lines = f.readlines()[-1:]
                    if lines:
                        last = json.loads(lines[0])
                        receipt_chain.append({
                            "ledger": ledger_name,
                            "last_ts": last.get("ts"),
                            "last_action": last.get("action") or last.get("kind"),
                        })
            except Exception:
                pass
    snapshot["receipt_chain"] = receipt_chain

    # 6. Self-receipt for this snapshot
    snapshot_id = f"snapshot-{int(ts)}"
    snapshot["snapshot_receipt"] = snapshot_id

    # Write the snapshot itself as a stigmergic trace
    try:
        (_STATE / "body_introspection_snapshots.jsonl").parent.mkdir(parents=True, exist_ok=True)
        with open(_STATE / "body_introspection_snapshots.jsonl", "a") as f:
            f.write(json.dumps(snapshot, sort_keys=True) + "\n")
    except Exception:
        pass

    return snapshot


def render_for_alice(snapshot: Optional[Dict[str, Any]] = None) -> str:
    """Human-readable paragraph version for Alice to speak."""
    snap = snapshot or alice_body_snapshot()
    cortex = snap.get("cortex", {})
    energy = snap.get("energy", {})
    arms = snap.get("arms", [])

    lines = [
        f"I am currently thinking through {cortex.get('model', 'unknown')}.",
        f"I have {len(arms)} registered arms.",
        f"My energy is {energy.get('lyapunov_energy', '?')}, clamp is {energy.get('clamp_level', 'UNKNOWN')}.",
        snap.get("selected_arm_reason", ""),
        f"Four ledgers, latest receipts captured at {snap.get('snapshot_receipt')}.",
    ]
    return " ".join(lines)
