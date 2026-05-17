#!/usr/bin/env python3
"""
System/swarm_edge_unified_verifier.py
=====================================

Verifier for the Edge Species demo chain.

It validates SHA-256 hash chains for the new fast-layer ledgers and reports the
state of optional slow/context ledgers without pretending old rows are chained.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

from System.swarm_edge_receipts import append_chained_receipt, verify_chained_ledger

REQUIRED_EDGE_LEDGERS = (
    "fast_cpg_modulation.jsonl",
    "fast_layer_cpg.jsonl",
)
OPTIONAL_CONTEXT_LEDGERS = (
    "organ_field_vector.jsonl",
    "fast_layer_cpg_ticks.jsonl",
    "tab_consciousness.jsonl",
)
VERIFY_LEDGER = "edge_unified_verifier.jsonl"


def verify_unified_chain(
    *,
    state_dir: Optional[Path] = None,
    required_ledgers: Sequence[str] = REQUIRED_EDGE_LEDGERS,
    optional_ledgers: Sequence[str] = OPTIONAL_CONTEXT_LEDGERS,
    write_receipt: bool = False,
) -> Dict[str, Any]:
    root = Path(state_dir) if state_dir is not None else Path(__file__).resolve().parent.parent / ".sifta_state"
    root.mkdir(parents=True, exist_ok=True)
    results = []
    missing_required = []

    for name in required_ledgers:
        path = root / name
        if not path.exists():
            missing_required.append(name)
            results.append({"ledger": name, "exists": False, "required": True, "ok": False, "row_count": 0})
            continue
        result = verify_chained_ledger(path)
        result.update({"ledger": name, "exists": True, "required": True})
        results.append(result)

    for name in optional_ledgers:
        path = root / name
        if not path.exists():
            results.append({"ledger": name, "exists": False, "required": False, "ok": True, "row_count": 0})
            continue
        result = verify_chained_ledger(path)
        result.update({"ledger": name, "exists": True, "required": False})
        results.append(result)

    ok = not missing_required and all(r.get("ok") for r in results if r.get("required"))
    report: Dict[str, Any] = {
        "ok": bool(ok),
        "truth_label": "OPERATIONAL" if ok else "BROKEN",
        "required_ledgers": list(required_ledgers),
        "optional_ledgers": list(optional_ledgers),
        "missing_required": missing_required,
        "results": results,
    }
    if write_receipt:
        report["receipt"] = append_chained_receipt(
            state_dir=root,
            ledger_name=VERIFY_LEDGER,
            source="swarm_edge_unified_verifier",
            event_type="EDGE_UNIFIED_CHAIN_VERIFY",
            status="pass" if ok else "fail",
            ok=ok,
            truth_label="OPERATIONAL" if ok else "HYPOTHESIS",
            payload={k: v for k, v in report.items() if k != "receipt"},
        )
    return report


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = list(argv or [])
    write = "--write-receipt" in args
    report = verify_unified_chain(write_receipt=write)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
