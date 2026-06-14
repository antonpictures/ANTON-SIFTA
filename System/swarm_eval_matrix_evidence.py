"""Eval matrix panel evidence pointers — real paths only (r1021 C7)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

_REPO = Path(__file__).resolve().parents[1]
_HUMAN_SUFFIX_RE = re.compile(r"\.(human|owner|george)\b", re.IGNORECASE)


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = _REPO / path_str
    return p


def panel_evidence_rows() -> List[Dict[str, Any]]:
    """Canonical evidence map for matrix panels."""
    return [
        {"panel": "living_substrate_loc", "path": "System/swarm_code_body_inventory.py", "ledger": ".sifta_state/canonical_organ_registry_snapshot.json"},
        {"panel": "appearance_walk", "path": ".sifta_state/eval/code_body_appearance_order.jsonl", "ledger": ".sifta_state/eval/code_body_appearance_order.jsonl"},
        {"panel": "organ_field", "path": "System/swarm_canonical_organ_registry.py", "ledger": ".sifta_state/organ_field.jsonl"},
        {"panel": "self_improvement", "path": "System/swarm_self_improvement_loop.py", "ledger": ".sifta_state/self_improvement_proposals.jsonl"},
        {"panel": "effector_gate", "path": "System/swarm_effector_gate.py", "ledger": ".sifta_state/effector_gate.jsonl"},
        {"panel": "intent_nonce", "path": "System/swarm_intent_nonce_gate.py", "ledger": ".sifta_state/intent_nonce_gate.jsonl"},
        {
            "panel": "shadow_swimmer_quarantine",
            "path": "System/swarm_ide_trace_quarantine.py",
            "ledger": ".sifta_state/ide_stigmergic_trace.jsonl",
            "quarantine_ledger": ".sifta_state/ide_stigmergic_trace_quarantine.jsonl",
            "mana_is_crypto": False,
            "stgm_is_crypto": True,
        },
        {"panel": "matrix_html", "path": "tools/generate_organ_eval_matrix_v2.py", "ledger": ".sifta_state/eval/ORGAN_EVAL_MATRIX_V2.html"},
        {"panel": "census_delta", "path": "System/swarm_census_delta.py", "ledger": ".sifta_state/eval/code_body_census_delta.jsonl"},
    ]


def validate_panel_evidence() -> Dict[str, Any]:
    rows = panel_evidence_rows()
    problems: List[Dict[str, Any]] = []
    ok_count = 0
    for row in rows:
        path = str(row.get("path") or "")
        ledger = str(row.get("ledger") or "")
        if _HUMAN_SUFFIX_RE.search(path) or _HUMAN_SUFFIX_RE.search(ledger):
            problems.append({"panel": row["panel"], "reason": "human_suffix_path", "path": path})
            continue
        path_ok = _resolve(path).exists()
        ledger_ok = _resolve(ledger).exists()
        if not path_ok:
            problems.append({"panel": row["panel"], "reason": "missing_path", "path": path})
        elif not ledger_ok:
            problems.append({"panel": row["panel"], "reason": "missing_ledger", "ledger": ledger})
        else:
            ok_count += 1
    return {"ok": not problems, "ok_count": ok_count, "total": len(rows), "problems": problems}
